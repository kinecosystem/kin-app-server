import requests
import json
from urllib.parse import urlencode
import time

# work in progress #

TRUEX_GET_ACTIVITY_URL = 'http://get.truex.com/v2'
PARTNER_KEY = ''
HARDCODED_CLIENT_IP = '54.90.81.9'

def get_activity_for_user(user_id):
    """gets an activity from the truex api"""
    try:
        activity_id = '123'
        payload = {'user': {'uid': str(user_id)},
                   'device': {'ip': HARDCODED_CLIENT_IP},
                   #'response': {'callback': 'stage.kinitapp.com/truex_cb?activity_id=%s' % activity_id,
                   #             'max_activities': 1},
                   'placement': {'key': PARTNER_KEY}}

        response = requests.post(TRUEX_GET_ACTIVITY_URL, json=payload)
        print(response.json())
        response.raise_for_status()
    except Exception as e:
        print('faild to get activity from truex: %s' % e)
    else:
        json_response = json.loads(response.text)
        print('the json response: %s' % json_response)


def get_activity_for_user2(user_id):
    """gets an activity from the truex api"""
    try:
        payload = {'user.uid': str(user_id),
                   'device.ip': HARDCODED_CLIENT_IP,
                   'placement.key': PARTNER_KEY}
        response = requests.get(TRUEX_GET_ACTIVITY_URL, params=payload)
        print(response.url)
        response.raise_for_status()
    except Exception as e:
        print('faild to get activity from truex: %s' % e)
    else:
        json_response = json.loads(response.text)
        print('the json response: %s' % json_response)


def generate_truex_url(user_id, kp_version, client_request_id):

    data = {
        # partner information
        'partner_config_hash':PARTNER_KEY,
        'placement.key': PARTNER_KEY,
        # app
        'app.name': 'Kinit',
        'app.version': kp_version,
        # user
        'user.uid': user_id,
        # device
        'device.ip': HARDCODED_CLIENT_IP,
        'device.ua': 'Mozilla/5.0',
        # response
        'response.max_activities': 1,

        # request ID
        'client_request_id': client_request_id
    }

    data['user.age'] = '12'
    data['user.gender'] = 'm'

    try:
        url = TRUEX_GET_ACTIVITY_URL + '?%s' % urlencode(data)
    except:
        print('failed to encode truex')
        return None

    return url


if __name__ == '__main__':
    get_activity_for_user2('9e2f2783-6741-4dd1-a862-6dc0e908bd86')
    ##resp = requests.get(generate_truex_url('9e2f2783-4431-4dd1-a862-6dc0e908bd86', '2', str(int(time.time()))))
    #print(resp.url)
    #resp.raise_for_status()
    #print(resp)
    #print(resp.json())