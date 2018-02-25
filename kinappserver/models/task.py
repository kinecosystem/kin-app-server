
from sqlalchemy_utils import UUIDType, ArrowType
import arrow
import json

from kinappserver import db
from kinappserver.utils import InvalidUsage, InternalError


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
        from kinappserver.models import UserAppData
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


def get_reward_for_task(task_id):
    '''return the amount of kin reward associated with this task'''
    task = Task.query.filter_by(task_id=task_id).first()
    if not task:
        raise InternalError('no such task_id')
    return task.kin_reward