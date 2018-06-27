import requests
import hmac
import json
from urllib.parse import urlencode
import time
from kinappserver import config
from base64 import b64encode
from hashlib import sha256, sha1

# work in progress #

TRUEX_GET_ACTIVITY_URL = 'https://get.truex.com/v2'
HARDCODED_CLIENT_IP = '188.64.206.240'


def get_activity(user_id, remote_ip, user_agent, window_width=None, window_height=None, screen_density=None, client_request_id=None):
    """generate a single activity from truex for the given user_id"""
    try:
        if not client_request_id: #TODO do we even need this?
            client_request_id = str(int(time.time()))
        url = generate_truex_url(user_id, remote_ip, client_request_id, user_agent, window_width, window_height, screen_density)
        print('truex get activity url: %s' % url)
        resp = requests.get(url)
        resp.raise_for_status()
    except Exception as e:
        print('failed to get an activity from truex: %s' % e)
        return False, None
    else:
        # process the response:
        activities = resp.json()
        if len(activities) == 0:
            if config.DEBUG:
                print('DEBUG: no activities received from truex, returning a canned activity')
                canned_activity = {'activity': [{'campaign_id': 13255, 'currency_amount': 1, 'display_text': None, 'id': 8974, 'image_url': 'https://s3.amazonaws.com/media.socialvi.be/assets/17190/gen-124x124.jpg?1362613767', 'name': 'Kik - Kin - KF Panda Mobile SVNRE', 'partner_id': 219, 'revenue_amount': '0.0072', 'session_id': 'jtGbGk5vTCO8Je8WcOEC6w', 'window_height': 540, 'window_url': 'http://serve.truex.com/engage?app.name=Kinit&campaign_id=13255&client_request_id=1529492319&creative_id=8974&currency_amount=1&env%5B%5D=flash&env%5B%5D=html&impression_signature=19b84efb65cd0e27182288dd32879dd3f3c8463e8cf1bfae011ec1991a232be2&impression_timestamp=1529492319.936121&initials=0&internal_referring_source=nvLFDGdUTEKlyGB2iPpQ5A&ip=188.64.206.239&network_user_id=c1ee58d9-c068-44fc-8c62-400f0537e8d2&placement_hash=21be84de4fa0cc0315a5563d02e293b99b67cd16&session_id=jtGbGk5vTCO8Je8WcOEC6w&timezone_offset=-2.0&user_agent=Android+5.0&vault=y6q616h7tfp2qpe00d37hr8srh8znci49d0yr7b4dax8bxaehq4xsoi193i0b4tenjbfdgs6lxtnk042qo33f5nig8fhhjd5rkywr9kdxq4z8qsdx492dqjkzpc79ukb0lavdhugs5oifkid57g43sw9pd9xv8x75b7a2z95lgg1ogdyrwv2cqq7aa0z9owryk9da3pi09p5vg6szmuzn4oq2ijk2we9hv5rg1xuu2qutlzg1pxy7m8iisrpqnm8mfzpqbst6bxrd0kzh6m9g72yjprhuqw7t30fzgz2hiuhfyi&bid_info=cikxt0o9ptky3tm9rabewwtlu78os1b56xfbkvrdkrfs0mwfkwt5sitfs0jelkkdk7zv48bt70erq9274xtrldizwz6ahu76ugbuvgdtya1pti3xqhgodmju76km4bhrzyx9cn7ww1gxxfeeaqd6y5jxxdvig8cmngyscfkw73k29lxhlm7ggsymghiibnub4m8z2a25m7s33wl56p5rrpw3279a03g6rpu0jduneoroi15cpbrmp7uk9ficy1c31p6mjgu860ws3ax96r10ewow1pcqt9qj4whb8hthnldswi62x7jch62131mgnotyysw6y1vsi5lfr84hzqdjucsb0ygwxopfm7gsm92ol9pdbxamyt12fw97wfkik7u4ct3qtpe382ovu75eurfctfho9qiezm9dfsklz862djhnk93qy5fvwgy6i', 'window_width': 960}], 'status': 'ok'}
                return True, canned_activity
            elif remote_ip != HARDCODED_CLIENT_IP:
                print('no activities returned for userid %s with remote_ip %s. re-trying with hardcoded ip...' % (user_id, remote_ip))
                return get_activity(user_id, HARDCODED_CLIENT_IP, user_agent, window_width, window_height, screen_density, client_request_id)
            else:
                return True, None

        return True, activities[0]


def generate_truex_url(user_id, remote_ip, client_request_id, user_agent, window_width, window_height, screen_denisty):
    data = {
        # partner information
        'placement.key': config.TRUEX_PARTNER_HASH,
        'placement.url': 'https',
        # app
        'app.name': 'Kinit',
        # user
        'user.uid': user_id,
        # device
        'device.ip': remote_ip,
        'device.ua': user_agent if user_agent is not None else 'Android 5.0',
        # response
        'response.max_activities': 1,
        # request ID
        #'client_request_id': client_request_id
    }

    # add optional window/screen data
    if screen_denisty:
        data['device.sd'] = screen_denisty
    if screen_denisty:
        data['adspace.width'] = window_width
    if screen_denisty:
        data['adspace.height'] = window_height

    try:
        url = TRUEX_GET_ACTIVITY_URL + '?%s' % urlencode(data)
    except Exception as e:
        print('failed to encode truex request')
        return None

    return url


def sign_truex_attrs(attrs):
    """signs the given attributes accoring to True[X]'s specs and returns the signature"""
    attr_names = [
        'application_key',
        'network_user_id',
        'currency_amount',
        'currency_label',
        'revenue',
        'placement_hash',
        'campaign_name',
        'campaign_id',
        'creative_name',
        'creative_id',
        'engagement_id',
        'client_request_id'
    ]
    sig_attrs = [attrs.get(n, None) for n in attr_names]
    if any(v is None for v in sig_attrs):
        return None

    sig_attrs = dict(zip(attr_names, sig_attrs))
    gen_signature = ''.join([n + '=' + str(sig_attrs[n]) for n in sorted(attr_names)]) + config.TRUEX_CALLBACK_SECRET
    return b64encode(hmac.new(bytes(config.TRUEX_CALLBACK_SECRET, 'latin-1'), bytes(gen_signature, 'latin-1'), sha1).digest())


def verify_sig(request):
    """verifies that the given request was indeed signed by Truex"""
    signature = request.get('sig')

    gen_signature = sign_truex_attrs(request)

    if not gen_signature:
        print('verify_truex: failed to sign the request')
        return False

    if signature.encode('latin-1') != gen_signature:
        print('verify_truex: the incoming request does not match the signature')
        print('signature: %s' % signature)
        print('gen_signature: %s' % gen_signature)
        return False

    return True
