from kinappserver import db
from sqlalchemy_utils import UUIDType
from kinappserver.utils import InvalidUsage
import logging as log


class TruexBlacklistedUser(db.Model):
    """list of users that are manually blacklisted from getting truex tasks. not expecting a lof of these"""
    user_id = db.Column('user_id', UUIDType(binary=False), db.ForeignKey("user.user_id"), primary_key=True, nullable=False)

    def __repr__(self):
        return '<user_id: %s>' % self.user_id


def is_user_id_blacklisted_for_truex(user_id):
    """returns true if this user_id is blacklisted for truex"""
    user = TruexBlacklistedUser.query.filter_by(user_id=user_id).first()
    if not user:
        return False
    return True


def block_user_from_truex_tasks(user_id):
    """add a user to the truex blocked list"""
    tbuser = TruexBlacklistedUser()
    tbuser.user_id = user_id
    db.session.add(tbuser)
    db.session.commit()


def unblock_user_from_truex_tasks(user_id):
    """remove a user from the truex list"""
    tbuser = TruexBlacklistedUser.query.filter_by(user_id=user_id).first()
    if not tbuser:
        raise InvalidUsage('cant find blocked user with user_id %s' % user_id)
    db.session.delete(tbuser)
    db.session.commit()
