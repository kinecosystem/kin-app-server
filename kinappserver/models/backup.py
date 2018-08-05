import arrow

from kinappserver import db
from kinappserver.utils import InternalError
from kinappserver.utils import InvalidUsage
from sqlalchemy_utils import UUIDType

from .offer import Offer


class BackupQuestion(db.Model):
    """the BackupQuestion model represents a single backup question. these are essentially hardcoded into the db.
    """
    sid = db.Column(db.Integer(), db.Sequence('sid', start=1, increment=1), primary_key=True)
    question_text = db.Column('question_text', db.String(300), unique=True)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now())

    def __repr__(self):
        return '<sid: %s, question_text: %s' \
               ' updated_at: %s>' % (self.sid, self.question_text, self.updated_at)


def generate_backup_questions_dict():
    """returns a dict of all the questions with their sid"""
    response = {}
    questions = BackupQuestion.query.order_by(BackupQuestion.sid).all()
    for q in questions:
        response[q.sid] = {'text': q.question_text}
    return response


class UserBackupHints(db.Model):
    """the UserBackupHints model holds (for each userid) the sid of the questions selected by the user for the recent-most backup.
    """
    user_id = db.Column('user_id', UUIDType(binary=False), db.ForeignKey("user.user_id"), primary_key=True, nullable=False)
    hints = db.Column(db.JSON(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now())

    def __repr__(self):
        return '<user_id: %s, hints: %s' \
               ' updated_at: %s>' % (self.user_id, self.hints, self.updated_at)


def store_backup_hints(user_id, hints):
    """stores given hints for the given userid in the db. overwrite if already existing"""
    try:
        ubh = get_user_backup_hints(user_id)
        print('user backup hints already exist for user_id %s, updating data' % user_id)
    except Exception as e:
        ubh = UserBackupHints()
    try:
        ubh.hints = hints
        ubh.user_id = user_id
        db.session.add(ubh)
        db.session.commit()
    except Exception as e:
        print('failed to store user backup hints with id: %s' % user_id)
        print(e)
        raise InternalError('failed to store user backup hints with id: %s' % user_id)
    else:
        return True


def get_user_backup_hints(user_id):
    """return the user backup hints object for the given user_id or throws exception"""
    ubh = UserBackupHints.query.filter_by(user_id=user_id).first()
    if not ubh:
        raise InvalidUsage('no such user_id')
    return ubh


def get_backup_hints(user_id):
    """return the user's back up hints"""
    try:
        return get_user_backup_hints(user_id).hints
    except Exception as e:
        return None
