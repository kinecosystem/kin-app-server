from datadog import statsd
import requests
import json
import os

URL_PREFIX = 'http://localhost:80/internal'

def report_balance():
    """tracks the kin and xlm balance on this server"""
    import socket
    #hostname = socket.gethostbyname(socket.gethostname())
    response = requests.get(URL_PREFIX + '/balance')

    base_seed_kin = json.loads(response.text)['balance']['base_seed']['kin']
    base_seed_xlm = json.loads(response.text)['balance']['base_seed']['xlm']
 
    metric = 'base-seed-kin'
    statsd.gauge(metric, base_seed_kin, tags=['app:kinit,env:%s' % os.environ['ENV']])
    metric = 'base-seed-xlm'
    statsd.gauge(metric, base_seed_xlm, tags=['app:kinit,env:%s' % os.environ['ENV']])

    for index in range(10):
        metric = 'channel-seed-%s-xlm' % index
        channel_xlm = json.loads(response.text)['balance']['channel_seeds'].get(str(index), None)
        if channel_xlm:
            statsd.gauge(metric, int(channel_xlm['xlm']), tags=['app:kinit,env:%s' % os.environ['ENV']])

    return True


report_balance()

