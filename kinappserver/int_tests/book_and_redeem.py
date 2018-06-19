import simplejson as json
from uuid import uuid4
from time import sleep
import requests

USER_ID_HEADER = "X-USERID"
SERVER_URL = "0.0.0.0:8000"


def post_to_server(path, payload=None, headers=None):
    req = None
    try:
        req = requests.post(SERVER_URL+path, json=payload, headers=headers)
    except Exception as e:
        print('request to (%s) failed' % path)
        raise(e)
    else:
        return req

def get_from_server(path):
    req = None
    try:
        req = requests.get(SERVER_URL+path)
    except Exception as e:
        print('request to (%s) failed' % path)
        raise(e)
    else:
        return req

def assertEqual(a,b):
    if a != b:
        print('failed assert of (%s) and (%b)' % (a,b))
        raise Exception("Assertion failed")


def book_and_redeem():
    """test creating orders"""
    offerid = '0'
    offer = {'id': offerid,
             'type': 'gift-card',
             'type_image_url': "https://s3.amazonaws.com/kinapp-static/brand_img/gift_card.png",
             'domain': 'music',
             'title': 'offer_title',
             'desc': 'offer_desc',
             'image_url': 'image_url',
             'skip_image_test': True,
             'price': 2,
             'address': 'GCORIYYEQP3ANHFT6XHMBY7VB3RH53WB5KZZHGCEXYRWCEJQZUXPGWQM',
             'provider':
                {'name': 'om-nom-nom-food', 'image_url': 'http://inter.webs/horsie.jpg'},
            }

    # add an offer
    resp = post_to_server('/offer/add', {'offer': offer})
    assertEqual(resp.status_code, 200)

    # enable the offer
    resp = post_to_server('/offer/set_active',
                          {'id': offerid,
                           'is_active': True})
    assertEqual(resp.status_code, 200)

    # create a good instance for the offer (1)
    resp = post_to_server('/good/add',
                          {'offer_id': offerid,
                            'good_type': 'code',
                            'value': 'abcd'})
    assertEqual(resp.status_code, 200)

    # create a good instance for the offer (2)
    resp = post_to_server('/good/add',
                          {'offer_id': offerid,
                            'good_type': 'code',
                            'value': 'abcd'})
    assertEqual(resp.status_code, 200)

    # create a good instance for the offer (3)
    resp = post_to_server('/good/add',
                          {'offer_id': offerid,
                            'good_type': 'code',
                            'value': 'abcd'})
    assertEqual(resp.status_code, 200)

    # create a good instance for the offer (4)
    resp = post_to_server('/good/add',
                          {'offer_id': offerid,
                            'good_type': 'code',
                            'value': 'abcd'})
    assertEqual(resp.status_code, 200)

    # 4 goods at this point
    resp = get_from_server('/good/inventory')
    assertEqual(resp.status_code, 200)
    assertEqual(json.loads(resp.data)['inventory'], {offer['id']: {'total': 4, 'unallocated': 4}})

    # register a couple of users
    userid1 = uuid4()
    resp = post_to_server('/user/register',{
                        'user_id': str(userid1),
                        'os': 'android',
                        'device_model': 'samsung8',
                        'device_id': '234234',
                        'time_zone': '05:00',
                        'token': 'fake_token',
                        'app_ver': '1.0'})
    assertEqual(resp.status_code, 200)

    userid2 = uuid4()
    resp = post_to_server('/user/register', {
                        'user_id': str(userid2),
                        'os': 'android',
                        'device_model': 'samsung8',
                        'device_id': '234234',
                        'time_zone': '05:00',
                        'token': 'fake_token',
                        'app_ver': '1.0'})
    assertEqual(resp.status_code, 200)

    # get user2 redeem history - should be empty
    resp = get_from_server('/user/redeemed', headers={USER_ID_HEADER: str(userid2)})
    self.assertEqual(resp.status_code, 200)
    print('redeemed: %s' % json.loads(resp.data))
    self.assertEqual(json.loads(resp.data)['redeemed'], [])

        # get user2 tx history - should have 0 items
        resp = get_from_server('/user/transactions', headers={USER_ID_HEADER: str(userid2)})
        self.assertEqual(resp.status_code, 200)
        print('txs: %s' % json.loads(resp.data))
        self.assertEqual(json.loads(resp.data)['txs'], [])

if __name__ == '__main__':
    book_and_redeem()
