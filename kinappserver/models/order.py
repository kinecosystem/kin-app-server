from uuid import uuid4
import datetime
import json
import arrow

from kinappserver import db, config, app
from kinappserver.utils import InvalidUsage, InternalError
from sqlalchemy_utils import UUIDType, ArrowType

class Order(db.Model):
    '''the Order class represent a single offer'''
    order_id = db.Column(UUIDType(binary=False), primary_key=True, nullable=False)
    offer_id = db.Column('offer_id', db.String(40) , db.ForeignKey("offer.offer_id"), primary_key=False, nullable=False)
    user_id = db.Column('user_id', UUIDType(binary=False), db.ForeignKey("user.user_id"), primary_key=False, nullable=False)
    kin_amount = db.Column(db.Integer(), nullable=False, primary_key=False)
    address = db.Column(db.String(80), nullable=False, primary_key=False)
    created_at = db.Column(ArrowType, default=arrow.utcnow())

    def __repr__(self):
        return '<order_id: %s, offer_id: %s, user_id: %s, kin_amount: %s, created_at: %s>' % (self.order_id, self.offer_id, self.user_id, self.kin_amount, self.created_at)

def create_order(user_id, offer_id):
    '''creates a new order'''

    # dont let users create too many simultaneous orders
    if len(get_orders_for_user(user_id)) >= config.MAX_SIMULTANEOUS_ORDERS_PER_USER:
        return None

    # get offer cost
    from .offer import get_cost_and_address
    kin_amount, address = get_cost_and_address(offer_id)
    if None in (kin_amount, address):
        return None


    order_id = uuid4()

    try:
        order = Order()
        order.order_id = order_id
        order.user_id = user_id
        order.offer_id = offer_id
        order.kin_amount = kin_amount
        order.address = address
        db.session.add(order)
        db.session.commit()
    except Exception as e:
        print('failed to create a new order with id %s' % order_id)
        raise InternalError('failed to create a new order')
    else:
        return str(order_id)

def list_all_order_data():
    '''returns a dict of all the orders'''
    response = {}
    orders = Order.query.order_by(Order.order_id).all()
    for order in orders:
        response[order.order_id] = {'order_id': order.order_id, 'offer_id': order.offer_id, 'user_id': order.user_id, 'kin_amount': order.kin_amount, 'created_at': order.created_at}
    return response


def delete_order(order_id):
    '''delete an order'''
    try:
        deleted_count = Order.query.filter_by(order_id=order_id).delete()
        if deleted_count != 1:
            # should never happen
            raise InternalError('deleted %s orders while trying to delete order-id:%s' % (deleted_count, order_id))
    except Exception as e:
        raise InternalError('failed to delete an order with id %s' % order_id)


def get_orders_for_user(user_id):
    '''return the list of active orders for this user'''
    orders = Order.query.filter_by(user_id=user_id).all()
    active_orders = {}
    now = arrow.utcnow()
    for order in orders:
        # filter out old orders
        if (now - order.created_at).total_seconds() <= config.ORDER_EXPIRATION_SECS:
            active_orders[order.order_id] = order
    return active_orders

    #TODO cleanup old, un-used orders

def process_order(user_id, order_id, tx_hash):
    '''release the goods to the user, now that they've been payed for'''
    # is there such an (active) order?
    order = get_orders_for_user(user_id).get(order_id, None)
    if order is None:
        return False, None

    # check the tx-hash: verify the memo, address and cost
    from stellar import verify_tx
    if not (verify_tx(tx_hash, order.kin_amount, order.dst_address, order.order_id)):
        print('cant verify tx-hash (%s) with expected_cost %s, expected_address %s, and expected_memo %s' % (tx_hash, order.kin_amount, order.dst_address, order.order_id))
        return False, None

    # docuemnt the tx in the db
    from .transaction import create_tx
    create_tx(tx_hash, user_id, order.dst_address, True, order.kin_amount, {'offer_id':order.offer_id})

    # get the goods
    goods = [{type:'code', 'code': 'abcdefg'}]

    # delete the order
    try:
        delete_order(order_id)
    except Exception as e:
        print('failed to delete order %s' % order_id)

    return True, goods
