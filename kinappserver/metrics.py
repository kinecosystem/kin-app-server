from datadog import statsd
import requests
import json
import os

URL_PREFIX = 'http://localhost:8000'

def simple_metric_increment(url, metric_name, key):
    """reports a simple, numerical metric to statsd that is returned via REST api from the server"""
    response = requests.get(url)
    try:
        value = json.loads(response.text)[key]
    except:
        value = -1
    statsd.increment('kinitapp.%s.%s' % (os.environ['ENV'], metric_name), value)

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


report_inventory()
