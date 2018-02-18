"""Eshulib Publiser: Defines an AMQP channels-pool mechanism that is used to send GCM and APNS messages.
   Messages are sent over a a re-usable connection, using multiple channels.

Usage:
- Users of this lib must first call init_config() with the configuration.
- Once init'd, users may call send_apns, send_gcm or send_apns_voip to send
messages.

Implementation details:
- The pool is initialized upon the first call to publish().
- The size of the pool is configurable via the CHANNEL_POOL_SIZE const.
- Ideally, the pool can be torn-down with the tear_down() function.
- If the connection is lost, the pool should re-establish one and recreate the
channels.

"""

from json import dumps
from threading import RLock
from time import sleep
from datetime import datetime
from amqpstorm import Connection

CHANNEL_POOL_SIZE = 10
WAIT_BLOCKED = 1
_channels_manager = None

inited = False
ESHU_CONFIG = {'QUEUE_NAME': '',
               'EXCHANGE_NAME': '',
               'ADDRESS': '',
               'USER': '',
               'PASSWORD': '',
               'VIRTUAL_HOST': '',
               'HEARTBEAT': '',
               'APP_ID': ''}


def init_config(address, queue_name, exchange_name, virtual_host, user, password, heartbeat, app_id):
    global ESHU_CONFIG, inited
    ESHU_CONFIG['ADDRESS'] = address
    ESHU_CONFIG['QUEUE_NAME'] = queue_name
    ESHU_CONFIG['EXCHANGE_NAME'] = exchange_name
    ESHU_CONFIG['VIRTUAL_HOST'] = virtual_host
    ESHU_CONFIG['USER'] = user
    ESHU_CONFIG['PASSWORD'] = password
    ESHU_CONFIG['HEARTBEAT'] = heartbeat
    ESHU_CONFIG['APP_ID'] = app_id
    inited = True


def send_apns_voip(routing_key, payload, tokens):
    """Send the given payload to the given tokens - as voip apns."""
    internal_send_apns(routing_key, payload, tokens, True)


def send_apns(routing_key, payload, tokens):
    """Send the given payload to the given tokens - as apns."""
    internal_send_apns(routing_key, payload, tokens, False)


def send_gcm(routing_key, payload, tokens, dry_run, ttl):
    """Send a gcm message to the given tokens with the given payload, ttl"""
    global ESHU_CONFIG
    for token in tokens:
        message = dumps({'app_id': ESHU_CONFIG['APP_ID'],
                         'data': {
                             'gcm': {'to': token,
                                    'dry_run': dry_run,
                                    'time_to_live': ttl,
                                    'data': payload
                                     }}})
        publish(routing_key, message)


def internal_send_apns(routing_key, payload, tokens, is_voip):
    global ESHU_CONFIG
    for token in tokens:
        message = dumps({'app_id': ESHU_CONFIG['APP_ID'],
            'data': {
                'apns': {
                    'device_token': token,
                    'voip': is_voip,
                    'data': payload
                }}})
        publish(routing_key, message)


def publish(routing_key, payload):
    """Publish the given payload."""
    global inited
    if not inited:
        print('cant publish payload: lib not yet inited')
        return

    global _channels_manager
    if _channels_manager is None:
        _channels_manager = ChannelsManager()

    channel = _channels_manager.get_channel()
    # Publish a message to the queue.
    channel.publish(payload, routing_key)
    _channels_manager.release_channel(channel)


class Channel():
    """Channel object."""

    _busy = False
    _channel = None
    _index = -1

    def __init__(self, connection, index):
        """Ctor for this channel."""
        self._channel = connection.channel()
        #self._channel.queue.declare(ESHU_CONFIG['QUEUE_NAME'], durable=True)
        self._channel.confirm_deliveries()
        self._index = index

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
        props = {'app_id': ESHU_CONFIG['APP_ID'], 'content_encoding': 'UTF-8', 'content_type': 'text/plain', 'timestamp': datetime.utcnow()}

        self._channel.basic.publish(body=payload, routing_key=routing_key, exchange=ESHU_CONFIG['EXCHANGE_NAME'], properties=props)

    def close(self):
        """Close the channel."""
        self._channel.close()


class ChannelsManager():
    """Manages AMQP channels over a single connection."""

    IDLE = 0.01
    _channels = []
    _connection = None
    _lock = RLock()

    def __init__(self):
        """Init the connection and channels."""
        self.init_pool()

    def init_pool(self):
        """Set up aconnection and channels if the connection is closed/doesn't exist.

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
            self._connection = Connection(ESHU_CONFIG['ADDRESS'],
                                          ESHU_CONFIG['USER'],
                                          ESHU_CONFIG['PASSWORD'],
                                          virtual_host=ESHU_CONFIG['VIRTUAL_HOST'],
                                          heartbeat=ESHU_CONFIG['HEARTBEAT'])
            # clear previous channels if they exist
            for channel in self._channels:
                channel.close()
            # create new channels
            self._channels = []
            for i in range(CHANNEL_POOL_SIZE):
                self._channels.append(Channel(self._connection, i))

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


if __name__ == '__main__':
    eshu ={
        'USER': 'admin',
        'PASSWORD': 'admin',
        'ADDRESS': '10.0.1.20',
        'VIRTUAL_HOST': 'kinapp',
        'QUEUE_NAME': 'eshu-queue',
        'EXCHANGE_NAME': 'eshu-exchange',
        'RELIABLE': True,
        'HEARTBEAT': 30,
        'APP_ID': 'kinapp'}

    gcm_payload = {"rguid": "task:1:1:engagement",
               "rounds_notification": {"notification_view_data": {
                   "epoc_time": 1458457811000,
                   "rguid": "task:1:1:engagement",
                   "type": "generic",
                   "type_data": {
                       "body": "Invite your closest friends to Rounds",
                       "notif_priority": "DEFAULT",
                       "sound": True,
                       "subtype": "NO_CALLS_FIRST_ITER",
                       "tap_action": {"data": "FRIENDS_TAB", "type": "OPEN_TAB"},
                       "title": "Have fun together!",
                       "visibility": "PUBLIC"}}}}

    init_config(eshu['ADDRESS'], eshu['QUEUE_NAME'], eshu['EXCHANGE_NAME'], eshu['VIRTUAL_HOST'], eshu['USER'], eshu['PASSWORD'], eshu['HEARTBEAT'], eshu['APP_ID'])
    for i in range(0, 1):
        send_gcm('eshu-key', gcm_payload, ['eRl3aOnvwt0:APA91bGF7CQOZB9lqNJnei0syRlpJrlOekDoS30F8bEooWWLsUkdPRUq6prZatgSfXDPXVLqaGeXNqApZgN4XKzLtXhQsq9EFSVNPoRH27Agux-S5D2EkIDNPa7-7EDGjLKymuPOT0O4'], False, ttl=DEFAULT_GCM_TTL)
