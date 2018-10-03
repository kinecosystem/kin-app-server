
from kinappserver import db, app


class BlacklistedEncPhoneNumber(db.Model):
    """the PhoneBackupHints model holds (for each userid) the sid of the questions selected by the user for the recent-most backup.
    """
    enc_phone_number = db.Column('enc_phone_number', db.String(200), primary_key=True, nullable=False) # cant be a foreign key because its not unique in user.
    added_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())

    def __repr__(self):
        return '<enc_phone_number: %s, added_at: %s>' % (self.enc_phone_number, self.added_at)


def is_phone_number_blacklisted(phone_number):
    encrypted_phone_number = app.encryption.encrypt(phone_number)
    return is_enc_phone_number_blacklisted(encrypted_phone_number)


def blacklist_phone_by_user_id(user_id):
    from .user import get_enc_phone_number_by_user_id
    enc_phone_number = get_enc_phone_number_by_user_id(user_id)
    if not enc_phone_number:
        print('blacklist_phone_by_user_id: no enc_number')
        return False

    return blacklist_enc_phone_number(enc_phone_number)


def blacklist_phone_number(phone_number):
    encrypted_phone_number = app.encryption.encrypt(phone_number)
    if is_enc_phone_number_blacklisted(encrypted_phone_number):
        # already blacklisted
        return True
    # else:
    return blacklist_enc_phone_number(encrypted_phone_number)


def blacklist_enc_phone_number(enc_phone_number):
    if enc_phone_number in (None, ''):
        print('cant blacklist phone number:%s' % enc_phone_number)
        return False

    blacklisted_enc_phone_number = BlacklistedEncPhoneNumber()
    try:
        blacklisted_enc_phone_number.enc_phone_number = enc_phone_number
        db.session.add(blacklisted_enc_phone_number)
        db.session.commit()
    except Exception as e:
        print('failed to store blacklisted_enc_phone_number with enc_phone_number: %s' % enc_phone_number)
        print(e)
        return False
    else:
        return True


def is_enc_phone_number_blacklisted(enc_phone_number):
    """return the user backup hints object for the given enc_phone_number or throws exception"""
    blacklisted_enc_phone_number = BlacklistedEncPhoneNumber.query.filter_by(enc_phone_number=enc_phone_number).first()
    if not blacklisted_enc_phone_number:
        return False
    return True


def is_userid_blacklisted(user_id):
    """determines whether the given user_id is blacklisted"""
    count = db.engine.execute("""select count(*) from public.user, public.blacklisted_enc_phone_number where public.user.enc_phone_number=public.blacklisted_enc_phone_number.enc_phone_number and public.user.user_id='%s';""" % user_id).scalar()
    if count == 0:
        return False
    return True
