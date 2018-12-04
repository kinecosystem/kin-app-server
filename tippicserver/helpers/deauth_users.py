# !/usr/bin/python
import psycopg2
import sys
from time import sleep
import arrow
sys.path.append("..")  # Adds higher directory to python modules path.

conn = None


def get_conn_string():
    from config import DB_CONNSTR
    return DB_CONNSTR


def connect(function_to_run):
    """ Connect to the PostgreSQL database server """
    global conn
    try:
        # connect to the PostgreSQL server
        #print('Connecting to database...')
        conn = psycopg2.connect(get_conn_string())

        #run a function
        function_to_run()

    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()
            #print('Database connection closed.')


def function_to_run():
    global conn
    # create a cursor
    cur = conn.cursor()


    now = arrow.utcnow()
    deauth_user_ids = []
    # get all the recently sent user-ids that were previously authenticated
    cur.execute("select user_id, send_date, ack_date from push_auth_token where send_date  >= NOW() - INTERVAL '15 seconds' and authenticated=true")
    recently_sent_auth_tokens = cur.fetchall()
    if len(recently_sent_auth_tokens) == 0:
        return
    print('deauth users: examining user_ids: %s' % [item[0] for item in recently_sent_auth_tokens])

    for item in recently_sent_auth_tokens:
        user_id=item[0]
        send_date=item[1]
        ack_date=item[2]

        send_date = arrow.get(send_date)
        ack_date = arrow.get(ack_date)
        sent_secs_ago = (now - send_date).total_seconds()
        ack_secs_ago = (now - ack_date).total_seconds()
        #TODO it would make more sense to simply erase the ack_date after we send, and simply find those users that have
        #TODO no ack_date.`
        if 5 < sent_secs_ago < 10 and ack_secs_ago > 10:
            print('scan_for_deauthed_users: marking user %s as unauthenticated. sent_secs_ago: %s. acked %s secs ago' % (user_id, sent_secs_ago, ack_secs_ago))
            deauth_user_ids.append(user_id)

    for user_id in deauth_user_ids:
        print('deauthing user %s' % user_id)

    # close the communication with the PostgreSQL
    cur.close()

if __name__ == '__main__':
    connect(function_to_run)
