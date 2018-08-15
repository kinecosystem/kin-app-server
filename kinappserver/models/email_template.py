
import datetime
from kinappserver import db


EMAIL_TEMPLATE_BACKUP_NAG_1 = 'backup_nag_1'


class EmailTemplate(db.Model):
    """email templates for various uses"""
    template_type = db.Column(db.String(100), primary_key=True)
    title = db.Column(db.String(200), primary_key=False)
    body = db.Column(db.String(100000), primary_key=False)
    sent_from = db.Column(db.String(100), primary_key=False)

    def __repr__(self):
        return '<template_type: %s, title: %s, body: %s, sent_from: %s>' % (self.template_type, self.title, self.body
                                                                            , self.sent_from)


def get_email_template_by_type(template_type):
    """returns a dict with the template data"""
    try:
        temp = EmailTemplate.query.filter_by(template_type=template_type).first()
        return {'template_type': temp.template_type, 'title': temp.title, 'body': temp.body, 'sent_from': temp.sent_from}
    except Exception as e:
        print('failed to get email template %s. e:%s' % (template_type, e))
        return None
