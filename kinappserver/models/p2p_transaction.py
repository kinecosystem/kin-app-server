"""The model for the Kin App Server p2p transaction."""

from sqlalchemy_utils import UUIDType
from sqlalchemy import desc


from kinappserver import db


class P2PTransaction(db.Model):
    """
    p2p transactions: between users
    """
    sender_user_id = db.Column('sender_user_id', UUIDType(binary=False), db.ForeignKey("user.user_id"), unique=False, nullable=False)
    receiver_user_id = db.Column('receiver_user_id', UUIDType(binary=False), db.ForeignKey("user.user_id"), unique=False, nullable=False)
    tx_hash = db.Column(db.String(100), nullable=False, primary_key=True)
    amount = db.Column(db.Integer(), nullable=False, primary_key=False)
    sender_address = db.Column(db.String(60), db.ForeignKey("user.public_address"), nullable=False, unique=False)
    receiver_address = db.Column(db.String(60), db.ForeignKey("user.public_address"), nullable=False, unique=False)
    update_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now())

    def __repr__(self):
        return '<p2ptx_hash: %s, sender_user_id: %s, receiver_user_id: %s, ' \
               'amount: %s, sender_address: %s, receiver_address: %s, update_at: %s>' % (self.tx_hash, self.sender_user_id, self.receiver_user_id,
                                                                                                                                                    self.amount, self.sender_address, self.receiver_address, self.update_at)


def list_p2p_transactions_for_user_id(user_id, max_txs=None):
    """returns all p2p txs by this user - or the last x tx if max_txs was passed"""
    sender_txs = P2PTransaction.query.filter(P2PTransaction.sender_user_id == user_id).order_by(desc(P2PTransaction.update_at)).all()
    receiver_txs = P2PTransaction.query.filter(P2PTransaction.receiver_user_id == user_id).order_by(desc(P2PTransaction.update_at)).all()
    # join and trim the amount of txs
    txs = receiver_txs + sender_txs
    txs = txs[:max_txs] if max_txs and max_txs > len(txs) else txs
    return txs


def create_p2p_tx(tx_hash, sender_user_id, receiver_user_id, sender_address, receiver_address, amount):
    """create a p2p transaction object and store in the db."""
    try:
        tx = P2PTransaction()
        tx.tx_hash = tx_hash
        tx.sender_user_id = sender_user_id
        tx.receiver_user_id = receiver_user_id
        tx.amount = int(amount)
        tx.sender_address = sender_address
        tx.receiver_address = receiver_address
        db.session.add(tx)
        db.session.commit()
    except Exception as e:
        print('cant add p2ptx to db with id %s. e:%s' % (tx_hash, e))


def add_p2p_tx(tx_hash, sender_user_id, receiver_address, amount):
    """create a new p2p tx based on reports from the client"""
    try:
        from kinappserver.models import get_userid_by_address, get_address_by_userid
        receiver_user_id = get_userid_by_address(receiver_address)
        sender_address = get_address_by_userid(sender_user_id)
        if None in (receiver_user_id, sender_address):
            print('cant create p2p tx - cant get one of the following: receiver_user_id: %s, sender_address: %s' % (receiver_user_id, sender_address))
            return False
        create_p2p_tx(tx_hash, sender_user_id, receiver_user_id, sender_address, receiver_address, amount)
    except Exception as e:
        print('failed to create a new p2p tx. exception: %s' % e)
        return False
    else:
        return True
