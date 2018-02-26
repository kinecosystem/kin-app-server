from uuid import uuid4
import arrow

from kinappserver import db, config, stellar
from kinappserver.utils import InternalError
from sqlalchemy_utils import UUIDType, ArrowType

from .offer import get_cost_and_address
from .transaction import create_tx
from .order import Order

class Good(db.Model):
    '''the Good class represent a single goods (as in, the singular of Goods). 

       Goods are pre-populated into the db and have a limited number of instances.
       Each good instance is a row in the db.  
    '''
    sid = db.Column(db.Integer(), db.Sequence('sid', start=1, increment=1), primary_key=True)
    offer_id = db.Column('offer_id', db.String(40), db.ForeignKey("offer.offer_id"), primary_key=False, nullable=False, unique=False)
    order_id = db.Column('order_id', db.String(config.ORDER_ID_LENGTH), db.ForeignKey("order.order_id"), primary_key=False, nullable=True, unique=True)
    value = db.Column(db.JSON(), nullable=False)
    good_type = db.Column(db.String(40), primary_key=False, nullable=False)
    tx_hash = db.Column('tx_hash', db.String(100), db.ForeignKey("transaction.tx_hash"), primary_key=False, nullable=True)
    created_at = db.Column(ArrowType)
    updated_at = db.Column(db.DateTime(timezone=False), server_default=db.func.now(), onupdate=db.func.now())

    def __repr__(self):
        return '<sid: %s, offer_id: %s, order_id: %s, type: %s, promised: %s, tx_hash: %s, created_at: %s, updated_at: %s>' % (self.sid, self.offer_id, self.order_id, self.good_type, self.promised, self.tx_hash, self.created_at, self.updated_at)


def create_good(offer_id, good_type, value):
    '''creates a new good-instance for the given offer_id with the given value'''
    try:
        now = arrow.utcnow()
        good = Good()
        good.offer_id = offer_id
        good.good_type = good_type
        good.value = value
        good.created_at = now
        db.session.add(good)
        db.session.commit()
    except Exception as e:
        print('failed to create a new good')
        print(e)
        raise InternalError('failed to create a new good')
    else:
        return True


def list_all_goods():
    '''returns a dict of all the goods'''
    response = {}
    goods = Good.query.order_by(Good.sid).all()
    for good in goods:
        response[good.sid] = {'sid': good.sid, 'offer_id': good.offer_id, 'order_id': good.order_id, 'type': good.good_type, 'created_at': good.created_at, 'tx_hash': good.tx_hash}
    return response


def count_available_goods(offer_id):
    '''return the number of available goods for the given offer_id'''
    results = db.engine.execute("select count(sid) from good where good.offer_id=\'%s\' and good.order_id is NULL;" % str(offer_id))
    return(results.fetchone()[0])


def allocate_good(offer_id, order_id):
    '''find and allocate a good to an order. returns True on success'''

    #TODO ensure the order hasn't expired?

    try:
        good = db.session.query(Good).filter(Good.offer_id==offer_id).filter(Good.order_id==None).with_for_update().first()
        good.order_id = order_id
        db.session.add(good)
        db.session.commit()
        db.session.flush()
    except Exception as e:
        print('failed to allocate good with order_id: %s' % order_id)
        print(e)
        db.session.rollback()
        return False
    else:
        return True


def release_good(order_id):
    '''release a previously allocated good back to the pool. returns True on success'''
    try:
        good = db.session.query(Good).filter(Good.order_id==order_id).with_for_update().one()
        good.order_id = None
        db.session.add(good)
        db.session.commit()
    except Exception as e:
        print('failed to release good with order_id: %s' % order_id)
        print(e)
        db.session.rollback()
        return False
    else:
        return True

def release_unclaimed_goods():
    '''traverse the list of goods and release those associated with expired goods
        
       this should be called by cron every minute or so
    '''
    print('releasing unclaimed goods...')
    goods = db.session.query(Good).filter(Good.tx_hash is None).filter(Good.order_id is not None).all()
    for good in goods:
        if has_expired(good.order_id):
            release_good(good.order_id)

    print('releasing unclaimed goods...done')
