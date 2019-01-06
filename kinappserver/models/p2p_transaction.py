"""The model for the Kin App Server p2p transaction."""

import logging as log
from sqlalchemy_utils import UUIDType
from sqlalchemy import desc
import arrow

from kinappserver import db


class P2PTransaction(db.Model):
    """
    p2p transactions: between users
    """
    sender_user_id = db.Column('sender_user_id', UUIDType(binary=False), db.ForeignKey("user.user_id"), unique=False, nullable=False)
    receiver_user_id = db.Column('receiver_user_id', UUIDType(binary=False), db.ForeignKey("user.user_id"), unique=False, nullable=True)
    receiver_app_sid = db.Column('receiver_app_sid', db.Integer, db.ForeignKey("app_discovery.sid"), unique=False, nullable=True)
    tx_hash = db.Column(db.String(100), nullable=False, primary_key=True)
    amount = db.Column(db.Integer(), nullable=False, primary_key=False)
    sender_address = db.Column(db.String(60), db.ForeignKey("user.public_address"), nullable=False, unique=False)
    receiver_address = db.Column('receiver_address', db.String(60), nullable=False, unique=False)
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


def create_p2p_tx(tx_hash, sender_user_id, receiver_user_id, sender_address, receiver_address, amount, receiver_app_sid):
    """create a p2p transaction object and store in the db."""
    try:
        tx = P2PTransaction()
        tx.tx_hash = tx_hash
        tx.sender_user_id = sender_user_id
        tx.receiver_user_id = receiver_user_id
        tx.receiver_app_sid = receiver_app_sid
        tx.amount = int(amount)
        tx.sender_address = sender_address
        tx.receiver_address = receiver_address
        db.session.add(tx)
        db.session.commit()
    except Exception as e:
        log.error('cant add p2ptx to db with id %s. e:%s' % (tx_hash, e))


def format_p2p_tx_dict(tx_hash, amount, format_for_receiver):
    """create a dict with the tx data as it would be sent/returned to the client"""
    tx_dict = {
         'title': 'Kin from a friend' if format_for_receiver else 'Kin to a friend',
         'description': 'a friend sent you %sKIN' % amount,
         'provider': {'image_url': 'https://s3.amazonaws.com/kinapp-static/brand_img/poll_logo_kin.png', 'name': 'friend'},
         'type': 'p2p',
         'tx_hash': tx_hash,
         'amount': amount,
         'client_received': format_for_receiver,
         'tx_info': {'memo': 'na', 'task_id': '-1'},
         'date': arrow.utcnow().timestamp}
    return tx_dict


def add_app2app_tx(tx_hash, sender_id, destination_app_sid, amount, destination_address):
    """create a new app2app tx based on reports from the client
    return True/False and (if successful, a dict with the tx data
    """
    try:
        from kinappserver.models import get_userid_by_address, get_address_by_userid
        sender_address = get_address_by_userid(sender_id)
        if None in (sender_id, sender_address):
            log.error('cant create p2p tx - cant get one of the following: destination_app_sid: %s, sender_address: %s' % (destination_app_sid, sender_address))
            return False
        create_p2p_tx(tx_hash, sender_id, None, sender_address, destination_address, amount, destination_app_sid)
        
    except Exception as e:
        log.error('failed to create a new p2p tx. exception: %s' % e)
        return False, None
    else:
        return True, format_p2p_tx_dict(tx_hash, amount, False)

def add_p2p_tx(tx_hash, sender_user_id, receiver_address, amount):
    """create a new p2p tx based on reports from the client
    return True/False and (if successful, a dict with the tx data
    """
    try:
        from kinappserver.models import get_userid_by_address, get_address_by_userid
        receiver_user_id = get_userid_by_address(receiver_address)
        sender_address = get_address_by_userid(sender_user_id)
        if None in (receiver_user_id, sender_address):
            log.error('cant create p2p tx - cant get one of the following: receiver_user_id: %s, sender_address: %s' % (receiver_user_id, sender_address))
            return False
        create_p2p_tx(tx_hash, sender_user_id, receiver_user_id, sender_address, receiver_address, amount, None)
        # create a json object that mimics the one in the /transactions api

        log.info('sending p2p-tx push message to user_id %s' % receiver_user_id)
        from ..push import send_p2p_push
        send_p2p_push(receiver_user_id, amount, format_p2p_tx_dict(tx_hash, amount, True))
    except Exception as e:
        log.error('failed to create a new p2p tx. exception: %s' % e)
        return False, None
    else:
        return True, format_p2p_tx_dict(tx_hash, amount, False)

