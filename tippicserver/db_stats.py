from datadog import statsd
import requests
import json
import os

URL_PREFIX = 'http://localhost:80/internal'

def report_db_stats():
    """reports the total and available number of goods for every offer id in the server"""

    import socket
    hostname = socket.gethostbyname(socket.gethostname())

    response = requests.get(URL_PREFIX + '/stats/db')
    stats = json.loads(response.text)['stats']
    statsd.gauge('dbstats-checkedout', stats['checkedout'], tags=['app:tippic,env:%s' % os.environ['ENV']])



report_db_stats()
