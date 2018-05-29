from datadog import statsd
import requests
import json
import os

URL_PREFIX = 'http://localhost:8000'


def report_missing_txs():
    """reports the number of users with missing txs in the db"""

    import socket
    hostname = socket.gethostbyname(socket.gethostname())
    response = requests.get(URL_PREFIX + '/users/missing_txs')
    missing_txs = json.loads(response.text)['missing_txs']
    statsd.gauge('kinitapp.%s.%s.%s' % (os.environ['ENV'], hostname, 'missing-txs'), len(missing_txs))


report_missing_txs()
