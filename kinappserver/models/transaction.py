'''The model for the Kin App Server.'''
import datetime

from sqlalchemy_utils import UUIDType

from kinappserver import db


class Transaction(db.Model):
    '''
    kin transactions
    '''
    user_id = db.Column('user_id', UUIDType(binary=False), db.ForeignKey("user.user_id"), primary_key=False, nullable=False)
    tx_hash = db.Column(db.String(100), nullable=False, primary_key=True)
    amount = db.Column(db.Integer(), nullable=False, primary_key=False)
    incoming_tx = db.Column(db.Boolean, unique=False, default=False) # are the moneys coming or going
    remote_address = db.Column(db.String(100), nullable=False, primary_key=False)
    tx_info = db.Column(db.JSON)
    update_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now())

    def __repr__(self):
        return '<tx_hash: %s, user_id: %s, amount: %s, remote_address: %s, incoming_tx: %s, tx_info: %s,  update_at: %s>' % (self.tx_hash, self.user_id, self.amount, self.remote_address, self.incoming_tx, self.tx_info, self.update_at)


def list_all_transactions():
    '''returns a dict of all the tasks'''
    response = {}
    txs = Transaction.query.order_by(Transaction.update_at).all()
    for tx in txs:
        response[tx.tx_hash] = {'tx_hash': tx.tx_hash, 'user_id': tx.user_id, 'remote_address': tx.remote_address, 'incoming_tx': tx.incoming_tx, 'amount': tx.amount, 'tx_info': tx.tx_info, 'update_at': tx.update_at}
    return response


def create_tx(tx_hash, user_id, remote_address, incoming_tx, amount, tx_info):
    try:
        tx = Transaction()
        tx.tx_hash = tx_hash
        tx.user_id = user_id
        tx.amount = int(amount)
        tx.incoming_tx = bool(incoming_tx)
        tx.remote_address = remote_address
        tx.tx_info = tx_info
        db.session.add(tx)
        db.session.commit()
    except Exception as e:
        print('cant add tx to db with id %s' % tx_hash)


def count_transactions_by_minutes_ago(minutes_ago=1):
    """return the number of failed txs since minutes_ago"""
    time_minutes_ago = datetime.datetime.now() - datetime.timedelta(minutes = minutes_ago)
    return len(Transaction.query.filter(Transaction.update_at>=time_minutes_ago).all())
