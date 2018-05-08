from datadog import statsd
import requests
import json
import os

URL_PREFIX = 'http://localhost:8000'

def report_db_stats():
    """reports the total and available number of goods for every offer id in the server"""

    import socket
    hostname = socket.gethostbyname(socket.gethostname())

    response = requests.get(URL_PREFIX + '/stats/db')
    stats = json.loads(response.text)['stats']
    statsd.gauge('kinitapp.%s.%s.%s' % (os.environ['ENV'], hostname,'dbstats-checkedout'), stats['checkedout'])
    statsd.gauge('kinitapp.%s.%s.%s' % (os.environ['ENV'], hostname,'dbstats-overflow'), stats['overflow'])
    statsd.gauge('kinitapp.%s.%s.%s' % (os.environ['ENV'], hostname,'dbstats-checkedin'), stats['checkedin'])


report_db_stats()
