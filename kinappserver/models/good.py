import arrow

from kinappserver import db
from kinappserver.utils import InternalError
from sqlalchemy_utils import UUIDType, ArrowType

from .offer import Offer

class Good(db.Model):
    """the Good class represent a single goods (as in, the singular of Goods).

       Goods are pre-populated into the db and have a limited number of instances.
       Each good instance is a row in the db.  
    """
    sid = db.Column(db.Integer(), db.Sequence('sid', start=1, increment=1), primary_key=True)
    offer_id = db.Column('offer_id', db.String(40), db.ForeignKey("offer.offer_id"), primary_key=False, nullable=False, unique=False)
    #  order_id = db.Column('order_id', db.String(config.ORDER_ID_LENGTH), db.ForeignKey("order.order_id"), primary_key=False, nullable=True, unique=True)
    # TODO the order_id should be a foreign key, but that implies that orders are created BEFORE the good is allocated. this
    # needs to be improved somehow.
    order_id = db.Column(db.String(40), primary_key=False, nullable=True, unique=True)
    value = db.Column(db.JSON(), nullable=False)
    good_type = db.Column(db.String(40), primary_key=False, nullable=False)
    tx_hash = db.Column('tx_hash', db.String(100), db.ForeignKey("transaction.tx_hash"), primary_key=False, nullable=True)
    created_at = db.Column(ArrowType)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now())
    extra_info = db.Column(db.JSON) # for additional, schemaless date

    def __repr__(self):
        return '<sid: %s, offer_id: %s, order_id: %s, type: %s, tx_hash: %s, created_at: %s,' \
               ' updated_at: %s>' % (self.sid, self.offer_id, self.order_id, self.good_type, self.tx_hash, self.created_at, self.updated_at)


def create_good(offer_id, good_type, value, extra_info=None):
    """creates a new good-instance for the given offer_id with the given value"""
    if not offer_id:
        print('refusing to create good with offer_id: %s' % offer_id)
        return False

    if does_code_exist(value):
        print('refusing to create good with code: %s as it already exists in the db' % value)
        return False

    try:
        now = arrow.utcnow()
        good = Good()
        good.offer_id = offer_id
        good.good_type = good_type
        good.value = value
        good.created_at = now
        if extra_info:
            good.extra_info = extra_info
        db.session.add(good)
        db.session.commit()
    except Exception as e:
        print('failed to create a new good')
        print(e)
        raise InternalError('failed to create a new good')
    else:
        return True


def list_all_goods():
    """returns a dict of all the goods"""
    response = {}
    goods = Good.query.order_by(Good.sid).all()
    for good in goods:
        response[good.sid] = {'sid': good.sid, 'offer_id': good.offer_id, 'order_id': good.order_id, 'type': good.good_type, 'created_at': good.created_at, 'tx_hash': good.tx_hash}
    return response


def list_inventory():
    """for each offer_id, generate a dict with the number of total goods and unallocated ones"""
    res = {}
    offers = Offer.query.order_by(Offer.offer_id).all()
    for offer in offers:
        res[offer.offer_id] = {'total': count_total_goods(offer.offer_id), 'unallocated': count_available_goods(offer.offer_id)}
    return res


def count_total_goods(offer_id):
    offer_id = int(offer_id)  # sanitize input
    results = db.engine.execute("select count(sid) from good where good.offer_id=\'%s\';" % str(offer_id))  # safe
    return(results.fetchone()[0])    


def count_available_goods(offer_id):
    """return the number of available goods for the given offer_id"""
    offer_id = int(offer_id)  # sanitize input
    results = db.engine.execute("select count(sid) from good where good.offer_id=\'%s\' and good.order_id is NULL;" % str(offer_id))  # safe
    return(results.fetchone()[0])


def allocate_good(offer_id, order_id):
    """find and allocate a good to an order.
       returns the good sid on success or None if no goods are available"""

    #TODO ensure the order hasn't expired?

    try:
        # lock the line until the commit is complete
        good = db.session.query(Good).filter(Good.offer_id==offer_id).filter(Good.order_id == None).with_for_update().first()
        if not good:
            return None
        good.order_id = order_id
        db.session.add(good)
        db.session.commit()
        db.session.flush()
    except Exception as e:
        db.session.rollback()
        print('failed to allocate good with order_id: %s. exception: %s' % (order_id,e))
        raise InternalError('cant allocate good for order_id: %s' % order_id)
    else:
        return good.sid


def finalize_good(order_id, tx_hash):
    """mark this good as used-up. return True on success"""
    good_res = {}
    try:
        # lock the line until the commit is complete
        good = db.session.query(Good).filter(Good.order_id == order_id).with_for_update().one()
        if not good:
            # should never happen
            raise InternalError('cant finalize good: good with order_id: %s not found' % order_id)
        else:
            good_res['type'] = good.good_type
            good_res['value'] = good.value
            good.tx_hash = tx_hash
            db.session.add(good)
            db.session.commit()
            db.session.flush()
    except Exception as e:
        db.session.rollback()
        print('failed to finalize good with order_id: %s. exception: %s' % (order_id,e))
        raise InternalError('cant finalize good for order_id: %s' % order_id)
    else:
        return True, good_res


def release_good(order_id):
    """release a previously allocated good back to the pool. returns True on success"""
    try:
        # lock the line until the commit is compelete
        good = db.session.query(Good).filter(Good.order_id == order_id).with_for_update().one()
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
    """traverse the list of goods and release those associated with expired goods
        
       this should be called by cron every minute or so
    """
    print('releasing unclaimed goods...')
    released = 0
    goods = db.session.query(Good).filter(Good.tx_hash == None).filter(Good.order_id != None).all()
    for good in goods:
        from .order import has_expired # don't move me to prevent cyclical deps
        if has_expired(good.order_id):
            release_good(good.order_id)
            released = released + 1

    print('released %s goods' % released)
    return released


def goods_avilable(offer_id):
    """returns true if the given offer_id has avilable goods"""
    return db.session.query(Good).filter(Good.offer_id == offer_id).filter(Good.order_id == None).count()>0


def get_redeemed_items(tx_hases):
    """returns an array of redeemed goods by the given tx_hashes array"""
    redeemed = []

    if not tx_hases:
        return redeemed

    for good in db.session.query(Good).filter(Good.tx_hash.in_(tx_hases)).order_by(Good.updated_at.desc()).all():
            redeemed.append({'date': arrow.get(good.updated_at).timestamp, 'value': good.value, 'type': good.good_type, 'offer_id': good.offer_id})
    return redeemed


def does_code_exist(code):
    """return true if the given code is already present in the db"""
    results = db.engine.execute("select * from good where cast(value as varchar)='\"%s\"' limit 1;" % code)
    results = results.fetchall()
    return (results != [])


def get_user_goods_report(user_id):
    """return a json with all the interesting user-goods stuff"""
    print('getting user goods report for %s' % user_id)
    user_goods_report = {}
    try:
        from .transaction import Transaction
        for good in db.session.query(Good, Transaction).filter(Transaction.user_id == user_id).filter(Good.tx_hash == Transaction.tx_hash):
            user_goods_report[good[0].sid] = {'user_id': good[1].user_id, 'offer_id': good[0].offer_id, 'tx_hash': good[0].tx_hash, 'created_at': str(good[0].created_at), 'value': good[0].value, 'amount': good[1].amount}
    except Exception as e:
        print('caught exception in get_user_goods_report:%s' % e)
    return user_goods_report
