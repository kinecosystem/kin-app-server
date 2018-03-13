
from sqlalchemy_utils import UUIDType, ArrowType
import arrow
import json

from kinappserver import db, config
from kinappserver.utils import InvalidUsage, InternalError, seconds_to_utc_midnight


class UserTaskResults(db.Model):
    '''
    the user task results
    '''
    user_id = db.Column('user_id', UUIDType(binary=False), db.ForeignKey("user.user_id"), primary_key=True, nullable=False)
    task_id = db.Column(db.String(40), nullable=False, primary_key=True)
    results = db.Column(db.JSON)
    update_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now())


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


def get_user_task_results(user_id):
    '''get the user's task results'''
    return UserTaskResults.query.filter_by(user_id=user_id).order_by(UserTaskResults.update_at).all()


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
    price = db.Column(db.Integer(), nullable=False, primary_key=False)
    min_to_complete = db.Column(db.Integer(), nullable=False, primary_key=False)
    provider_data = db.Column(db.JSON)
    tags = db.Column(db.JSON)
    items = db.Column(db.JSON)
    start_date = db.Column(ArrowType)
    update_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now())

    def __repr__(self):
        return '<task_id: %s, task_type: %s, title: %s, desc: %s, price: %s, min_to_complete: %s, start_date>' % (self.task_id, self.task_type, self.title, self.desc, self.price, self.min_to_complete, self.start_data)


def list_all_task_data():
    '''returns a dict of all the tasks'''
    response = {}
    tasks = Task.query.order_by(Task.task_id).all()
    for task in tasks:
        response[task.task_id] = {'task_id': task.task_id, 'task_type': task.task_type, 'title': task.title}
    return response


def get_tasks_for_user(user_id):
    '''return an array of the current tasks for this user

       if the policy is 'no-cooldown', always return the next avilable task with the time
       set to the user's local 'now'

       if the policy is 'default', always return the next availble task but take into account
       the last time this user submitted task-results, and apply cooldown if nessecary 
    '''

    from .user import get_user_app_data
    from .task import get_user_task_results

    user_app_data = get_user_app_data(user_id)
    # no cooldown policy: just return the time-zone adjusted next task
    if config.TASK_ALLOCATION_POLICY=='no-cooldown':
        if len(user_app_data.completed_tasks) == 0:
            return [get_task_by_id('0')]
        else:
            task = get_task_by_id(str(len(json.loads(user_app_data.completed_tasks))))
            if task is None:
                return []
            else:
                return [task]
    else:
        # with cooldown policy: 
        
        task_results = get_user_task_results(user_id)
        if len(task_results) == 0:
            print('no previous task results, no cooldown needed')
            return [get_task_by_id('0')]

        shift_seconds = 0
        print('task results so far: %s' % task_results)
        if should_apply_cooldown(task_results):
            shift_seconds = calculate_cooldown(user_id)
            print('applying cooldown: shift in seconds: %s' % shift_seconds)
        else:
            print('no cooldown needed')
        task = get_task_by_id(str(len(json.loads(user_app_data.completed_tasks))), shift_seconds)
        if task is None:
            return []
        else:
            return [task]


def calculate_cooldown(user_id):
    '''calculate the time shift (in seconds) needed for cooldown, for this user'''
    from .user import get_user_tz
    user_tz = get_user_tz(user_id)
    seconds_to_midnight = seconds_to_utc_midnight()
    print('seconds to next utc midnight: %s, tz-shift in seconds: %s' % (seconds_to_midnight, -(60*60 * int(user_tz))))
    cooldown = (seconds_to_midnight - (60*60 * int(user_tz)))
    print('total cooldown, in seconds: %s' % cooldown)
    return cooldown


def should_apply_cooldown(ordered_task_results):
    '''return True if cooldown is needed.
    
       cooldown is defined as time since the last time task results were submitted.
    '''
    if not ordered_task_results:
        # should not happened, as checked before
        raise InternalError('no task results were passed')
    else:
        if (arrow.utcnow() - arrow.get(ordered_task_results[0].update_at)).total_seconds() < 24*60*60:
            print('cooldown needed. last submission: %s, total seconds ago: %s' % (ordered_task_results[0].update_at, (arrow.utcnow() - arrow.get(ordered_task_results[0].update_at)).total_seconds()))
            return True
        return False


def get_task_by_id(task_id, shift_seconds=0):
    '''return the json representation of the task or None if no such task exists'''

    task = Task.query.filter_by(task_id=task_id).first()
    if task is None:
        return None

    # build the json object:
    task_json = {}
    task_json['id'] = task_id
    task_json['title'] = task.title
    task_json['type'] = task.task_type
    task_json['desc'] = task.desc
    task_json['price'] = task.price
    task_json['min_to_complete'] = task.min_to_complete
    task_json['provider'] = task.provider_data
    task_json['tags'] = task.tags
    task_json['items'] = task.items
    task_json['start_date'] = arrow.utcnow().shift(seconds=shift_seconds).timestamp
    return task_json


def add_task(task_json):
    try:
        # sanity for task data
        for item in task_json['items']:
            if item['type'] not in ['textimage', 'text']:
                raise InvalidUsage('cant add task with invalid item-type')

        task = Task()
        task.task_id = task_json['id']
        task.task_type = task_json['type']
        task.title = task_json['title']
        task.desc = task_json['desc']
        task.price = int(task_json['price'])
        task.min_to_complete = int(task_json['min_to_complete'])
        task.provider_data = task_json['provider']
        task.tags = task_json['tags']
        task.items = task_json['items']
        print(task_json['start_date'])
        task.start_date = arrow.get(task_json['start_date'])
        print("the task: %s" % task.start_date)
        db.session.add(task)
        db.session.commit()
    except Exception as e:
        print(e)
        print('cant add task to db with id %s' % task_json['id'])
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
    return task.price