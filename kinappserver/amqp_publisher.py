"""Eshulib Publiser: Defines an AMQP channels-pool mechanism that is used to send GCM and APNS messages.
   Messages are sent over a a re-usable connection, using multiple channels.

Usage:
- Users of this lib must first call init_config() with the configuration.
- Once init'd, users may call send_apns, send_gcm or send_apns_voip to send
messages.

Implementation details:
- The pool is initialized upon the first call to publish().
- The size of the pool is configurable via the CHANNEL_POOL_SIZE parameter.
- Ideally, the pool can be torn-down with the tear_down() function.
- If the connection is lost, the pool should re-establish one and recreate the
channels.

"""

from json import dumps
from threading import RLock
from time import sleep
from datetime import datetime
from amqpstorm import Connection


class AmqpPublisher:
    WAIT_BLOCKED = 1

    # member variables:
    _channels_manager = None
    inited = False
    ESHU_CONFIG = None

    def __init__(self):
        """Ctor for the top level object - the publisher."""
        self.ESHU_CONFIG = {'QUEUE_NAME': '',
                       'EXCHANGE_NAME': '',
                       'ADDRESS': '',
                       'USER': '',
                       'PASSWORD': '',
                       'VIRTUAL_HOST': '',
                       'HEARTBEAT': '',
                       'APP_ID': '',
                       'TTL': '',
                       'CHANNEL_POOL_SIZE': 10}
        self._channels_manager = None
        self._inited = False

    def get_config(self):
        return self.ESHU_CONFIG

    def init_config(self, env, address, queue_name, exchange_name, virtual_host, user, password, heartbeat, app_id, ttl):
        if self.inited:
            print('refusing to re-init config')
            return False

        if env == '':
            log.error('cant init publisher: no env provided')
            return False
        else:
            print('initing publisher with %s env' % env)

        self.ESHU_CONFIG['ADDRESS'] = address
        self.ESHU_CONFIG['QUEUE_NAME'] = queue_name + '-' + env
        self.ESHU_CONFIG['EXCHANGE_NAME'] = exchange_name + '-' + env
        self.ESHU_CONFIG['VIRTUAL_HOST'] = virtual_host
        self.ESHU_CONFIG['USER'] = user
        self.ESHU_CONFIG['PASSWORD'] = password
        self.ESHU_CONFIG['HEARTBEAT'] = heartbeat
        self.ESHU_CONFIG['APP_ID'] = app_id + '-' + env
        self.ESHU_CONFIG['TTL'] = ttl
        self.inited = True
        return True

    def send_apns_voip(self, routing_key, payload, tokens):
        """Send the given payload to the given tokens - as voip apns."""
        self.internal_send_apns(routing_key, payload, tokens, True, self.ESHU_CONFIG['TTL'])

    def send_apns(self, routing_key, payload, tokens):
        """Send the given payload to the given tokens - as apns."""
        self.internal_send_apns(routing_key, payload, tokens, False, self.ESHU_CONFIG['TTL'])

    def send_gcm(self, routing_key, payload, tokens, dry_run, ttl):
        """Send a gcm message to the given tokens with the given payload, ttl"""
        for token in tokens:
            message = {'app_id': self.ESHU_CONFIG['APP_ID'],
                       'data': {
                            'gcm': {
                                    'to': token,
                                    'dry_run': dry_run,
                                    'time_to_live': ttl,
                                    'data': payload
                                   }
                            }
                        }
            self.publish(routing_key, dumps(message))

    def internal_send_apns(self, routing_key, payload, tokens, is_voip, ttl):
        for token in tokens:
            message = dumps({'app_id': self.ESHU_CONFIG['APP_ID'],
                'data': {
                    'ttl': ttl,
                    'apns': {
                        'device_token': token,
                        'voip': is_voip,
                        'data': payload
                    }}})
            self.publish(routing_key, message)

    def publish(self, routing_key, payload, retry=True):
        """Publish the given payload."""
        if not self.inited:
            log.error('cant publish payload: lib not yet inited')
            return

        if self._channels_manager is None:
            self._channels_manager = ChannelsManager(self.ESHU_CONFIG)

        channel = self._channels_manager.get_channel()

        try:
            # Publish a message to the queue.
            channel.publish(payload, routing_key)
        except Exception as e:
            print('amqp_publisher: failed to publish message to amqp. exception: %s' % e)
            self._channels_manager.release_channel(channel)
            print('amqp_publisher: attempting to re-establish connection...')
            self._channels_manager.establish_connection()
            if retry:
                print('amqp_publisher: attempting to re-send message...')
                self.publish(routing_key, payload, retry=False)
        else:
            self._channels_manager.release_channel(channel)


class Channel:
    """Channel object."""

    _busy = False
    _index = -1
    _exchange_name = None
    _channel = None
    _config = None
    _app_id = None

    def __init__(self, connection, index, exchange_name, app_id):
        """Ctor for this channel."""
        self._index = index
        self._exchange_name = exchange_name
        self._busy = False
        self._app_id = app_id
        self._channel = connection.channel()
        #self._channel.queue.declare(ESHU_CONFIG['QUEUE_NAME'], durable=True)
        self._channel.confirm_deliveries()

    def acquire(self):
        """Acquire this channel."""
        self._busy = True

    def release(self):
        """Release this channel."""
        self._busy = False

    def is_busy(self):
        """Return True if the channel is taken."""
        return self._busy

    def publish(self, payload, routing_key):
        """Publish the given payload via this channel."""

        # If connection is blocked, wait before trying to publish again.
        #while self._channel.is_blocked:
        #    time.sleep(WAIT_BLOCKED)
        #    continue

        # Set a bunch of message-level properties
        props = {'app_id': self._app_id, 'content_encoding': 'UTF-8', 'content_type': 'text/plain', 'timestamp': datetime.utcnow()}

        self._channel.basic.publish(body=payload, routing_key=routing_key, exchange=self._exchange_name, properties=props)

    def close(self):
        """Close the channel."""
        self._channel.close()


class ChannelsManager:
    """Manages AMQP channels over a single connection."""

    IDLE = 0.01
    _channels = []
    _connection = None
    _lock = RLock()
    _config = None

    def __init__(self, config):
        """Init the connection and channels."""
        self._config = config
        self._channels = []
        self._connection = None
        self._lock = RLock()

        self.init_pool()

    def init_pool(self):
        """Set up a connection and channels if the connection is closed/doesn't exist.

        Does nothing if the connection is already up.
        """
        if self._connection and self._connection.is_open:
            return
        elif self._connection and self._connection.is_opening:
            while self._connection.is_opening:
                sleep(ChannelsManager.IDLE)
            return
        else:
            # create/recreate the connection and overwrite the channels
            self.establish_connection()

    def establish_connection(self):
        self._connection = Connection(self._config['ADDRESS'],
                                      self._config['USER'],
                                      self._config['PASSWORD'],
                                      virtual_host=self._config['VIRTUAL_HOST'],
                                      heartbeat=self._config['HEARTBEAT'])
        # clear previous channels if they exist
        for channel in self._channels:
            channel.close()
        # create new channels
        self._channels = []
        for i in range(self._config['CHANNEL_POOL_SIZE']):
            print('creating an amqpl channel...')
            self._channels.append(Channel(self._connection, i, self._config['EXCHANGE_NAME'], self._config['APP_ID']))

    def get_channel(self):
        """Acquire a channel from the pool. Blocks if none are available."""
        while True:
            with self._lock:

                self.init_pool()  # does nothing if the pool exists. recreates it on error

                for channel in self._channels:
                    if not channel.is_busy():
                        channel.acquire()
                        return channel
            sleep(ChannelsManager.IDLE)

    def release_channel(self, channel):
        """Release the given channel back to the pool."""
        with self._lock:
            for c in self._channels:
                if c == channel:
                    channel.release()
                    return True
            return False

    def tear_down(self):
        """Close all channels in the pool and the connection."""
        for channel in self._channels:
            channel.close()
        self._connection.close()