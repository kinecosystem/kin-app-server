
import datetime
from kinappserver import db


class ACL(db.Model):
    """ACL for the server"""
    ip_addr = db.Column(db.String(40), primary_key=True)
    name = db.Column(db.String(40), primary_key=False)

    def __repr__(self):
        return '<ip: %s, name: %s>' % (self.ip_addr, self.name)


def is_in_acl(ip_addr):
    """replaces the old token with a new one"""
    card = ACL.query.filter_by(ip_addr=ip_addr).first()
    if not card:
        return False
    return True
