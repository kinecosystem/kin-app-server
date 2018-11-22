from kinappserver import db, config
from kinappserver.utils import InvalidUsage, test_image, OS_ANDROID, OS_IOS
import logging as log

class Offer(db.Model):
    """the Offer class represent a single offer"""
    offer_id = db.Column(db.String(40), nullable=False, primary_key=True)
    offer_type = db.Column(db.String(40), nullable=False, primary_key=False)
    offer_type_image_url = db.Column(db.String(100), nullable=False, primary_key=False)
    offer_domain = db.Column(db.String(40), nullable=False, primary_key=False)
    is_active = db.Column(db.Boolean, unique=False, default=False)
    title = db.Column(db.String(80), nullable=False, primary_key=False)
    desc = db.Column(db.String(500), nullable=False, primary_key=False)
    image_url = db.Column(db.String(100), nullable=False, primary_key=False)
    kin_cost = db.Column(db.Integer(), nullable=False, primary_key=False)
    address = db.Column(db.String(80), nullable=False, primary_key=False)
    update_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now())
    provider_data = db.Column(db.JSON)
    min_client_version_ios = db.Column(db.String(80), nullable=True, primary_key=False)
    min_client_version_android = db.Column(db.String(80), nullable=True, primary_key=False)
    unavailable_reason = None
    cannot_buy_reason = None

    def __repr__(self):
        return '<offer_id: %s, offer_type: %s, title: %s, desc: %s, kin_cost: %s, is_active: %s, min_client_version_ios: %s, min_client_version_android: %s>' % \
               (self.offer_id, self.offer_type, self.title, self.desc, self.kin_cost, self.is_active, self.min_client_version_ios, self.min_client_version_android)


def list_all_offer_data():
    """returns a dict of all the offers"""
    response = {}
    offers = Offer.query.order_by(Offer.offer_id).all()
    for offer in offers:
        response[offer.offer_id] = {'id': offer.offer_id, 'offer_type': offer.offer_type, 'title': offer.title}
    return response


def offer_to_json(offer):
    """converts the given offer object to a json-representation"""
    if not offer:
        return {}
    # build the json object:
    offer_json = {}
    offer_json['id'] = offer.offer_id
    offer_json['type'] = offer.offer_type
    offer_json['type_image_url'] = offer.offer_type_image_url
    offer_json['domain'] = offer.offer_domain
    offer_json['title'] = offer.title
    offer_json['desc'] = offer.desc
    offer_json['image_url'] = offer.image_url
    offer_json['price'] = offer.kin_cost
    offer_json['address'] = offer.address
    offer_json['provider'] = offer.provider_data
    offer_json['unavailable_reason'] = offer.unavailable_reason
    offer_json['cannot_buy_reason'] = offer.cannot_buy_reason
    return offer_json


def set_offer_active(offer_id, is_active):
    """enable/disable offer by offer_id"""
    offer = Offer.query.filter_by(offer_id=offer_id).first()
    if not offer:
        raise InvalidUsage('no such offer_id')

    offer.is_active = is_active
    db.session.add(offer)
    db.session.commit()
    return True


def add_offer(offer_json, set_active=False):
    """adds an offer to the db"""

    skip_image_test = offer_json.get('skip_image_test', False)
    if not skip_image_test:
        print('testing accessibility of offer urls (this can take a few seconds...)')
        # ensure all urls are accessible:
        fail_flag = False
        image_url = offer_json['type_image_url']
        if image_url:
            if not test_image(image_url):
                log.error('offer type_image_url - %s - could not be verified' % image_url)
                fail_flag = True

        image_url = offer_json['image_url']
        if image_url:
            if not test_image(image_url):
                log.error('offer image_url - %s - could not be verified' % image_url)
                fail_flag = True

        image_url = offer_json['provider']['image_url']
        if image_url:
            if not test_image(image_url):
                log.error('offer provider image_url - %s - could not be verified' % image_url)
                fail_flag = True

        if fail_flag:
            log.error('could not ensure accessibility of all urls. refusing to add offer')
            return False
        log.info('done testing accessibility of offer urls')

    try:
        offer = Offer()
        offer.offer_id = str(offer_json['id'])
        offer.offer_type = offer_json['type']
        offer.offer_type_image_url = offer_json['type_image_url']
        offer.offer_domain = offer_json['domain']
        offer.title = offer_json['title']
        offer.desc = offer_json['desc']
        offer.image_url = offer_json['image_url']
        offer.kin_cost = int(offer_json['price'])
        offer.address = offer_json['address']
        offer.provider_data = offer_json['provider']
        offer.min_client_version_ios = offer_json.get('min_client_version_ios', None)  # optional, can be None
        offer.min_client_version_android = offer_json.get('min_client_version_android', None)  # optional, can be None

        db.session.add(offer)
        db.session.commit()
    except Exception as e:
        print(e)
        log.error('cant add offer to db with id %s' % offer_json['id'])
        return False
    else:
        if set_active:
            set_offer_active(str(offer_json['id']), True)
        return True


def get_cost_and_address(offer_id):
    """return the kin cost and address associated with this offer"""
    offer = Offer.query.filter_by(offer_id=offer_id).first()
    if not offer.is_active:
        raise InvalidUsage('offer is not active')
    return offer.kin_cost, offer.address


def get_offers_for_user(user_id):
    """return the list of offers with there status for this user"""
    import time
    from distutils.version import LooseVersion
    from .user import get_user_app_data, get_user_os_type, get_user_inapp_balance
    from .good import goods_avilable
    from .transaction import get_offers_bought_in_days_ago

    # for debugging
    start = time.time()

    all_offers = Offer.query.filter_by(is_active=True).order_by(Offer.kin_cost.asc()).all()
    tx_infos = get_offers_bought_in_days_ago(user_id, config.TIME_RANGE_IN_DAYS)
    user_balance = get_user_inapp_balance(user_id)
    end = time.time()

    log.info("## GETTING OFFERS MID PTIME: %s", end - start)
    # filter out offers with no goods
    redeemable_offers = []
    for offer in all_offers:
        counter = len([tx for tx in tx_infos if tx['offer_id'] == offer.offer_id])
        
        if not goods_avilable(offer.offer_id):
            offer.unavailable_reason = 'Sold out Check back again soon'
        elif user_balance < offer.kin_cost:
            offer.cannot_buy_reason = 'Sorry, You can only buy goods with Kin earned from Kinit.'
        elif counter >= config.GIFTCARDS_PER_TIME_RANGE:
            offer.unavailable_reason = 'You’ve reached the maximum number of this gift card for this month'
        redeemable_offers.append(offer)        
    
    # filter out p2p for users with client versions that do not support it
    filter_p2p = False

    if not config.P2P_TRANSFERS_ENABLED:
        log.info('filter out p2p for all users as per config flag')
        filter_p2p = True
    else:
        # TODO remove this chunk of code when we go live on prod2.
        try:
            os_type = get_user_os_type(user_id)
        except Exception as e:
            # race condition - the user's OS hasn't been written into the db yet, so
            # just dont show the p2p offer. yes its an ugly patch
            log.error('filter p2p - cant get user os_type. e:%s' % e)
            filter_p2p = True
        else:
            # try to get the user's version:
            client_version = get_user_app_data(user_id).app_ver
            if os_type == OS_IOS and LooseVersion(client_version) < LooseVersion('0.11.0'):
                log.info('filter out p2p for old ios client %s' % client_version)
                filter_p2p = True
            elif os_type == OS_ANDROID and LooseVersion(client_version) < LooseVersion('0.7.4'):
                log.info('filter out p2p for old android client version %s' % client_version)
                filter_p2p = True

    # filter the first p2p item if one exists:
    if filter_p2p:
        item_to_remove = None

        # find the first item to remove
        for offer in redeemable_offers:
            if offer.offer_type == 'p2p':
                item_to_remove = offer

        # ...and remove it
        if item_to_remove is not None:
            redeemable_offers.remove(item_to_remove)

    # filter offers by the min_client_version fields
    # 1. get the client's version and os:
    try:
        client_version = get_user_app_data(user_id).app_ver
        os_type = get_user_os_type(user_id)
        offers_to_remove = []
    except Exception as e:
        log.error('cant get app_ver or os_type - not filtering offers')
    else:
        # 2. collect offers that are not allowed for this os/app_ver
        for offer in redeemable_offers:
            if os_type == OS_ANDROID:
                if offer.unavailable_reason is not None and LooseVersion(client_version) < LooseVersion(config.GIFTCARDS_ANDROID_VERSION):
                    # client does not support text on offers, remove it
                    offers_to_remove.append(offer)
                elif not offer.min_client_version_android:
                    # no minimum set, so dont remove
                    continue
                elif LooseVersion(offer.min_client_version_android) > LooseVersion(client_version):
                    offers_to_remove.append(offer)
            else:  # ios
                if offer.unavailable_reason is not None and LooseVersion(client_version) < LooseVersion(config.GIFTCARDS_IOS_VERSION):
                    # client does not support text on offers, remove it
                    offers_to_remove.append(offer)
                elif not offer.min_client_version_ios:
                    # no minimum set, so dont remove
                    continue
                elif LooseVersion(offer.min_client_version_ios) > LooseVersion(client_version):
                    offers_to_remove.append(offer)
        # 3. clean up offers list
        for offer in offers_to_remove:
            #print('get_offers_for_user: removing offer_id %s' % offer.offer_id)
            redeemable_offers.remove(offer)


    # the client shows offers by the order they are listed, so make sure p2p (if it exists) is first
    redeemable_offers = sorted(redeemable_offers, key=lambda k: k.offer_type != 'p2p', reverse=False)

    # convert to json
    offers_json_array = []
    for offer in redeemable_offers:
        offers_json_array.append(offer_to_json(offer))

    end = time.time()
    log.info('offers for user %s: %s. \n ## GETTING OFFERS PTIME: %s' % (user_id, [o['id'] for o in offers_json_array], end - start))
    return offers_json_array


def get_offer_details(offer_id):
    """return a dict with some of the given offerid's metadata"""
    offer = Offer.query.filter_by(offer_id=offer_id).first()
    if not offer:
        log.error('cant find offer with id %s. using default text' % offer_id)
        return {'title': 'unknown offer', 'desc': '', 'provider': {}}

    return {'title': offer.title, 'desc': offer.desc, 'provider': offer.provider_data}
