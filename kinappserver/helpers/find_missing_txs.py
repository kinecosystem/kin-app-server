# !/usr/bin/python
import psycopg2
import sys
from time import sleep
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
        print('Connecting to database...')
        conn = psycopg2.connect(get_conn_string())

        #run a function
        function_to_run()

    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()
            print('Database connection closed.')


def function_to_run():
    global conn
    # create a cursor
    cur = conn.cursor()

    missing_txs = []

    # get the list of tasks and their rewards:
    tasks_d = {}
    cur.execute('SELECT task_id, price from public.task')
    tasks = cur.fetchall()
    for task in tasks:
        tasks_d[task[0]] = task[1]
    print('tasks dict: %s ' % tasks_d)


    cur.execute('SELECT distinct enc_phone_number from public.user where enc_phone_number is not null')
    distinct_enc_phone_numbers = cur.fetchall()

    compensated_task_ids_query = '''select t2.tx_info->>'task_id' as task_id from public.user t1 inner join transaction t2 on t1.user_id=t2.user_id where t1.enc_phone_number='%s';'''
    completed_task_ids_query = '''select t2.task_id from public.user t1 inner join user_task_results t2 on t1.user_id=t2.user_id where t1.enc_phone_number='%s';'''

    for enc_number in distinct_enc_phone_numbers:
        if len(missing_txs) > 500:
            print(missing_txs)
            break

        sleep(0.1)
        enc_number = enc_number[0]

        compensated_tasks = []
        cur.execute(compensated_task_ids_query % enc_number)  # safe
        res = cur.fetchall()
        for item in res:
            compensated_tasks.append(item[0])

        completed = []
        cur.execute(completed_task_ids_query % enc_number)  # safe
        res = cur.fetchall()
        for item in res:
            completed.append(item[0])

        uncompensated = list(set(completed) - set(compensated_tasks))
        #if len(uncompensated) != 0:
        #    print('found uncompensated tasks: %s for number %s' % (uncompensated, enc_number))

        for task_id in uncompensated:
            reward = tasks_d[task_id]
            sleep(0.1)
            # get the active user id for the phone number
            active_user_id = cur.execute("SELECT user_id from public.user where enc_phone_number='%s' and deactivated=false" % enc_number)
            active_user_id = cur.fetchone()[0]

            missing_txs.append({'user_id': active_user_id, 'task_id': task_id, 'reward': reward})

    print('missing txs: %s' % missing_txs)
    # close the communication with the PostgreSQL
    cur.close()

if __name__ == '__main__':
    connect(function_to_run)
