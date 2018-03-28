import uuid

from kinappserver import amqp_publisher, config

def generate_push_id():
    return uuid.uuid4().hex

def engagement_payload_apns(push_type):
    push_id = generate_push_id()
    # TODO report push_id
    if push_type == 'engage-recent':
        return apns_payload("", "Let's earn some Kin!", push_type, push_id)
    elif push_type == 'engage-week':
        return apns_payload("", "Let's earn some Kin!", push_type, push_id)

def apns_payload(title, body, push_type, push_id, sound='default'):
    '''generate an apns payload'''
    payload_dict = {'aps': {'alert':{'title': title, 'body': body}, 'sound': sound}, 'kin':{'push_type': push_type, 'push_id': push_id}}

    print('the payload: %s' % payload_dict)
    return payload_dict


def send_gcm(token, payload):
    payload_dict = {}
    payload_dict['message'] = payload
    amqp_publisher.send_gcm("eshu-key", payload_dict, [token], False, config.GCM_TTL_SECS)


def send_apns(token, payload):
    amqp_publisher.send_apns("eshu-key", payload, [token])
