# blackhawk logic be here:
# all logic concerning the offline generation of gift cards (egift in BH terminology)

# blackhawk offers an api that lets us buy egifts - codes - from various vendors. this code is run
# periodically by cron to determine whether we need to generate more codes.
# each item in the blackhawk_offer table correlates to an entry in the offers table. Once the number
# of unallocated goods for a certain offer goes below a threshold, the code below requests another batch
# from blackhawk. it can take up-to 4 minutes until the cards are actually ready ('processed'), which is why this
# process is done off-line. once the cards are ready, a 'good' entry is written in to the Good table.
#
# the blackhawk api specifies how to generate an order: first you must 'create' it, then 'add cards' to it
# and finally 'complete' it (and then wait for it to be processed.

# blackhawk/omnicode client portal url: https://clients.omnicard.com/

import json
import requests
from kinappserver.models import create_bh_card, list_unprocessed_orders, set_processed_orders, \
    create_good, get_bh_creds, replace_bh_token, list_inventory, get_bh_offers
from kinappserver import config
from kinappserver.utils import increment_metric, gauge_metric
import urllib.parse

HEADERS = {'Content-Type': 'application/x-www-form-urlencoded'}
API_BASE_URI = 'https://api.omnicard.com/2.x'


def parse_bh_response_message(resp):
    """generic function to get the message portion from blackhawk API or None on failure"""
    if resp.status_code != 200:
        print('http request to blackhawk failed. request: %s' % resp.url)
        return None
    else:
        try:
            response = resp.json()['response']
            if response['status'] != 1000:
                print('error: blackhawk response status != 1000')
                print('response: %s' % response)
                return None
            return response['message']
        except Exception as e:
            print(e)
            print('failed to parse blackhawk api response')
            return None


def escape_payload(payload_dict):
    """used to convert a python dict to the format accepted by blackhawk's servers"""
    payload = ''
    for key in payload_dict.keys():
        payload = (payload + '&') if payload is not '' else ''
        payload = payload + key + '=' + payload_dict[key]
    return urllib.parse.quote_plus(payload, safe=';/?:@&=+$,')


def generate_auth_token_api(username, password):
    """get an ephemeral auth token from BH"""
    resp = requests.post('%s/apiUsers/auth.json' % API_BASE_URI, headers=HEADERS,
                         data=escape_payload({'data[username]': username, 'data[password]': password}))
    return parse_bh_response_message(resp)


def get_order_status_api(token, order_id):
    """gor the given order_id, returns the order status (like 'processed' or 'verified')"""
    resp = requests.post('%s/orders/getOrder.json' % API_BASE_URI, headers=HEADERS,
                         data=escape_payload({'data[token]': token, 'data[order_id]': order_id}))
    message = parse_bh_response_message(resp)
    if message:
        return message['order']['status']
    return None


def get_bh_account_balance_api(token, account_id):
    """gets the balance on the account (one account is assumed)"""
    accounts = get_accounts_data_api(token)
    if accounts is None:
        print('no blackhawk account configured - cant get balance')
        return None

    for account in accounts:
        if str(account['account']['id']) == str(account_id):
            return account['account']['balance']

    print('could not find account id %s balance' % account_id)


def get_accounts_data_api(token):
    """returns info about this account from BH"""
    resp = requests.post('%s/funds/getAccounts.json' % API_BASE_URI, headers=HEADERS,
                         data=escape_payload({'data[token]': token}))
    account_data = parse_bh_response_message(resp)
    if not account_data:
        print('failed ot get account data with token: %s' % token)
    return account_data


def get_merchants_api(token):
    """returns all the merchants"""
    resp = requests.post('%s/orderOptions/getMerchants.json' % API_BASE_URI, headers=HEADERS,
                         data=escape_payload({'data[token]': token}))
    return parse_bh_response_message(resp)


def get_merchant_api(token, merchant_code):
    """returns all the merchants"""
    resp = requests.post('%s/orderOptions/getMerchant.json' % API_BASE_URI, headers=HEADERS,
                         data=escape_payload({'data[token]': token, 'data[merchant_code]': str(merchant_code)}))
    return parse_bh_response_message(resp)


def egift_start_order_api(token, merchant_code, merchant_template_id):
    """starts an egift order with the given merchant code and template id"""

    resp = requests.post('%s/egiftOrders/start.json' % API_BASE_URI, headers=HEADERS,
                         data=escape_payload({'data[token]': token, 'data[merchant_code]': str(merchant_code),
                                              'data[delivery]': 'download',
                                              'data[merchant_template_id]': str(merchant_template_id),
                                              'data[contact][name]': 'support@kinitapp.com',
                                              'data[contact][email]': 'support@kinitapp.com',
                                              'data[contact][organization]': 'kinitapp.com'}))
    result = parse_bh_response_message(resp)
    return result['order_id'] if result else None


def egift_complete_order_api(token, order_id, account_id, digital_signature):
    """completes an egift order"""
    resp = requests.post('%s/egiftOrders/complete.json' % API_BASE_URI, headers=HEADERS,
                         data=escape_payload(
                                        {'data[token]': token,
                                         'data[order_id]': str(order_id),
                                         'data[options][payment_type]': 'fundsbank',
                                         'data[options][account_id]': str(account_id),
                                         'data[options][digital_signature]': str(digital_signature)}))
    result = parse_bh_response_message(resp)
    return result['order_id'] if result else None


def get_account_balance():
    """gets the accounts balance."""
    creds = get_bh_creds()
    if not creds or not creds['token']:
        print('no bh creds object/auth token')
        return False
    else:
        return get_bh_account_balance_api(creds['token'], creds['account_id'])


def egift_add_card_api(token, order_id, denomination):
    """adds a card == generates a single redemption code

    note that according to the API the code isn't usable until after the order is completed
    and the order has been processed. the redemption code can be received from this API, and also
    the get_card API.
    """
    resp = requests.post('%s/egiftOrders/addCard.json' % API_BASE_URI, headers=HEADERS,
                         data=escape_payload({'data[token]': token,
                                              'data[order_id]': order_id,
                                              'data[card][message]': 'random message the user will never see',
                                              'data[card][denomination]': str(float(denomination)),
                                              'data[card][first_name]': 'kinit',
                                              'data[card][last_name]': 'user'}))
    message = parse_bh_response_message(resp)
    return message['card']['id'] if message else None


def egift_get_card_api(token, card_id):
    """return info about the given card_id. used to determine card status"""
    resp = requests.post('%s/egiftCards/getCard.json' % API_BASE_URI, headers=HEADERS,
                         data=escape_payload({'data[token]': token, 'data[card_id]': str(card_id)}))
    message = parse_bh_response_message(resp)
    return message['card'] if message else None


def order_gift_cards(merchant_code, merchant_template_id, denomination, num_of_cards=1):
    """this function orders a set of gift cards"""
    card_ids = []

    # get the creds object
    creds = get_bh_creds()
    if not creds or not creds['token']:
        print('no bh creds object/auth token')
        return False
    else:
        token = creds['token']

    order_id = egift_start_order_api(token, merchant_code, merchant_template_id)
    if not order_id:
        print('failed to create order')
        return False

    for i in range(num_of_cards):
        card_id = egift_add_card_api(token, order_id, denomination)
        if not card_id:
            print('failed to create card')
            return False
        else:
            print('order_gift_cards: added a bh card with id: %s' % card_id)
            card_ids.append(card_id)

    returned_order_id = egift_complete_order_api(token, order_id, creds['account_id'], creds['digital_signature'])
    if not returned_order_id:
        print('failed to complete order_id %s' % order_id)

    # at this point, the card isn't ready yet. we need to monitor the order
    # until it is processed. in the meanwhile, lets store it in the db.

    for card_id in card_ids:
        create_bh_card(card_id, order_id, merchant_code, denomination)
        increment_metric('bh_card_ordered')

    return True


def track_orders():
    """go over all the unprocessed orders and determine whether they were processed.
    if so, retrieve the redemption code for each of the cards in the now-processed orders.

    returns the number of yet unprocessed orders or -1 if the token was bad / sth went wrong
    """

    creds = get_bh_creds()
    token = creds['token']
    if not token:
        print('track_orders: no bh auth token')
        return -1

    orders_dict = list_unprocessed_orders()
    unprocessed_orders = 0

    for order_id in orders_dict.keys():
        status = get_order_status_api(token, order_id)
        print('received status:%s for order_id:%s' % (status, order_id))
        if status == 'incomplete':
            print('ignoring order_id %s with status: incomplete' % order_id)
            continue
        if status == 'cancelled':
            print('ignoring order_id %s with status: cancelled' % order_id)
            continue
        if status == 'processed':
            # order was processed, so add all related cards to our db
            print('detected a processed order: %s. getting card codes for this order...' % order_id)
            for card_id in orders_dict[order_id]:
                card = egift_get_card_api(token, card_id)
                if card is None:
                    print('could not retrieve info about cardid %s' % card_id)
                    increment_metric('bh_card_processing_failure')
                    continue
                print('card info: %s' % card)
                code = card['redemption_details']['activation_account_number']  # the actual redemption code is called 'activation_account_number'
                pin = card['redemption_details'].get('security_code', None)  # sometimes there's a PIN code - so add it if its there
                if pin:
                    code = code + '   PIN:%s' % pin
                merchant_code = card['merchant_code']
                card_id = card['id']
                order_id = card['order']['id']

                if create_good(merchant_code_to_offer_id(merchant_code, card_id, order_id), 'code', code):
                    print('created good with code %s for card_id %s' % (code, card_id))
                    increment_metric('bh_card_processed')
                else:
                    print('failed to convert bh card_id %s to good' % card_id)
                    increment_metric('bh_card_processing_failure')

            set_processed_orders(orders_dict[order_id])
        else:
            unprocessed_orders = unprocessed_orders + 1

    return unprocessed_orders


def merchant_code_to_offer_id(merchant_code, card_id, order_id):
    """convert the merchant_code from blackhawk into an offer id in our db"""
    for offer in get_bh_offers():
        # compare against the merchant template id, as that's what the api actually returns and not
        # the merchant code
        if offer.merchant_template_id == merchant_code:
            return offer.offer_id

    print('ERROR: unknown merchant_code %s - cant convert card id %s in order %s' % (merchant_code, card_id, order_id))
    return None


def refresh_bh_auth_token(force=False):
    """this function re-creates the bh auth token and saves it to the db

    this function will be called by cron periodically to update the token before it expires.
    this function assumes the db contains the relevant creds needed to create a new token
    """
    creds = get_bh_creds()
    if not creds:
        print('cant get bh creds from db. bailing')
        return False
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    if not force and (now - creds['token_generation_time']).total_seconds() < 60*60*24*2:
        # no need to refresh token. still quite fresh.
        return True

    new_token = generate_auth_token_api(creds['username'], creds['password'])
    if not new_token:
        print('failed to generate new token from bh')
        return False

    if replace_bh_token(new_token):
        print('replaced bh auth token in the db to: %s' % new_token)
    else:
        print('failed to replace bh token in db')
        return False

    return True


def replenish_bh_cards():
    """inspect the current status of the goods, and buy additional cards if needed.
    this function is called by cron every minute.
    this function only handles amazon gift cards at the moment.
    this function will not order additional cards as long as there are some cards
    still being processed by blackhawk.
    """
    
    # start by converting previously-unprocessed orders into goods
    yet_unprocessed_orders = track_orders()
    if yet_unprocessed_orders < 0:
        print('could not determine the number of yet unprocessed orders - bailing')
        return False

    # TODO: at the moment, we only generate a new order (for any card) if there are no pending yet-unprocessed orders.
    # TODO this may create a bottleneck once we have multiple blackhawk offers configured. in the future, we may want
    # TODO to change that.
    if yet_unprocessed_orders > 10:
        print('replenish_bh_cards: not making additional blackhawk orders while there are %s unprocessed orders' % yet_unprocessed_orders)
        return True

    inventory = list_inventory()

    # get current balance:
    # if the balance is very low, don't continue as it just creates incomplete-able orders in the BH db.
    try:
        balance = get_account_balance()
    except Exception as e:
        print('track_orders: something went wrong trying to get the balance. exception: %s', e)
        return False
    else:
        if int(float(balance)) < config.BLACKHAWK_CRITICAL_BALANCE_THRESHOLD:
            print('replenish_bh_cards: balance is critically low (%s, threshold: %s), refusing to continue' % (balance, config.BLACKHAWK_CRITICAL_BALANCE_THRESHOLD))
            return False

    # go over all the bh offers and see if any need ordering
    for offer in get_bh_offers():
        goods_left = inventory[offer.offer_id]['unallocated']
        if goods_left < offer.minimum_threshold:
            print('detected shortage in blackhawk offer_id %s (%s left, threshold: %s). ordering more from blackhawk' % (offer.offer_id, goods_left, offer.minimum_threshold))
            if not order_gift_cards(offer.merchant_code,
                                    offer.merchant_template_id,
                                    offer.denomination,
                                    offer.batch_size):
                return True
        else:
            print('no need to replenish cards for blackhawk offer_id %s. (available: %s, threshold: %s)' % (offer.offer_id, goods_left, offer.minimum_threshold))

    return True
