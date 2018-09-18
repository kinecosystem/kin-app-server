
from kinappserver import db, app
from kinappserver.utils import InternalError
from kinappserver.utils import InvalidUsage , increment_metric
MINIMAL_BACKUP_HINTS = 2
import arrow

class BackupQuestion(db.Model):
    """the BackupQuestion model represents a single backup question. these are essentially hardcoded into the db.
    """
    sid = db.Column(db.Integer(), db.Sequence('sid', start=1, increment=1), primary_key=True)
    question_text = db.Column('question_text', db.String(300), unique=True)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now())

    def __repr__(self):
        return '<sid: %s, question_text: %s' \
               ' updated_at: %s>' % (self.sid, self.question_text, self.updated_at)


def generate_backup_questions_list():
    """returns a list of all the questions with their sid"""
    response = []
    questions = BackupQuestion.query.order_by(BackupQuestion.sid).all()
    for q in questions:
        response.append({'id': q.sid, 'text': q.question_text})
    return response


class PhoneBackupHints(db.Model):
    """the PhoneBackupHints model holds (for each userid) the sid of the questions selected by the user for the recent-most backup.
    """
    enc_phone_number = db.Column('enc_phone_number', db.String(200), primary_key=True, nullable=False) # cant be a foreign key because its not unique in user.
    hints = db.Column(db.JSON(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now())
    previous_hints = db.Column(db.JSON(), nullable=True)

    def __repr__(self):
        return '<user_id: %s, hints: %s' \
               ' updated_at: %s>' % (self.enc_phone_number, self.hints, self.updated_at)


def store_backup_hints(user_id, hints):
    """stores given hints for the given userid in the db. overwrite if already existing"""
    from .user import get_enc_phone_number_by_user_id

    # sanity: require min number of hints:
    if len(hints) < MINIMAL_BACKUP_HINTS:
        print('wont store less than %s hints. aborting' % MINIMAL_BACKUP_HINTS)
        return False

    # sanity: ensure the hints make sense
    all_hints_sids = [item['id'] for item in generate_backup_questions_list()]
    for item in hints:
        if item not in all_hints_sids:
            print('cant find given hint %s in the pool of hints. aborting' % item)
            return False

    enc_phone_number = get_enc_phone_number_by_user_id(user_id)
    if enc_phone_number in (None, ''):
        print('cant store hints for user_id %s - bad enc_phone_number' % user_id)
        return False
    try:
        ubh = get_user_backup_hints_by_enc_phone(enc_phone_number)
        print('user backup hints already exist for enc_phone_number %s, updating data.' % enc_phone_number)
    except Exception as e:
        ubh = PhoneBackupHints()
    try:
        # save previous hints
        if ubh.hints is not None:
            if ubh.previous_hints is None:
                ubh.previous_hints = [{'date': arrow.get(ubh.updated_at).timestamp, 'hints': ubh.hints}]
            else:
                ubh.previous_hints.append({'date': arrow.get(ubh.updated_at).timestamp, 'hints': ubh.hints})
            # turns out sqlalchemy cant detect json updates, and requires manual flagging:
            # https://stackoverflow.com/questions/30088089/sqlalchemy-json-typedecorator-not-saving-correctly-issues-with-session-commit/34339963#34339963
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(ubh, "previous_hints")

        ubh.hints = hints
        ubh.enc_phone_number = enc_phone_number
        db.session.add(ubh)
        db.session.commit()
    except Exception as e:
        print('failed to store user backup hints with enc_phone_number: %s' % enc_phone_number)
        print(e)
        return False
    else:
        return True


def get_user_backup_hints_by_enc_phone(enc_phone_number):
    """return the user backup hints object for the given enc_phone_number or throws exception"""
    ubh = PhoneBackupHints.query.filter_by(enc_phone_number=enc_phone_number).first()
    if not ubh:
        raise InvalidUsage('no such enc_phone_number')
    return ubh


def get_backup_hints(user_id):
    """return the user's phone number backup hints by user_id"""
    try:
        from .user import get_enc_phone_number_by_user_id
        enc_phone_number = get_enc_phone_number_by_user_id(user_id)
        if enc_phone_number in (None, ''):
            print('cant get hints for user_id %s - bad enc_phone_number' % user_id)
            return []

        return get_user_backup_hints_by_enc_phone(enc_phone_number).hints
    except Exception as e:
        return []
