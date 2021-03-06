from datadog import statsd
import requests
import json
import os
import redis


def report_exceptions():
    """tracks the number of exceptions found in the log"""
    import subprocess
    import socket
    redis_key = 'track-exceptions-%s-%s' % (os.environ['ENV'], socket.gethostname())
    REDIS_URL = 'kinit-app-prod.qugi0x.ng.0001.use1.cache.amazonaws.com'
    completed_process = subprocess.run("cat /var/log/kinappserver.err.log|grep Traceback|wc -l", shell=True, stdout=subprocess.PIPE)
    try:
        num_exceptions = int(completed_process.stdout)
    except Exception as e:
        log.error('failed to calculate num_exceptions from stdout %s. aborting' % completed_process.stdout)
        return False

    # compare against value in redis
    redis_con = redis.StrictRedis(host=REDIS_URL, port=6379, db=0)
    try:
        previous_value = int(redis_con.get(redis_key))
    except Exception as e:
        log.error('cant get previous value from reids. Exception %s. defaulting to 0' % e)
        previous_value = 0

    # evaluate
    if previous_value < num_exceptions:
        print('detected new exceptions. previous value: %s current: %s' % (previous_value, num_exceptions))
        found_new_exceptions = 2 # datadog treshold set to '1'
    elif previous_value >= num_exceptions:
        found_new_exceptions = 0

    # persist to redis
    redis_con.set(redis_key, num_exceptions)

    # also send to dd
    statsd.gauge('track-exceptions', found_new_exceptions, tags=['app:kinit,env:%s' % os.environ['ENV']])
    return True


report_exceptions()

