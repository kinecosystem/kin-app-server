from kinappserver import db
from kinappserver.utils import InvalidUsage, test_image


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

    def __repr__(self):
        return '<offer_id: %s, offer_type: %s, title: %s, desc: %s, kin_cost: %s, is_active: %s>' % \
               (self.offer_id, self.offer_type, self.title, self.desc, self.kin_cost, self.is_active)


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
                print('offer type_image_url - %s - could not be verified' % image_url)
                fail_flag = True

        image_url = offer_json['image_url']
        if image_url:
            if not test_image(image_url):
                print('offer image_url - %s - could not be verified' % image_url)
                fail_flag = True

        image_url = offer_json['provider']['image_url']
        if image_url:
            if not test_image(image_url):
                print('offer provider image_url - %s - could not be verified' % image_url)
                fail_flag = True

        if fail_flag:
            print('could not ensure accessibility of all urls. refusing to add offer')
            return False
        print('done testing accessibility of offer urls')

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
        db.session.add(offer)
        db.session.commit()
    except Exception as e:
        print(e)
        print('cant add offer to db with id %s' % offer_json['id'])
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
    """return the list of active offers for this user"""
    offers = Offer.query.filter_by(is_active=True).order_by(Offer.kin_cost.asc()).all()
    
    # filter out offers with no goods
    redeemable_offers = []
    from .good import goods_avilable
    for offer in offers:
        if goods_avilable(offer.offer_id):
            redeemable_offers.append(offer)
        else:
            print('filtering out un-redeemable offer-id: %s' % offer.offer_id)

    offers_json_array = []
    for offer in redeemable_offers:
        offers_json_array.append(offer_to_json(offer))
    print('offers for user %s: %s' % (user_id, offers_json_array))
    return offers_json_array


def get_offer_details(offer_id):
    """return a dict with some of the given offerid's metadata"""
    offer = Offer.query.filter_by(offer_id=offer_id).first()
    if not offer:
        raise InvalidUsage('no offer with id %s exists' % offer_id)
    return {'title': offer.title, 'desc': offer.desc, 'provider': offer.provider_data}
