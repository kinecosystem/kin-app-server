from datadog import statsd
import requests
import json
import os

URL_PREFIX = 'http://localhost:8000'

def report_balance():
    """tracks the kin and xlm balance on this server"""
    import socket
    hostname = socket.gethostbyname(socket.gethostname())
    response = requests.get(URL_PREFIX + '/balance')

    base_seed_kin = json.loads(response.text)['balance']['base_seed']['kin']
    base_seed_xlm = json.loads(response.text)['balance']['base_seed']['xlm']
 
    metric = 'base-seed-kin'
    statsd.gauge('kinitapp.%s.%s.%s' % (os.environ['ENV'], hostname, metric), base_seed_kin)
    metric = 'base-seed-xlm'
    statsd.gauge('kinitapp.%s.%s.%s' % (os.environ['ENV'], hostname, metric), base_seed_xlm)

    return True


report_balance()

