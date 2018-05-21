import requests


def compensate_user(user_id, task_id, kin_amount):
    print('compensating user %s for taskid %s' % (user_id, task_id))
    resp = requests.post('http://localhost:8000/user/compensate', json={'task_id': task_id, 'user_id': user_id, 'kin_amount': kin_amount})
    print(resp.status_code)


def start():
    import json

    with open('list.json') as f:
        data = json.load(f)
        for item in data['missing_txs']:
            compensate_user(item[0], item[1], item[2])


if __name__=='__main__':
    start()