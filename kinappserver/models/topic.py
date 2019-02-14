from kinappserver import db
from kinappserver.utils import test_image, InvalidUsage
import logging as log
from .user import UserAppData


class Topic(db.Model):
    """the Task class represent a single task"""
    sid = db.Column(db.Integer(), db.Sequence(
        'topic_sid', start=1, increment=1), primary_key=True)
    name = db.Column(db.String(80), nullable=False,
                     primary_key=False, unique=True)
    icon_url = db.Column(db.String(200), nullable=False, primary_key=False)

    def __repr__(self):
        return '<sid: %s, name:%s, icon_url:%s>' % (str(self.sid), self.name, self.icon_url)


def add_topic(new_topic):
    try:
        topic = Topic()
        topic.name = new_topic['name']
        topic.icon_url = new_topic['icon_url']
        db.session.add(topic)
        db.session.commit()
        return True
    except Exception as e:
        log.error('failed to create a new topic. e:%s' % e)
        raise InvalidUsage('failed to add topic')


def list_all_topics():
    """returns a dict of all the topics"""
    response = {}
    topics = Topic.query.all()
    for topic in topics:
        response[topic.sid] = {'name': topic.name, 'icon_url': topic.icon_url}

    return response


def get_user_topics(user_id):
    """returns topics ids of the user"""
    user_app_data = UserAppData.query.filter_by(user_id=user_id).one()
    return user_app_data.topics


def set_user_topics(user_id, topics):
    """set user's topics """
    from kinappserver.models.user import get_user_app_data
    try:
        user_app_data = get_user_app_data(user_id)
        user_app_data.topics = topics
        db.session.add(user_app_data)
        db.session.commit()
        return True
    except Exception as e:
        log.error('failed to updated user topics. e:%s' % e)
        raise InvalidUsage('failed to add topic')
