'''The model for the Kin App Server.'''
from uuid import uuid4
import datetime
import redis_lock
from sqlalchemy_utils import UUIDType, ArrowType
import arrow
import json

from kinappserver import db, config, app, stellar
from kinappserver.utils import InvalidUsage, InternalError, send_apns, send_gcm


class Transaction(db.Model):
    '''
    kin transactions
    '''
    user_id = db.Column('user_id', UUIDType(binary=False), db.ForeignKey("user.user_id"), primary_key=True, nullable=False)
    tx_hash = db.Column(db.String(100), nullable=False, primary_key=True)
    amount = db.Column(db.Integer(), nullable=False, primary_key=False)
    update_at = db.Column(db.DateTime(timezone=False), server_default=db.func.now(), onupdate=db.func.now())

    def __repr__(self):
        return '<tx_hash: %s, user_id: %s, amount: %s, desc: %s, update_at: %s>' % (self.tx_hash, self.user_id, self.amount, self.update_at)


def list_all_transactions():
    '''returns a dict of all the tasks'''
    response = {}
    txs = Transaction.query.order_by(Transaction.update_at).all()
    for tx in txs:
        response[tx.tx_hash] = {'tx_hash': tx.tx_hash, 'user_id': tx.user_id, 'amount': tx.amount, 'update_at': tx.update_at}
    return response


def create_tx(tx_hash, user_id, amount):
    try:
        tx = Transaction()
        tx.tx_hash = tx_hash
        tx.user_id = user_id
        tx.amount = int(amount)
        db.session.add(tx)
        db.session.commit()
    except Exception as e:
        print(e)
        print('cant add tx to db with id %s' % tx_hash)


