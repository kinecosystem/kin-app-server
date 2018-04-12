"""The model for the Kin App Server."""
import datetime

from sqlalchemy_utils import UUIDType

from kinappserver import db, stellar


class Transaction(db.Model):
    """
    kin transactions
    """
    user_id = db.Column('user_id', UUIDType(binary=False), db.ForeignKey("user.user_id"), primary_key=False, nullable=False)
    tx_hash = db.Column(db.String(100), nullable=False, primary_key=True)
    amount = db.Column(db.Integer(), nullable=False, primary_key=False)
    incoming_tx = db.Column(db.Boolean, unique=False, default=False)  # are the moneys coming or going
    remote_address = db.Column(db.String(100), nullable=False, primary_key=False)
    tx_info = db.Column(db.JSON)
    update_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now())

    def __repr__(self):
        return '<tx_hash: %s, user_id: %s, amount: %s, remote_address: %s, incoming_tx: %s, tx_info: %s,  update_at: %s>' % (self.tx_hash, self.user_id, self.amount, self.remote_address, self.incoming_tx, self.tx_info, self.update_at)


def list_user_transactions(user_id, max_txs=None):
    """returns all txs by this user - or the last x tx if max_txs was passed"""
    txs = Transaction.query.filter(Transaction.user_id == user_id).order_by(Transaction.update_at.asc()).all()
    return txs[:max_txs] if max_txs and max_txs > len(txs) else txs


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
    time_minutes_ago = datetime.datetime.now() - datetime.timedelta(minutes=minutes_ago)
    return len(Transaction.query.filter(Transaction.update_at >= time_minutes_ago).all())


def expected_user_kin_balance(user_id):
    """this function calculates the expected kin balance of the given user based on his past txs"""
    expected_balance = 0
    user_txs = Transaction.query.filter(Transaction.user_id == user_id).all()
    for tx in user_txs:
        if tx.incoming_tx:
            expected_balance = expected_balance - tx.amount
        else:
            expected_balance = expected_balance + tx.amount
    return expected_balance


def get_current_user_kin_balance(user_id):
    """get the current kin balance for the user with the given user_id."""
    # determine the user's public address from pre-existing outgoing txs
    user_outgoing_txs = Transaction.query.filter(Transaction.user_id == user_id).filter(Transaction.incoming_tx==False).all()
    if len(user_outgoing_txs) == 0:
        return 0  # user should not have any Kins
    else:
        return stellar.get_kin_balance(user_outgoing_txs[0].remote_address)

