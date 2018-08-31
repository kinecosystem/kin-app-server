from datadog import statsd
import requests
import json
import os

URL_PREFIX = 'http://localhost:80/internal'


def report_inventory():
    """reports the total and available number of goods for every offer id in the server"""
    inventory = {}
    response = requests.get(URL_PREFIX + '/good/inventory')
    try:
        inventory = json.loads(response.text)['inventory']
    except Exception as e:
        print('cant collect inventory')
        pass
    for offer_id in inventory.keys():
        metric_name_total = 'inventory-offerid-%s-total' % offer_id
        metric_name_unallocated = 'inventory-offerid-%s-unallocated' % offer_id
        statsd.gauge('kinitapp.%s.%s' % (os.environ['ENV'], metric_name_unallocated), inventory[offer_id]['unallocated'])
        statsd.gauge('kinitapp.%s.%s' % (os.environ['ENV'], metric_name_total), inventory[offer_id]['total'])


def report_bh_balance():
    """tracks the current balance of our blackhawk account"""
    balance = 0
    response = requests.get(URL_PREFIX + '/blackhawk/account/balance')
    try:
        balance = json.loads(response.text)['balance']
    except Exception as e:
        print('cant collect balance')
        pass

    metric = 'bh-account-balance'
    statsd.gauge('kinitapp.%s.%s' % (os.environ['ENV'], metric), balance)


def report_unauthed_user_count():
    """tracks the current number of unauthed users"""
    count = -1
    response = requests.get(URL_PREFIX + '/users/unauthed')
    try:
        count = len(json.loads(response.text)['user_ids'])
    except Exception as e:
        print('cant collect unauthed user count')
        pass

    metric = 'unauthed_user_count'
    statsd.gauge('kinitapp.%s.%s' % (os.environ['ENV'], metric), count)


report_inventory()
report_bh_balance()
report_unauthed_user_count()
