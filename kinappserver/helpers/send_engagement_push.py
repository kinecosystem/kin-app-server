import requests
from time import sleep
SLEEP_TIME_SEC = 3


def main():
    for scheme in ('engage-recent','engage-week'):

        # request the list of user_ids from the server
        user_ids = get_userids(scheme)
        for user_id in user_ids:
            print('sending to user_id %s with scheme %s' % (user_id, scheme))
            send_push(user_id, scheme)
            sleep(SLEEP_TIME_SEC)


def get_userids(scheme):
    res = requests.get('https://api.kinitapp.com/engagement/list?scheme=%s' % scheme, timeout=180)
    return res.json()['user_ids']['iOS'] + res.json()['user_ids']['android']


def send_push(user_id, scheme):
    res = requests.post('https://api.kinitapp.com/engagement/push', json={'user_id': user_id, 'scheme': scheme})
    print(res)


if __name__ == '__main__':
    main()
