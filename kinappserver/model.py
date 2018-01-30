'''The model for the Kin App Server.'''
from uuid import uuid4
import datetime
import redis_lock
from sqlalchemy_utils import UUIDType

from kinappserver import db, config, app
from kinappserver.utils import InvalidUsage

class User(db.Model):
    '''
    the user model
    '''
    sid = db.Column(db.Integer(), db.Sequence('sid', start=1, increment=1), primary_key=False)
    user_id = db.Column(UUIDType(binary=False), primary_key=True, nullable=False)
    os_type = db.Column(db.String(10), primary_key=False, nullable=False)
    device_model = db.Column(db.String(40), primary_key=False, nullable=False)
    push_token = db.Column(db.String(80), primary_key=False, nullable=True)
    time_zone = db.Column(db.String(10), primary_key=False, nullable=False)
    device_id = db.Column(db.String(40), primary_key=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=False), server_default=db.func.now())


    def __repr__(self):
        return '<sid: %s, user_id: %s, os_type: %s, device_model: %s, push_token: %s, time_zone: %s, device_id: %s>' % (self.sid, self.user_id, self.os_type, self.device_model, self.push_token, self.time_zone, self.device_id)

def get_user(user_id):
    user = User.query.filter_by(user_id=user_id).first()
    if not user:
        raise InvalidUsage('no such user_id')
    return user

def user_exists(user_id):
    user = User.query.filter_by(user_id=user_id).first()
    return True if user else False

def create_user(user_id, os_type, device_model, push_token, time_zone, device_id):
    '''create a new user and commit to the database. should only fail if the user_id is duplicate'''
    if user_exists(user_id):
            raise InvalidUsage('refusing to create user. user_id %s already exists' % user_id)
    user = User()
    user.user_id = user_id
    user.os_type = os_type
    user.device_model = device_model
    user.push_token = push_token
    user.time_zone = time_zone
    user.device_id = device_id
    db.session.add(user)
    db.session.commit()

    user_app_data = UserAppData()
    user_app_data.user_id = user_id
    user_app_data.answered_quests = []
    db.session.add(user_app_data)
    db.session.commit()

def update_user_token(user_id, push_token):
    '''updates the user's token with a new one'''
    user = get_user(user_id)
    print('user:%s', user)
    user.push_token = push_token
    db.session.add(user)
    db.session.commit()

def list_all_users():
    '''returns a dict of all the whitelisted users and their PAs (if available)'''
    response = {}
    users = User.query.order_by(User.user_id).all()
    for user in users:
        response[user.user_id] = {'sid': user.sid, 'os': user.os_type, 'push_token': user.push_token, 'timezone': user.time_zone, 'device_id': user.device_id, 'device_model': user.device_model}
    return response


class UserAppData(db.Model):
    '''
    the user app data model tracks the version of the app installed @ the client
    '''
    user_id = db.Column('user_id', UUIDType(binary=False), db.ForeignKey("user.user_id"), primary_key=True, nullable=False)
    app_ver = db.Column(db.String(40), primary_key=False, nullable=True)
    update_at = db.Column(db.DateTime(timezone=False), server_default=db.func.now(), onupdate=db.func.now())
    answered_quests = db.Column(db.JSON)

def update_user_app_version(user_id, app_ver):
    ''''''
    try:
        userAppData = UserAppData.query.filter_by(user_id=user_id).first()
        userAppData.app_ver = app_ver
        db.session.add(userAppData)
        db.session.commit()
    except Exception as e:
        print(e)
        raise InvalidUsage('cant set user app data')

def list_all_users_app_data():
    '''returns a dict of all the user-app-data'''
    response = {}
    users = UserAppData.query.order_by(UserAppData.user_id).all()
    for user in users:
        response[user.user_id] = {'user_id': user.user_id,  'app_ver': user.app_ver, 'update': user.update_at, 'answered_quests': user.answered_quests}
    return response

def get_user_app_data(user_id):
    user_app_data = UserAppData.query.filter_by(user_id=user_id).first()
    if not user_app_data:
        raise InvalidUsage('no such user_id')
    return user_app_data

class UserQuestAnswers(db.Model):
    '''
    the user quest answers
    '''
    user_id = db.Column('user_id', UUIDType(binary=False), db.ForeignKey("user.user_id"), primary_key=False, nullable=False)
    quest_id = db.Column(db.String(40), nullable=False, primary_key=True)
    answers = db.Column(db.JSON)
    update_at = db.Column(db.DateTime(timezone=False), server_default=db.func.now(), onupdate=db.func.now())


def store_answers(user_id, quest_id, answers):
    '''store the answers provided by the user'''
    try:
        userQuestAnswers = UserQuestAnswers()
        userQuestAnswers.user_id = user_id
        userQuestAnswers.quest_id = quest_id
        userQuestAnswers.answers = answers
        db.session.add(userQuestAnswers)
        db.session.commit()
    except Exception as e:
        raise InvalidUsage('cant set user quest answers data')

def list_all_users_answers_data():
    '''returns a dict of all the user-quest-data'''
    response = {}
    user_answers = UserQuestAnswers.query.order_by(UserQuestAnswers.user_id).all()
    for user in user_answers:
        response[user.user_id] = {'user_id': user.user_id,  'quest_id': user.quest_id, 'answers': user.answers}
    return response

class Questionnaire(db.Model):
    '''the Questionnaire class represent a single questionnaire'''
    quest_id = db.Column(db.String(40), nullable=False, primary_key=True)
    title = db.Column(db.String(80), nullable=False, primary_key=False)
    desc = db.Column(db.String(80), nullable=False, primary_key=False)
    kin_reward = db.Column(db.Integer(), nullable=False, primary_key=False)
    min_to_complete = db.Column(db.Integer(), nullable=False, primary_key=False)
    author_data = db.Column(db.JSON)
    tags = db.Column(db.JSON)
    questions = db.Column(db.JSON)
    update_at = db.Column(db.DateTime(timezone=False), server_default=db.func.now(), onupdate=db.func.now())


    def __repr__(self):
        return '<quest_id: %s, title: %s, desc: %s, kin_reward: %s, min_to_complete: %s>' % (self.quest_id, self.title, self.desc, self.kin_reward, self.min_to_complete)

def list_all_questionnaires_data():
    '''returns a dict of all the questionnaires'''
    response = {}
    quests = Questionnaire.query.order_by(Questionnaire.quest_id).all()
    for quest in quests:
        response[quest.quest_id] = {'quest_id': quest.quest_id,  'title': quest.title}
    return response

def get_quest_by_id(quest_id):
    '''return a json representing the questionnaire'''
    quest = Questionnaire.query.filter_by(quest_id=quest_id).first()
    if quest is None:
        return None
    # build the json object:
    quest_json = {}
    quest_json['id'] = quest_id
    quest_json['title'] = quest.title
    quest_json['desc'] = quest.desc
    quest_json['kin_reward'] = quest.kin_reward
    quest_json['min_to_complete'] = quest.min_to_complete
    quest_json['author'] = quest.author_data
    quest_json['tags'] = quest.tags
    quest_json['questions'] = quest.questions
    return quest_json

def add_questionnare(quest_id, quest_json):
    try:
        quest = Questionnaire()
        quest.quest_id = quest_id
        quest.title = quest_json['title']
        quest.desc = quest_json['desc']
        quest.kin_reward = int(quest_json['kin_reward'])
        quest.min_to_complete = int(quest_json['min_to_complete'])
        quest.author_data = quest_json['author']
        quest.tags = quest_json['tags']
        quest.questions = quest_json['questions']
        print(quest)
        db.session.add(quest)
        db.session.commit()
    except Exception as e:
        print('cant add questionnaire to db with id %s' % quest_id)

def get_quest_ids_for_user(user_id):
    '''get the list of current questionnaire_ids for this user'''
    user_app_data = get_user_app_data(user_id)
    if len(user_app_data.answered_quests) == 0:
        return ['0']
