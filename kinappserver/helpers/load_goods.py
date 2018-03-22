# this script loads a list of codes from a file as goods with a given offer_id
# usage: python3 load_goods.py <filename> <the_offer_id>
import json
import sys
import requests

def load_goods(filename, offer_id):
    print('reading file: %s' % filename)
    url = 'http://localhost:8000/good/add'
    headers = {"Content-Type": "application/json"}
    lines = tuple(open(filename, 'r'))
    payload = '''{"offer_id": "%s", "good_type": "code", "value": "%s"}'''
    for code in lines:
        inner_payload = payload % (offer_id, code.rstrip())
        print('posting payload: %s' % inner_payload)
        requests.post(url, headers=headers, json=json.loads(inner_payload))

if __name__=="__main__":
    load_goods(sys.argv[1], sys.argv[2])