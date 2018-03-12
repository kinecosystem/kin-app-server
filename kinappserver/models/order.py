from uuid import uuid4
import arrow

from kinappserver import db, config, stellar, utils
from kinappserver.utils import InternalError
from sqlalchemy_utils import UUIDType, ArrowType

from .offer import get_cost_and_address
from .transaction import create_tx
from .good import allocate_good, finalize_good

class Order(db.Model):
    '''the Order class represent a single order. 

       orders are generated when a client wishes to buy an offer.
       orders are time-limited and expire after a while.
    '''
    order_id = db.Column(db.String(config.ORDER_ID_LENGTH), primary_key=True, nullable=False)
    offer_id = db.Column('offer_id', db.String(40), db.ForeignKey("offer.offer_id"), primary_key=False, nullable=False)
    user_id = db.Column('user_id', UUIDType(binary=False), db.ForeignKey("user.user_id"), primary_key=False, nullable=False)
    kin_amount = db.Column(db.Integer(), nullable=False, primary_key=False)
    address = db.Column(db.String(80), nullable=False, primary_key=False)
    created_at = db.Column(ArrowType)

    def __repr__(self):
        return '<order_id: %s, offer_id: %s, user_id: %s, kin_amount: %s, created_at: %s>' % (self.order_id, self.offer_id, self.user_id, self.kin_amount, self.created_at)

def has_expired(order_id):
    '''determines whether an order has expired. this feteches from db.'''
    now = arrow.utcnow()
    order = Order.query.filter_by(order_id=order_id).one()
    if (now - order.created_at).total_seconds() <= config.ORDER_EXPIRATION_SECS:
        return False
    return True

def create_order(user_id, offer_id):
    '''creates a new order and allocate the goods for it'''

    # dont let users create too many simultaneous orders
    if len(get_orders_for_user(user_id)) >= int(config.MAX_SIMULTANEOUS_ORDERS_PER_USER):
        print('rejecting users oferr - too many orders')
        return None, utils.ERROR_ORDERS_COOLDOWN

    # get offer cost
    kin_amount, address = get_cost_and_address(offer_id)
    if None in (kin_amount, address):
        # should never happen
        raise InternalError('failed to get offer details')

    # make up an order_id
    order_id = str(uuid4())[:config.ORDER_ID_LENGTH] #max you can fit inside a stellar memo

    # attempt to allocate a good for this order
    if not allocate_good(offer_id, order_id):
        # no good available to allocate. bummer
        print('out of goods for offer_id: %s' % offer_id)
        return None, utils.ERROR_NO_GOODS

    try:
        order = Order()
        order.order_id = order_id
        order.user_id = user_id
        order.offer_id = offer_id
        order.kin_amount = kin_amount
        order.address = address
        order.created_at = arrow.utcnow()
        db.session.add(order)
        db.session.commit()
    except Exception as e:
        print('failed to create a new order with id %s' % order_id)
        raise InternalError('failed to create a new order')
    else:
        return str(order_id), None


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
    '''return a dict of active orders for this user

       returns a dict with the order-id as its key and the order object as value
    '''
    orders = Order.query.filter_by(user_id=user_id).all()
    active_orders = {}
    now = arrow.utcnow()
    for order in orders:
        # filter out expired orders
        if (now - order.created_at).total_seconds() <= config.ORDER_EXPIRATION_SECS:
            active_orders[str(order.order_id)] = order
    return active_orders

    #TODO cleanup old, un-used orders


def get_order_by_order_id(order_id):
    '''returns the order object from the db, if it exists and is active'''
    if order_id is None:
        return None

    order = Order.query.filter_by(order_id=order_id).first()
    if not order:
        print('no order with id: %s' % order_id)
        return None

    # ensure the order isn't stale
    if (arrow.utcnow() - order.created_at).total_seconds() > config.ORDER_EXPIRATION_SECS:
        print('order %s expired' % order_id)
        return None
    return order


def process_order(user_id, tx_hash):
    '''release the goods to the user, provided that they've been payed for'''
    # extract the tx_data from the blockchain
    goods  = []
    res, tx_data = stellar.extract_tx_payment_data(tx_hash)
    if not res:
        print('could not extract tx_data for tx_hash: %s' % tx_hash)
        return False, None

    # get the order from the db using the memo in the tx
    order = get_order_by_order_id(tx_data['memo'])
    if not order:
        print('cant match tx order_id to any active orders')
        return False, None

    # ensure the tx matches the order
    if tx_data['to_address'] != order.address:
        print('tx address does not match offer address')
        return False, None
    if int(tx_data['amount']) != order.kin_amount:
        print('tx amount does not match offer amount')
        return False, None

    # tx matched! docuemnt the tx in the db with a tx object
    create_tx(tx_hash, user_id, order.address, True, order.kin_amount, {'offer_id': str(order.offer_id)})

    # get the allocated goods
    res, good = finalize_good(order.order_id, tx_hash)
    if res:
        goods.append(good)
    else:
        print('failed to finalize the good for tx_hash: %s' % tx_hash)

    # delete the order
    try:
        delete_order(order.order_id)
    except Exception as e:
        print('failed to delete order %s' % order.order_id)

    return True, goods
