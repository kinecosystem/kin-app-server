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
    created_at = db.Column(ArrowType, default=arrow.utcnow())

    def __repr__(self):
        return '<order_id: %s, offer_id: %s, user_id: %s, created_at: %s>' % (self.order_id, self.offer_id, self.user_id, self.created_at)

def create_order(user_id, offer_id):
    '''creates a new order'''

    # dont let users create too many simultaneous orders
    if len(get_orders_for_user(user_id)) >= config.MAX_SIMULTANEOUS_ORDERS_PER_USER:
        return None

    order_id = uuid4()

    try:
        order = Order()
        order.order_id = order_id
        order.user_id = user_id
        order.offer_id = offer_id
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
        response[order.order_id] = {'order_id': order.order_id, 'offer_id': order.offer_id, 'user_id': order.user_id, 'created_at': order.created_at}
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
    active_orders = []
    now = arrow.utcnow()
    for order in orders:
        # filter out old orders
        if (now - order.created_at).total_seconds() <= config.ORDER_EXPIRATION_SECS:
            active_orders.append(order)
    return active_orders

    #TODO cleanup old, un-used orders