import requests


def request_re_register(user_ids):
    resp = requests.post('http://localhost:8000/users/push_register', json={'user_ids': user_ids})
    print(resp.status_code)

def


def start():



if __name__=='__main__':
    start()