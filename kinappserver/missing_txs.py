from datadog import statsd
import requests
import json
import os

URL_PREFIX = 'http://localhost:80/internal'


def report_missing_txs():
    """reports the number of users with missing txs in the db"""

    response = requests.get(URL_PREFIX + '/users/missing_txs')
    missing_txs = json.loads(response.text)['missing_txs']
    statsd.gauge('kinitapp.%s.%s' % (os.environ['ENV'], 'missing-txs'), len(missing_txs))


report_missing_txs()
