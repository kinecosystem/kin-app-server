import requests
import hmac
import json
from urllib.parse import urlencode
import time
from kinappserver import config
from base64 import b64encode
from hashlib import sha256, sha1

# work in progress #

TRUEX_GET_ACTIVITY_URL = 'https://get.truex.com/v2'
HARDCODED_CLIENT_IP = '188.64.206.240'


def get_activity(user_id, remote_ip, client_request_id=None):
    """generate a single activity from truex for the given user_id"""
    try:
        if not client_request_id: #TODO do we even need this?
            client_request_id = str(int(time.time()))
        url = generate_truex_url(user_id, remote_ip, client_request_id)
        print('truex get activity url: %s' % url)
        resp = requests.get(url)
        resp.raise_for_status()
    except Exception as e:
        print('failed to get an activity from truex: %s' % e)
        return False, None
    else:
        # process the response:
        activities = resp.json()
        if len(activities) == 0:
            print('no activities returned for userid %s' % user_id)
            return True, None

        return True, activities[0]


def generate_truex_url(user_id, remote_ip, client_request_id):
    data = {
        # partner information
        'placement.key': config.TRUEX_PARTNER_HASH,
        'placement.url': 'https',
        # app
        'app.name': 'Kinit',
        # user
        'user.uid': user_id,
        # device
        'device.ip': remote_ip if remote_ip is not None else HARDCODED_CLIENT_IP,
        'device.ua': 'Android 5.0',
        # response
        'response.max_activities': 1,
        # request ID
        #'client_request_id': client_request_id
    }

    try:
        url = TRUEX_GET_ACTIVITY_URL + '?%s' % urlencode(data)
    except Exception as e:
        print('failed to encode truex request')
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
