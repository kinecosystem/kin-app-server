'''The model for the Kin App Server.'''
from uuid import uuid4
import datetime
import redis_lock
from sqlalchemy_utils import UUIDType, ArrowType
import arrow
import json

from kinappserver import db, config, app, stellar
from kinappserver.utils import InvalidUsage, InternalError, send_apns, send_gcm


class User(db.Model):
    '''
    the user model
    '''
    sid = db.Column(db.Integer(), db.Sequence('sid', start=1, increment=1), primary_key=False)
    user_id = db.Column(UUIDType(binary=False), primary_key=True, nullable=False)
    os_type = db.Column(db.String(10), primary_key=False, nullable=False)
    device_model = db.Column(db.String(40), primary_key=False, nullable=False)
    push_token = db.Column(db.String(200), primary_key=False, nullable=True)
    time_zone = db.Column(db.String(10), primary_key=False, nullable=False)
    device_id = db.Column(db.String(40), primary_key=False, nullable=True)
    created_at = db.Column(db.DateTime(timezone=False), server_default=db.func.now())
    onboarded = db.Column(db.Boolean, unique=False, default=False)

    def __repr__(self):
        return '<sid: %s, user_id: %s, os_type: %s, device_model: %s, push_token: %s, time_zone: %s, device_id: %s, onboarded: %s>' % (self.sid, self.user_id, self.os_type, self.device_model, self.push_token, self.time_zone, self.device_id, self.onboarded)


def get_user(user_id):
    user = User.query.filter_by(user_id=user_id).first()
    if not user:
        raise InvalidUsage('no such user_id')
    return user


def user_exists(user_id):
    user = User.query.filter_by(user_id=user_id).first()
    return True if user else False


def is_onboarded(user_id):
    '''returns wheather the user has an account or None if there's no such user.'''
    try:
        return User.query.filter_by(user_id=user_id).first().onboarded
    except Exception as e:
        return None


def set_onboarded(user_id, onboarded):
    '''set the onbarded field of the user in the db'''
    user = get_user(user_id)
    user.onboarded = onboarded
    db.session.add(user)
    db.session.commit()


def create_user(user_id, os_type, device_model, push_token, time_zone, device_id, app_ver):
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
    user_app_data.completed_tasks = '[]'
    user_app_data.app_ver = app_ver
    db.session.add(user_app_data)
    db.session.commit()


def update_user_token(user_id, push_token):
    '''updates the user's token with a new one'''
    user = get_user(user_id)
    user.push_token = push_token
    db.session.add(user)
    db.session.commit()


def list_all_users():
    '''returns a dict of all the whitelisted users and their PAs (if available)'''
    response = {}
    users = User.query.order_by(User.user_id).all()
    for user in users:
        response[str(user.user_id)] = {'sid': user.sid, 'os': user.os_type, 'push_token': user.push_token, 'time_zone': user.time_zone, 'device_id': user.device_id, 'device_model': user.device_model, 'onboarded': user.onboarded}
    return response


class UserAppData(db.Model):
    '''
    the user app data model tracks the version of the app installed @ the client
    '''
    user_id = db.Column('user_id', UUIDType(binary=False), db.ForeignKey("user.user_id"), primary_key=True, nullable=False)
    app_ver = db.Column(db.String(40), primary_key=False, nullable=False)
    update_at = db.Column(db.DateTime(timezone=False), server_default=db.func.now(), onupdate=db.func.now())
    completed_tasks = db.Column(db.JSON)


def update_user_app_version(user_id, app_ver):
    '''update the user app version'''
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
        response[user.user_id] = {'user_id': user.user_id,  'app_ver': user.app_ver, 'update': user.update_at, 'completed_tasks': user.completed_tasks}
    return response


def get_user_app_data(user_id):
    user_app_data = UserAppData.query.filter_by(user_id=user_id).first()
    if not user_app_data:
        raise InvalidUsage('no such user_id')
    return user_app_data


class UserTaskResults(db.Model):
    '''
    the user task results
    '''
    user_id = db.Column('user_id', UUIDType(binary=False), db.ForeignKey("user.user_id"), primary_key=True, nullable=False)
    task_id = db.Column(db.String(40), nullable=False, primary_key=True)
    results = db.Column(db.JSON)
    update_at = db.Column(db.DateTime(timezone=False), server_default=db.func.now(), onupdate=db.func.now())


def store_task_results(user_id, task_id, results):
    '''store the results provided by the user'''
    try:
        # store the results
        userTaskResults = UserTaskResults()
        userTaskResults.user_id = user_id
        userTaskResults.task_id = task_id
        userTaskResults.results = results
        db.session.add(userTaskResults)

        # write down the completed task-id
        user_app_data = UserAppData.query.filter_by(user_id=user_id).first()
        if user_app_data is None:
            raise('cant retrieve user app data for user:%s' % user_id)
        completed_tasks = json.loads(user_app_data.completed_tasks)
        completed_tasks.append(task_id)
        user_app_data.completed_tasks = json.dumps(completed_tasks)
        db.session.add(user_app_data)
        db.session.commit()
    except Exception as e:
        print(e)
        raise InvalidUsage('cant store_task_results')


def list_all_users_results_data():
    '''returns a dict of all the user-results-data'''
    response = {}
    user_results = UserTaskResults.query.order_by(UserTaskResults.user_id).all()
    for user in user_results:
        response[user.user_id] = {'user_id': user.user_id,  'task_id': user.task_id, 'results': user.results}
    return response


class Task(db.Model):
    '''the Task class represent a single task'''
    task_id = db.Column(db.String(40), nullable=False, primary_key=True)
    task_type = db.Column(db.String(40), nullable=False, primary_key=True)
    title = db.Column(db.String(80), nullable=False, primary_key=False)
    desc = db.Column(db.String(80), nullable=False, primary_key=False)
    kin_reward = db.Column(db.Integer(), nullable=False, primary_key=False)
    min_to_complete = db.Column(db.Integer(), nullable=False, primary_key=False)
    author_data = db.Column(db.JSON)
    tags = db.Column(db.JSON)
    items = db.Column(db.JSON)
    start_date = db.Column(ArrowType)
    update_at = db.Column(db.DateTime(timezone=False), server_default=db.func.now(), onupdate=db.func.now())

    def __repr__(self):
        return '<task_id: %s, task_type: %s, title: %s, desc: %s, kin_reward: %s, min_to_complete: %s, start_date>' % (self.task_id, self.task_type, self.title, self.desc, self.kin_reward, self.min_to_complete, self.start_data)


def list_all_task_data():
    '''returns a dict of all the tasks'''
    response = {}
    tasks = Task.query.order_by(Task.task_id).all()
    for task in tasks:
        response[task.task_id] = {'task_id': task.task_id, 'task_type': task.task_type, 'title': task.title}
    return response


def get_task_by_id(task_id):
    '''return a json representing the task'''
    task = Task.query.filter_by(task_id=task_id).first()
    if task is None:
        return None
    # build the json object:
    task_json = {}
    task_json['id'] = task_id
    task_json['title'] = task.title
    task_json['type'] = task.task_type
    task_json['desc'] = task.desc
    task_json['kin_reward'] = task.kin_reward
    task_json['min_to_complete'] = task.min_to_complete
    task_json['author'] = task.author_data
    task_json['tags'] = task.tags
    task_json['items'] = task.items
    task_json['start_date'] = task.start_date.timestamp
    return task_json


def add_task(task_json):
    try:
        task = Task()
        task.task_id = task_json['task_id']
        task.task_type = task_json['type']
        task.title = task_json['title']
        task.desc = task_json['desc']
        task.kin_reward = int(task_json['kin_reward'])
        task.min_to_complete = int(task_json['min_to_complete'])
        task.author_data = task_json['author']
        task.tags = task_json['tags']
        task.items = task_json['items']
        print(task_json['start_date'])
        task.start_date = arrow.get(task_json['start_date'])
        print("the task: %s" % task.start_date)
        db.session.add(task)
        db.session.commit()
    except Exception as e:
        print(e)
        print('cant add task to db with id %s' % task_json['task_id'])
        return False
    else:
        return True


def update_task_time(task_id, time_string):
    '''debug function used to update existing tasks's time in the db'''
    task = Task.query.filter_by(task_id=task_id).first()
    if not task:
        raise InternalError('no such task_id')
    task.start_date = time_string
    db.session.add(task)
    db.session.commit()


def get_task_ids_for_user(user_id):
    '''get the list of current task_ids for this user.
       the current policy is to hand the user the n+1 task, 
       which happens to be the len(completed tasks):
       len(0) == 1
       len(0,1) == 2
       len(0,1,2) == 3 etc
    '''
    user_app_data = get_user_app_data(user_id)
    if len(user_app_data.completed_tasks) == 0:
        return ['0']
    else:
        return [str(len(json.loads(user_app_data.completed_tasks)))]


def get_reward_for_task(task_id):
    '''return the amount of kin reward associated with this task'''
    task = Task.query.filter_by(task_id=task_id).first()
    if not task:
        raise InternalError('no such task_id')
    return task.kin_reward


class Transaction(db.Model):
    '''
    kin transactions
    '''
    user_id = db.Column('user_id', UUIDType(binary=False), db.ForeignKey("user.user_id"), primary_key=True, nullable=False)
    tx_hash = db.Column(db.String(100), nullable=False, primary_key=True)
    amount = db.Column(db.Integer(), nullable=False, primary_key=False)
    update_at = db.Column(db.DateTime(timezone=False), server_default=db.func.now(), onupdate=db.func.now())

    def __repr__(self):
        return '<tx_hash: %s, user_id: %s, amount: %s, desc: %s, update_at: %s>' % (self.tx_hash, self.user_id, self.amount, self.update_at)


def list_all_transactions():
    '''returns a dict of all the tasks'''
    response = {}
    txs = Transaction.query.order_by(Transaction.update_at).all()
    for tx in txs:
        response[tx.tx_hash] = {'tx_hash': tx.tx_hash, 'user_id': tx.user_id, 'amount': tx.amount, 'update_at': tx.update_at}
    return response


def create_tx(tx_hash, user_id, amount):
    try:
        tx = Transaction()
        tx.tx_hash = tx_hash
        tx.user_id = user_id
        tx.amount = int(amount)
        db.session.add(tx)
        db.session.commit()
    except Exception as e:
        print(e)
        print('cant add tx to db with id %s' % tx_hash)


def reward_store_and_push(public_address, task_id, send_push, user_id):
    '''create a thread to perform this function in the background'''
    from threading import Thread
    thread = Thread(target=reward_address_for_task_internal, args=(public_address, task_id, send_push, user_id))
    thread.start()


def reward_address_for_task_internal(public_address, task_id, send_push, user_id):
    '''transfer the correct amount of kins for the task to the given address'''
    # get reward amount from db
    amount = get_reward_for_task(task_id)
    if not amount:
        print('could not figure reward amount for task_id: %s' % task_id)
        raise InternalError('cant find reward for taskid %s' % task_id)
    try:
        # send the moneys
        print('calling send_kin: %s, %s' % (public_address, amount))
        tx_hash = stellar.send_kin(public_address, amount, 'kin-app')#-taskid:%s' % task_id)
    except Exception as e:
        print('caught exception sending %s kins to %s - exception: %s:' % (amount, public_address, e))
        raise InternalError('failed sending %s kins to %s' % (amount, public_address))
    finally: #TODO dont do this if we fail with the tx
        if send_push:
            send_push_tx_completed(user_id, tx_hash, amount, task_id)
        create_tx(tx_hash, user_id, amount) # TODO Add memeo?


def get_user_push_data(user_id):
    '''returns the os_type and the token for the given user_id'''
    response = {}
    user = User.query.filter_by(user_id=user_id).first()
    if not user:
        return None, None
    else:
        return user.os_type, user.push_token


def send_push_tx_completed(user_id, tx_hash, amount, task_id):
    '''send a message indicating that the tx has been successfully completed'''
    os_type, token = get_user_push_data(user_id)
    if token is None:
        print('cant push to user %s: no push token' % user_id)
        return False
    if os_type == 'iOS': #TODO move to consts
        payload = {} #TODO finalize this
        send_apns(token, payload)
    else:
        payload = {'type': 'tx_completed', 'user_id': user_id, 'tx_hash': tx_hash, 'kin': amount, 'task_id': task_id}
        send_gcm(token, payload)
    return True
