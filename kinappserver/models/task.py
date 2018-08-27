
from sqlalchemy_utils import UUIDType, ArrowType
import arrow
import json

from kinappserver import db, config
from kinappserver.push import send_please_upgrade_push
from kinappserver.utils import InvalidUsage, InternalError, seconds_to_local_nth_midnight, OS_ANDROID, DEFAULT_MIN_CLIENT_VERSION, test_image, test_url
from kinappserver.models import store_next_task_results_ts, get_next_task_results_ts


TASK_TYPE_TRUEX = 'truex'


class UserTaskResults(db.Model):
    """
    the user task results
    """
    user_id = db.Column('user_id', UUIDType(binary=False), db.ForeignKey("user.user_id"), primary_key=True, nullable=False)
    task_id = db.Column(db.String(40), nullable=False, primary_key=True)
    results = db.Column(db.JSON)
    update_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now())


def reject_premature_results(user_id):
    """determine whether the results were submitted prematurely"""
    next_task_ts = get_next_task_results_ts(user_id)
    if next_task_ts is None:
        return False
    
    now = arrow.utcnow()
    results_valid_at = arrow.get(next_task_ts)

    if results_valid_at > now:
        print('rejecting results. will only be valid in %s seconds' % (results_valid_at - now).total_seconds() )
        return True
    return False


def calculate_timeshift(user_id, delay_days=1):
    """calculate the time shift (in seconds) needed for cooldown, for this user"""
    from .user import get_user_tz
    print('calculating timeshift for user_id: %s' % user_id)
    user_tz = get_user_tz(user_id)
    seconds_to_midnight = seconds_to_local_nth_midnight(user_tz, delay_days)
    print('seconds to next local midnight: %s for user_id %s with tz %s' % (seconds_to_midnight, user_id, user_tz))
    return seconds_to_midnight


def store_task_results(user_id, task_id, results):
    """store the results provided by the user"""
    # reject hackers trying to send task results too soon


    try:
        # store the results
        user_task_results = UserTaskResults()
        user_task_results.user_id = user_id
        user_task_results.task_id = task_id
        user_task_results.results = results
        db.session.add(user_task_results)

        # write down the completed task-id
        from kinappserver.models import UserAppData
        user_app_data = UserAppData.query.filter_by(user_id=user_id).first()
        if user_app_data is None:
            print('cant retrieve user app data for user:%s' % user_id)
            raise InternalError('cant retrieve user app data for user:%s' % user_id)
        completed_tasks = json.loads(user_app_data.completed_tasks)
        completed_tasks.append(task_id)
        user_app_data.completed_tasks = json.dumps(completed_tasks)
        db.session.add(user_app_data)
        db.session.commit()

        print('wrote user_app_data.completed_tasks for userid: %s' % user_id)

        # calculate the next valid submission time, and store it:
        delay_days = None
        # calculate the next task's valid submission time, and store it:
        # this takes into account the delay_days field on the next task.
        try:
            delay_days = get_task_delay(str(int(task_id) + 1))  # throws exception if no such task exists
        except Exception as e:
            print('cant find task_delay for next task_id of %s' % task_id)

        if delay_days is None or int(delay_days) == 0:
            shifted_ts = arrow.utcnow().timestamp
            print('setting next task time to now (delay_days is: %s)' % delay_days)
        else:
            shift_seconds = calculate_timeshift(user_id, delay_days)
            shifted_ts = arrow.utcnow().shift(seconds=shift_seconds).timestamp
            print('setting next task time to %s seconds in the future' % shift_seconds)

        print('next valid submission time for user %s, (previous task id %s) in shifted_ts: %s' % (user_id, task_id, shifted_ts))

        store_next_task_results_ts(user_id, shifted_ts)

        return True
    except Exception as e:
        print('exception in store_task_results: %s', e)
        raise InvalidUsage('cant store_task_results')


def get_user_task_results(user_id):
    """get the user's task results, ordered by update_at"""
    return UserTaskResults.query.filter_by(user_id=user_id).order_by(UserTaskResults.update_at).all()


def list_all_users_results_data():
    """returns a dict of all the user-results-data"""
    response = {}
    user_results = UserTaskResults.query.order_by(UserTaskResults.user_id).all()
    for user in user_results:
        response[user.user_id] = {'user_id': user.user_id,  'task_id': user.task_id, 'results': user.results}
    return response


def get_task_results(task_id):
    """returns all the results for the task with the given id"""
    results = UserTaskResults.query.filter_by(task_id=task_id).order_by(UserTaskResults.user_id).all()
    # format the results as json
    results_dict = {}
    for entry in results:
        results_dict[str(entry.user_id)] = entry.results
    print('results: %s' % results_dict)
    return results_dict


class Task(db.Model):
    """the Task class represent a single task"""
    task_id = db.Column(db.String(40), nullable=False, primary_key=True)
    task_type = db.Column(db.String(40), nullable=False, primary_key=True)
    title = db.Column(db.String(80), nullable=False, primary_key=False)
    desc = db.Column(db.String(200), nullable=False, primary_key=False)
    price = db.Column(db.Integer(), nullable=False, primary_key=False)
    video_url = db.Column(db.String(100), nullable=True, primary_key=False)
    min_to_complete = db.Column(db.Float(), nullable=False, primary_key=False)
    provider_data = db.Column(db.JSON)
    tags = db.Column(db.JSON)
    items = db.Column(db.JSON)
    start_date = db.Column(ArrowType)
    update_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now())
    delay_days = db.Column(db.Integer(), nullable=False, primary_key=False)
    min_client_version_android = db.Column(db.String(80), nullable=False, primary_key=False)
    min_client_version_ios = db.Column(db.String(80), nullable=False, primary_key=False)

    def __repr__(self):
        return '<task_id: %s, task_type: %s, title: %s, desc: %s, price: %s, video_url: %s, min_to_complete: %s, start_date: %s, delay_days: %s, min_client_version_android: %s, min_client_version_ios %s>' % \
               (self.task_id, self.task_type, self.title, self.desc, self.price, self.video_url, self.min_to_complete, self.start_data, self.delay_days, self.min_client_version_android, self.min_client_version_ios)


def list_all_task_data():
    """returns a dict of all the tasks"""
    response = {}
    tasks = Task.query.order_by(Task.task_id).all()
    for task in tasks:
        response[task.task_id] = {'task_id': task.task_id, 'task_type': task.task_type, 'title': task.title}
    return response


def get_tasks_for_user(user_id):
    """return an array of the current tasks for this user or empty array if there are
        no more tasks in the db.

       there are 3 outcomes here:
        - either this user has no pre-existing results -> gets the first task
        - or the user completed all the available tasks -> gets an empty array
        - or the user gets the next task (which is len(completed-tasks)
    """

    from .user import get_user_app_data, get_user_os_type

    user_app_data = get_user_app_data(user_id)

    # if the user has no previous task results, just give her task '0'
    if len(user_app_data.completed_tasks) == 0:
        print('no previous task results, giving task 0')
        return [get_task_by_id('0')]


    next_task = get_task_by_id(str(len(json.loads(user_app_data.completed_tasks))), get_next_task_results_ts(user_id))

    if next_task is None:  # no more tasks atm...
        return []
    else:
        # does the user's client support this task?
        os_type = get_user_os_type(user_id)
        if not can_support_task(os_type, user_app_data.app_ver, next_task):
            # client does NOT support the next task, so return an empty array and push a notification
            print('user %s, client os:%s client_ver:%s does not support the next task. returning empty array' % (user_id, os_type, user_app_data.app_ver))
            send_please_upgrade_push(user_id)
            return []

        else:
            return [next_task]


def can_support_task(os_type, app_ver, task):
    """ returns true if the client with the given os_type and app_ver can correctly handle the given task"""
    from distutils.version import LooseVersion
    if os_type == OS_ANDROID:
        if LooseVersion(app_ver) >= LooseVersion(task.get('min_client_version_android')):
            return True
    elif LooseVersion(app_ver) >= LooseVersion(task.get('min_client_version_ios')):
            return True
    print('can_support_task: task min version: %s, the client app version: %s' % (task.get('min_client_version_android'), app_ver))
    return False


def get_task_by_id(task_id, shifted_ts=None):
    """return the json representation of the task or None if no such task exists"""

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
    if task.video_url is not None:
        task_json['video_url'] = task.video_url
    task_json['min_to_complete'] = task.min_to_complete
    task_json['provider'] = task.provider_data
    task_json['tags'] = task.tags
    task_json['items'] = task.items
    task_json['updated_at'] = arrow.get(task.update_at).timestamp
    task_json['start_date'] = int(shifted_ts if shifted_ts is not None else arrow.utcnow().timestamp)
    task_json['min_client_version_android'] = task.min_client_version_android or DEFAULT_MIN_CLIENT_VERSION
    task_json['min_client_version_ios'] = task.min_client_version_ios or DEFAULT_MIN_CLIENT_VERSION

    return task_json


def add_task(task_json):
    try:
        print('trying to add task...')
        # sanity for task data
        for item in task_json['items']:
            if item['type'] not in ['textimage', 'text', 'textmultiple', 'textemoji', 'rating', 'tip', 'dual_image']:
                print('invalid item type:%s ' % item['type'])
                raise InvalidUsage('cant add task with invalid item-type')

            # test validity of quiz items
            if item.get('quiz_data', None):
                # the task must be of type quiz
                if not task_json['type'] == 'quiz':
                        raise InvalidUsage('found quiz_data for a non-quiz task type')

                # quiz_data must have answer_id, explanation and reward and they must not be empty
                answer_id = item['quiz_data']['answer_id']
                exp = item['quiz_data']['explanation']
                reward = item['quiz_data']['reward']
                if '' in (answer_id, exp, reward):
                    raise InvalidUsage('empty fields in one of answer_id, exp, reward')

                # the answer_id must match a an answer in the item results
                if answer_id not in [result['id'] for result in item['results']]:
                    raise InvalidUsage('answer_id %s does not match answer_ids %s' % (answer_id, [result['id'] for result in item['results']]))


        fail_flag = False
        skip_image_test = task_json.get('skip_image_test', False)

        if task_json['type'] == 'video_questionnaire':
            video_url = task_json.get('video_url', None)
            if video_url is None:
                print('missing video_url in video_questionnaire')
                raise InvalidUsage('no video_url field in the video_questionnaire!')
            elif not skip_image_test:
                    if not test_url(video_url):
                        print('failed to get the video url: %s' % video_url)
                        fail_flag = True

        if not skip_image_test:
            print('testing accessibility of task urls (this can take a few seconds...)')
            # ensure all urls are accessible:
            image_url = task_json['provider'].get('image_url')
            if image_url:
                if not test_image(image_url):
                    print('image url - %s - could not be verified' % image_url)
                    fail_flag = True

            # test image_url within item results
            items = task_json['items']
            for item in items:
                image_url = item.get('image_url', None)
                if image_url is not None and not test_image(image_url):
                    print('failed to verify task image_url: %s' % image_url)
                    fail_flag = True
                for res in item['results']:
                    image_url = res.get('image_url', None)
                    if image_url is not None and not test_image(image_url):
                        print('failed to verify task result image_url: %s' % image_url)
                        fail_flag = True
            print('done testing accessibility of task urls')

        if fail_flag:
            print('cant verify the images - aborting')
            raise InvalidUsage('cant verify images')

        task = Task()
        task.delay_days = task_json.get('delay_days', 1)  # default is 1
        task.task_id = task_json['id']
        task.task_type = task_json['type']
        task.title = task_json['title']
        task.desc = task_json['desc']
        task.price = int(task_json['price'])
        task.video_url = task_json.get('video_url', None)
        task.min_to_complete = float(task_json['min_to_complete'])
        task.provider_data = task_json['provider']
        task.tags = task_json['tags']
        task.items = task_json['items']
        task.start_date = arrow.get(task_json['start_date'])
        task.min_client_version_ios = task_json.get('min_client_version_ios', DEFAULT_MIN_CLIENT_VERSION)
        task.min_client_version_android = task_json.get('min_client_version_android', DEFAULT_MIN_CLIENT_VERSION)
        db.session.add(task)
        db.session.commit()
    except Exception as e:
        print(e)
        print('cant add task to db with id %s' % task_json['id'])
        return False
    else:
        return True


def set_delay_days(delay_days, task_id=None):
    """sets the delay days on all the tasks or optionally on one task"""
    if task_id:  # sanitize input
        task_id = int(task_id)

    where_clause = '' if not task_id else 'where task_id=\'%s\'' % task_id
    db.engine.execute("update task set delay_days=%d %s" % (int(delay_days), where_clause))  # safe
    return True


def get_reward_for_task(task_id):
    """return the amount of kin reward associated with this task"""
    task = Task.query.filter_by(task_id=task_id).first()
    if not task:
        raise InternalError('no such task_id: %s' % task_id)
    return task.price


def get_task_delay(task_id):
    """return the amount of delay associated with this task"""
    task = Task.query.filter_by(task_id=task_id).first()
    if not task:
        raise InternalError('no such task_id: %s' % task_id)
    return task.delay_days


def get_task_details(task_id):
    """return a dict with some of the given taskid's metadata"""
    task = Task.query.filter_by(task_id=task_id).first()
    if not task:
        print('cant find task with task_id %s. using default text' % task_id)
        return {'title': 'Delayed Kin', 'desc': '', 'provider': {"image_url": "https://cdn.kinitapp.com/brand_img/poll_logo_kin.png", "name": "Kinit Team"}}
    return {'title': task.title, 'desc': task.desc, 'provider': task.provider_data}


def handle_task_results_resubmission(user_id, task_id):
    """
    This function handles cases where users attempt to re-submit previously submitted results

    there are 2 main cases:
        - the user is re-submitting results of a task for which she was already compensated
        - the user is re-submitting results of a task for which she was NOT already compensated.

        the first case is easy: just retrieve the transaction and send the memo back to the user.

        the second case is more complicated: ideally we want to erase the previous results and just
        continue as usual (meaning, save the results and compensate the user. however, we must also ensure
        that the user isn't already in the process of being compensated to prevent double-payments
    """
    from kinappserver.models import get_memo_for_user_ids

    from .user import get_associated_user_ids
    associated_user_ids = get_associated_user_ids(user_id)
    memo, user_id = get_memo_for_user_ids(associated_user_ids, task_id)
    return memo, user_id


def get_truex_activity(user_id, remote_ip, user_agent):
    """returns a truex activity for the user if she is allowed one now"""

    tasks = []

    # is the next task of type 'truex'?
    try:
        tasks = get_tasks_for_user(user_id)
    except Exception as e:
        print('cant get activity - no such user %s' % user_id)

    if tasks == []:
        print('cant get activity: no next task')
        return None

    if tasks[0]['type'] != TASK_TYPE_TRUEX:
        print('cant get activity: user\'s next task isnt truex')
        return None

    # is the user eligible for a task now?
    now = arrow.utcnow()
    next_task_ts = get_next_task_results_ts(user_id)
    if next_task_ts and now < arrow.get(next_task_ts):
        print('cant get truex activity: now: %s user\'s tx: %s' % (now, arrow.get(next_task_ts)))
        return None

    # get truex activity for user:
    from kinappserver.truex import get_activity
    #TODO should we get/convert screen size to window size? also should we bother with density?
    return get_activity(user_id, remote_ip, user_agent)  # returns status, activity
