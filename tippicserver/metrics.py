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
        log.error('cant collect inventory')
        pass
    for offer_id in inventory.keys():
        metric_name_unallocated = 'inventory-offerid-%s-unallocated' % offer_id
        statsd.gauge(metric_name_unallocated, inventory[offer_id]['unallocated'], tags=['app:tippic,env:%s' % os.environ['ENV']])


def report_bh_balance():
    """tracks the current balance of our blackhawk account"""
    requests.get(URL_PREFIX + '/blackhawk/account/balance')


def report_tx_total():
    response = requests.get(URL_PREFIX + '/tx/total')
    try:
        to_public = (json.loads(response.text)['total']['to_public'])
        from_public = (json.loads(response.text)['total']['from_public'])
        public_kin = to_public - from_public
        metric = 'public_kin'
        statsd.gauge(metric, public_kin, tags=['app:tippic,env:%s' % os.environ['ENV']])
    except Exception as e:
        log.error('cant collect tx totals')
        pass




def report_unauthed_user_count():
    """tracks the current number of unauthed users"""
    count = -1
    response = requests.get(URL_PREFIX + '/users/unauthed')
    try:
        count = len(json.loads(response.text)['user_ids'])
    except Exception as e:
        log.error('cant collect unauthed user count')
        pass

    metric = 'unauthed_user_count'
    statsd.gauge(metric, count, tags=['app:tippic,env:%s' % os.environ['ENV']])


report_inventory()
report_bh_balance()
report_unauthed_user_count()
report_tx_total()
