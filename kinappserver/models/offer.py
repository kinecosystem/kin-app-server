from kinappserver import db, config, utils
from kinappserver.utils import InvalidUsage, test_image, OS_ANDROID, OS_IOS
import logging as log
from datetime import datetime, timedelta

class Offer(db.Model):
    """the Offer class represent a single offer"""
    offer_id = db.Column(db.String(40), nullable=False, primary_key=True)
    offer_type = db.Column(db.String(40), nullable=False, primary_key=False)
    offer_type_image_url = db.Column(db.String(100), nullable=False, primary_key=False)
    offer_domain = db.Column(db.String(40), nullable=False, primary_key=False)
    is_active = db.Column(db.Boolean, unique=False, default=False)
    title = db.Column(db.String(80), nullable=False, primary_key=False)
    desc = db.Column(db.String(1000), nullable=False, primary_key=False)
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

    all_offers = Offer.query.filter_by(is_active=True).order_by(Offer.kin_cost.asc()).all()

    start = time.time()
    locked_offers_ids = get_locked_offers(user_id, config.OFFER_LIMIT_TIME_RANGE)
    end = time.time()
    log.info("## locked_offers_ids MID PTIME: %s", end - start)

    start = time.time()
    user_balance = get_user_inapp_balance(user_id)
    end = time.time()
    log.info("## GETTING user_balance MID PTIME: %s", end - start)

    # filter out offers with no goods
    available_offers = []
    unavailable_offers = []
    for offer in all_offers:
        if offer.offer_type == 'p2p':
            # we no longer support p2p as an offer type
            # we may want to add it again in the future, in which case we will have
            # to handle it being on top of the list + appear only for versions that support it.
            continue
        elif not goods_avilable(offer.offer_id):
            offer.unavailable_reason = 'Sold out\nCheck back again soon'
            unavailable_offers.append(offer)
        elif str(offer.offer_id) in locked_offers_ids:
            offer.unavailable_reason = 'You’ve reached the maximum number of this gift card for this month'
            unavailable_offers.append(offer)
        elif user_balance < offer.kin_cost:
            offer.cannot_buy_reason = 'Sorry, You can only buy goods with Kin earned from Kinit.'
            available_offers.append(offer)
        else:
            available_offers.append(offer)


    # filter offers by the min_client_version fields
    # 1. get the client's version and os:
    try:
        client_version = get_user_app_data(user_id).app_ver
        os_type = get_user_os_type(user_id)
    except Exception as e:
        redeemable_offers = available_offers
        log.error('cant get app_ver or os_type - not filtering offers')
    else:
        # 2. collect offers that are not allowed for this os/app_ver
        if os_type == OS_ANDROID and LooseVersion(client_version) < LooseVersion(
                config.OFFER_RATE_LIMIT_MIN_ANDROID_VERSION):
            # client does not support text on offers, remove it
            redeemable_offers = available_offers
        elif os_type == OS_IOS and LooseVersion(client_version) < LooseVersion(config.OFFER_RATE_LIMIT_MIN_IOS_VERSION):
            redeemable_offers = available_offers
        else:
            redeemable_offers = available_offers + unavailable_offers

        for offer in redeemable_offers:
            if os_type == OS_ANDROID and offer.min_client_version_android:
                if LooseVersion(offer.min_client_version_android) > LooseVersion(client_version):
                    redeemable_offers.remove(offer)
            elif os_type == OS_IOS and offer.min_client_version_ios:
                if LooseVersion(offer.min_client_version_ios) > LooseVersion(client_version):
                    redeemable_offers.remove(offer)

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


def set_locked_offers(user_id, days):
    """ scan the db for offers bought in the last {days} and update USER_LOCKED_OFFERS_REDIS_KEY"""
    log.info("user_id: %s - not cache - set_locked_offers! " % user_id)
    date_days_from_now = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    offers_bought_in_time_range = db.engine.execute("select tx_info, update_at from public.transaction "
                                                    "where user_id='%s' and incoming_tx=true "
                                                    "and update_at > ('%s'::date);" % (user_id, date_days_from_now)).fetchall()
    # extract data from result
    offers_bought_in_time_range_ids = [item[0]['offer_id'] for item in offers_bought_in_time_range]
    offers_bought_in_time_range_timestamp = [item[1].strftime('%m/%d/%Y') for item in offers_bought_in_time_range]
    # build locked_offers_ids array
    locked_offers_ids = dict(zip(offers_bought_in_time_range_ids, offers_bought_in_time_range_timestamp))
    # write to cache
    utils.write_json_to_cache(config.USER_LOCKED_OFFERS_REDIS_KEY % user_id, locked_offers_ids)
    log.info("user_id: %s - locked_offers_ids: %s" % (user_id, locked_offers_ids))
    return locked_offers_ids.keys()


def get_locked_offers(user_id, days):
    """return list of locked offers"""
    # first check if we have a cached result.
    locked_offers_ids = utils.read_json_from_cache(config.USER_LOCKED_OFFERS_REDIS_KEY % user_id)
    if locked_offers_ids is not None:
        log.info("user_id: %s - get_locked_offers - cache found!" % user_id)
        # we need to check if offer's timestamp is old enough to be unlocked
        locked_offers_ids = {k: v for k, v in locked_offers_ids.items() if datetime.strptime(v, '%m/%d/%Y') + timedelta(days=days) > datetime.now()}
        # update cache
        utils.write_json_to_cache(config.USER_LOCKED_OFFERS_REDIS_KEY % user_id, locked_offers_ids)
        log.info("user_id: %s - locked_offers_ids: %s" % (user_id, locked_offers_ids))
        return locked_offers_ids.keys()
    else:
        # cache not available, query the db store and return the result
        return set_locked_offers(user_id, days)
