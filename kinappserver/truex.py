import requests
import hmac
import json
from urllib.parse import urlencode
import time
from kinappserver import config, utils, models
from base64 import b64encode
from hashlib import sha256, sha1

import logging as log

# work in progress #

TRUEX_GET_ACTIVITY_URL = 'https://get.truex.com/v2'
HARDCODED_CLIENT_IP = '188.64.206.240'
TRUEX_USER_ID_EXPIRATION_SEC = 60*60*12 # 12 hours


def get_activity(user_id, remote_ip, user_agent, window_width=None, window_height=None, screen_density=None, client_request_id=None):
    """generate a single activity from truex for the given user_id"""
    try:
        if not client_request_id: #TODO do we even need this?
            client_request_id = str(int(time.time()))

        # get the truex user_id for this user
        network_user_id = models.get_truex_user_id(user_id)

        url = generate_truex_url(network_user_id, remote_ip, client_request_id, user_agent, window_width, window_height, screen_density)
        print('truex get activity url: %s. network_user_id: %s' % (url, network_user_id))
        resp = requests.get(url)
        resp.raise_for_status()
    except Exception as e:
        log.error('failed to get an activity from truex: %s' % e)
        return None
    else:
        # process the response:
        activities = resp.json()
        if len(activities) == 0:
            if remote_ip != HARDCODED_CLIENT_IP:
                print('no activities returned for userid %s with remote_ip %s. re-trying with hardcoded ip...' % (user_id, remote_ip))
                return get_activity(user_id, HARDCODED_CLIENT_IP, user_agent, window_width, window_height, screen_density, client_request_id)
            else:
                log.error('cant get activity for userid %s with remote_ip: %s. bummer' % (user_id, remote_ip))
                return None

        # slap the network user_id onto the activity:
        activities[0]['network_user_id'] = network_user_id

        return activities[0]


def generate_truex_url(network_user_id, remote_ip, client_request_id, user_agent, window_width, window_height, screen_denisty):

    data = {
        # partner information
        'placement.key': config.TRUEX_PARTNER_HASH,
        'placement.url': 'https',
        # app
        'app.name': 'Kinit',
        # user
        'user.uid': network_user_id,
        # device
        'device.ip': remote_ip,
        'device.ua': user_agent if user_agent is not None else 'Mozilla/5.0 (Linux; Android 8.0.0; SM-G935F Build/R16NW; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/67.0.3396.87 Mobile Safari/537.36',
        # response
        'response.max_activities': 1,
        # request ID
        #'client_request_id': client_request_id
    }

    # add optional window/screen data
    if screen_denisty:
        data['device.sd'] = screen_denisty
    if screen_denisty:
        data['adspace.width'] = window_width
    if screen_denisty:
        data['adspace.height'] = window_height

    try:
        url = TRUEX_GET_ACTIVITY_URL + '?%s' % urlencode(data)
    except Exception as e:
        log.error('failed to encode truex request')
        return None

    return url


def sign_truex_attrs(attrs):
    """signs the given attributes accoring to True[X]'s specs and returns the signature"""
    attr_names = [
        'application_key',
        'network_user_id',
        'currency_amount',
        'currency_label',
        'revenue',
        'placement_hash',
        'campaign_name',
        'campaign_id',
        'creative_name',
        'creative_id',
        'engagement_id',
        'client_request_id'
    ]
    sig_attrs = [attrs.get(n, None) for n in attr_names]
    if any(v is None for v in sig_attrs):
        return None

    sig_attrs = dict(zip(attr_names, sig_attrs))
    gen_signature = ''.join([n + '=' + str(sig_attrs[n]) for n in sorted(attr_names)]) + config.TRUEX_CALLBACK_SECRET
    return b64encode(hmac.new(bytes(config.TRUEX_CALLBACK_SECRET, 'latin-1'), bytes(gen_signature, 'latin-1'), sha1).digest())


def verify_sig(request):
    """verifies that the given request was indeed signed by Truex"""
    signature = request.get('sig')

    gen_signature = sign_truex_attrs(request)

    if not gen_signature:
        print('verify_truex: failed to sign the request')
        return False

    if signature.encode('latin-1') != gen_signature:
        print('verify_truex: the incoming request does not match the signature')
        print('signature: %s' % signature)
        print('gen_signature: %s' % gen_signature)
        return False

    return True
