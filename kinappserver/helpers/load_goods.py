# this script loads a list of codes from a file as goods with a given offer_id
# usage: python3 load_goods.py <filename> <the_offer_id>

import sys
import requests 

def load_goods(filename, offer_id):
    print('reading file: %s' % filename)
    url = 'http://localhost:8000/good/add'
    headers = {"Content-Type": "application/json"}
    lines = tuple(open(filename, 'r'))
    payload = '''{"offer_id": "%s", "good_type": "code", "value": "%s"}'''
    for code in lines:
        payload = payload % (offer_id, code.rstrip())
        #print('posting payload: %s' % payload)
        requests.post(url, headers, json=payload)

if __name__=="__main__":
    load_goods(sys.argv[1], sys.argv[2])