from datadog import statsd
import requests
import json
import os

URL_PREFIX = "http://localhost:8000"

def metric(url, metric_name):
    response = requests.get(url)
    try:
	    count = json.loads(response.text)['count']
    except:
	    count = -1
    statsd.increment('kinitapp.%s.%s' % (os.environ['ENV'], metric_name), count)

metric(URL_PREFIX + "/count_txs?minutes_ago=1", "tx_count")