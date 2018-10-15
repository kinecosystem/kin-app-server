"""The model for the Kin App Server."""
import datetime

from sqlalchemy_utils import UUIDType
from sqlalchemy import desc
import arrow

from kinappserver import db, stellar


class Transaction(db.Model):
    """
    kin transactions: from and to the server
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
    txs = Transaction.query.filter(Transaction.user_id == user_id).order_by(desc(Transaction.update_at)).all()
    # trim the amount of txs
    txs = txs[:max_txs] if max_txs and max_txs > len(txs) else txs
    return txs


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
    else:
        print('created tx with txinfo: %s' % tx.tx_info)

def count_transactions_by_minutes_ago(minutes_ago=1):
    """return the number of failed txs since minutes_ago"""
    time_minutes_ago = datetime.datetime.now() - datetime.timedelta(minutes=minutes_ago)
    return len(Transaction.query.filter(Transaction.update_at >= time_minutes_ago).all())


def get_memo_for_user_ids(user_ids, task_id):
    """"return the memo of the transaction or None for the given list of user_ids and task_id

    this function tries to find the memo of for the tx that relates to the given task_id and
    any of the given user_ids. only one memo is returned along with its associated user_id. or (None, None).
    """
    user_ids = "\',\'".join(user_ids)
    task_id = int(task_id)  # sanitize input
    prep_stat = "select (user_id, tx_info->>'memo') from public.transaction where user_id in ('%s') and tx_info->>'task_id' LIKE '%s' fetch first 1 rows only" % (user_ids, task_id)
    results = db.engine.execute(prep_stat)
    row = results.fetchone()
    if row is None:
        return None, None
    else:
        comma_index = row[0].find(',')  # ugh. its actually a concatenated string
        memo = row[0][comma_index+1:]
        user_id = row[0][:comma_index-1]
        return memo, user_id


def update_tx_ts(tx_hash, timestamp):
    tx = Transaction.query.filter_by(tx_hash=tx_hash).first()
    tx.update_at = timestamp
    db.session.add(tx)
    db.session.commit()


def get_user_tx_report(user_id):
    """return a json with all the interesting user-tx stuff"""
    print('getting user tx report for %s' % user_id)
    user_tx_report = {}
    try:
        txs = list_user_transactions(user_id)
        for tx in txs:
            user_tx_report[tx.tx_hash] = {'amount': tx.amount, 'in': tx.incoming_tx, 'date': tx.update_at, 'info': tx.tx_info, 'address': tx.remote_address}

    except Exception as e:
        print('caught exception in get_user_tx_report:%s' % e)
    return user_tx_report


def get_tx_totals():
    totals = {'to_public': 0, 'from_public': 0}
    prep_stat = 'select sum(amount) from transaction where incoming_tx=false;'
    totals['to_public'] = db.engine.execute(prep_stat).scalar()
    prep_stat = 'select sum(amount) from transaction where incoming_tx=true;'
    totals['from_public'] = db.engine.execute(prep_stat).scalar()

    return totals
