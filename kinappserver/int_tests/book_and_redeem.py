import simplejson as json
from uuid import uuid4
import requests
import kin

USER_ID_HEADER = "X-USERID"
URL_PREFIX = 'http://localhost:80/internal'
STELLAR_KIN_ISSUER_ADDRESS = 'GCKG5WGBIJP74UDNRIRDFGENNIH5Y3KBI5IHREFAJKV4MQXLELT7EX6V'


def make_payment(address, amount):
    sdk = kin.SDK(horizon_endpoint_uri='https://horizon-testnet.kininfrastructure.com', network='Kin Testnet ; December 2018', secret_key=get_ssm_parameter('/config/stage/stellar/base-seed'))
    tx_hash = sdk.send_kin(address, amount, memo_text='testmemo')
    return tx_hash


def get_ssm_parameter(param_name, kms_key_region='us-east-1'):
    """retreives an encrpyetd value from AWSs ssm or None"""
    try:
        ssm_client = boto3.client('ssm', region_name=kms_key_region)
        print('getting param from ssm: %s' % param_name)
        res = ssm_client.get_parameter(Name=param_name, WithDecryption=True)
        return res['Parameter']['Value']
    except Exception as e:
        log.error('cant get secure value: %s from ssm' % param_name)
        print(e)
        return None


def post_to_server(path, payload=None, headers=None):
    req = None
    try:
        req = requests.post(SERVER_URL+path, json=payload, headers=headers)
        req.raise_for_status()
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
        log.error('failed assert of (%s) and (%b)' % (a,b))
        raise Exception("Assertion failed")


def assertNotEqual(a,b):
    if a == b:
        log.error('failed assert of (%s) and (%b)' % (a,b))
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
             'address': 'GCYUCLHLMARYYT5EXJIK2KZJCMRGIKKUCCJKJOAPUBALTBWVXAT4F4OZ',
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
                            'value': 'abcd1'})
    assertEqual(resp.status_code, 200)

    # create a good instance for the offer (3)
    resp = post_to_server('/good/add',
                          {'offer_id': offerid,
                            'good_type': 'code',
                            'value': 'abcd2'})
    assertEqual(resp.status_code, 200)

    # create a good instance for the offer (4)
    resp = post_to_server('/good/add',
                          {'offer_id': offerid,
                            'good_type': 'code',
                            'value': 'abcd3'})
    assertEqual(resp.status_code, 200)

    # 4 goods at this point
    resp = get_from_server('/good/inventory')
    assertEqual(resp.status_code, 200)
    assertEqual(json.loads(resp.data)['inventory'], {offer['id']: {'total': 4, 'unallocated': 4}})

    # register a couple of users
    userid1 = uuid4()
    resp = post_to_server('/user/register', {
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
    assertEqual(resp.status_code, 200)
    print('redeemed: %s' % json.loads(resp.data))
    assertEqual(json.loads(resp.data)['redeemed'], [])

    # get user2 tx history - should have 0 items
    resp = get_from_server('/user/transactions', headers={USER_ID_HEADER: str(userid2)})
    assertEqual(resp.status_code, 200)
    print('txs: %s' % json.loads(resp.data))
    assertEqual(json.loads(resp.data)['txs'], [])

    # create the first order
    resp = post_to_server('/offer/book',
                         {'id': offerid},
                         headers={USER_ID_HEADER: str(userid1)})
    assertEqual(resp.status_code, 200)
    data = json.loads(resp.data)
    assertEqual(data['status'], 'ok')
    assertNotEqual(data['order_id'], None)
    orderid1 = data['order_id']
    print('order_id: %s' % orderid1)

    # pay for the order with the sdk
    tx_hash = make_payment(offer['address'], offer['price'])

    # try to redeem the goods - should work
    resp = post_to_server('/offer/redeem',
                          {'tx_hash': tx_hash})
    assertEqual(resp.status_code, 200)
    data = json.loads(resp.data)
    print(data)

if __name__ == '__main__':
    book_and_redeem()
