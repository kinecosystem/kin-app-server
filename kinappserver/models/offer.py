from uuid import uuid4
import datetime
import json

from kinappserver import db, config, app, stellar
from kinappserver.utils import InvalidUsage, InternalError


class Offer(db.Model):
    '''the Offer class represent a single offer'''
    offer_id = db.Column(db.String(40), nullable=False, primary_key=True)
    offer_type = db.Column(db.String(40), nullable=False, primary_key=True)
    offer_domain = db.Column(db.String(40), nullable=False, primary_key=True)
    title = db.Column(db.String(80), nullable=False, primary_key=False)
    desc = db.Column(db.String(80), nullable=False, primary_key=False)
    image_url = db.Column(db.String(80), nullable=False, primary_key=False)
    kin_cost = db.Column(db.Integer(), nullable=False, primary_key=False)
    address = db.Column(db.String(80), nullable=False, primary_key=False)
    update_at = db.Column(db.DateTime(timezone=False), server_default=db.func.now(), onupdate=db.func.now())

    def __repr__(self):
        return '<offer_id: %s, offer_type: %s, title: %s, desc: %s, kin_cost: %s>' % (self.offer_id, self.offer_type, self.title, self.desc, self.kin_cost)


def list_all_offer_data():
    '''returns a dict of all the offers'''
    response = {}
    offers = Offer.query.order_by(Offer.offer_id).all()
    for offer in offers:
        response[offer.offer_id] = {'offer_id': offer.offer_id, 'offer_type': offer.offer_type, 'title': offer.title}
    return response


def get_offer_by_id(offer_id):
    '''return a json representing the offer'''
    offer = offer.query.filter_by(offer_id=offer_id).first()
    if offer is None:
        return None
    # build the json object:
    offer_json = {}
    offer_json['id'] = offer_id
    offer_json['type'] = offer.offer_type
    offer_json['domain'] = offer.offer_domain
    offer_json['title'] = offer.title
    offer_json['desc'] = offer.desc
    offer_json['image_url'] = offer.image_url
    offer_json['price'] = offer.kin_cost
    offer_json['address'] = offer.address
    offer_json['provider'] = offer.provider_data
    return offer_json


def add_offer(offer_json):
    try:
        offer = Offer()
        offer.offer_id = offer_json['offer_id']
        offer.offer_type = offer_json['type']
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
        print('cant add offer to db with id %s' % offer_json['offer_id'])
        return False
    else:
        return True


def get_cost_for_offer(offer_id):
    '''return the kin cost associated with this offer'''
    offer = Offer.query.filter_by(offer_id=offer_id).first()
    if not offer:
        raise InternalError('no such offer_id')
    return offer.kin_cost