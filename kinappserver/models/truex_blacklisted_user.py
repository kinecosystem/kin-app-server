from kinappserver import db
from sqlalchemy_utils import UUIDType


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
