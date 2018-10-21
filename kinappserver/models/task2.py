
from sqlalchemy_utils import UUIDType, ArrowType
import arrow
import json
from ast import literal_eval

from kinappserver import db, config, app
from kinappserver.push import send_please_upgrade_push
from kinappserver.utils import InvalidUsage, InternalError, seconds_to_local_nth_midnight, OS_ANDROID, OS_IOS, DEFAULT_MIN_CLIENT_VERSION, test_image, test_url, get_country_code_by_ip, increment_metric, commit_json_changed_to_orm
from kinappserver.models import store_next_task_results_ts, get_next_task_results_ts, get_user_os_type, get_user_app_data, get_unenc_phone_number_by_user_id
from .truex_blacklisted_user import is_user_id_blacklisted_for_truex

TASK_TYPE_TRUEX = 'truex'


class UserTaskResults(db.Model):
    """
    the user task results
    """
    user_id = db.Column('user_id', UUIDType(binary=False), db.ForeignKey("user.user_id"), primary_key=True, nullable=False)
    task_id = db.Column(db.String(40), nullable=False, primary_key=True)
    results = db.Column(db.JSON)
    update_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now())


def reject_premature_results(user_id, task_id):
    """determine whether the results were submitted prematurely"""
    next_task_ts = get_next_task_results_ts(user_id, get_task_by_id(task_id)['cat_id'])
    if next_task_ts is None:
        return False
    
    now = arrow.utcnow()
    results_valid_at = arrow.get(next_task_ts)

    if results_valid_at > now:
        print('rejecting results. will only be valid in %s seconds' % (results_valid_at - now).total_seconds())
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


# TODO add cache
def get_cat_id_for_task_id(task_id):
    return get_task_by_id(task_id)['cat_id']


def store_task_results(user_id, task_id, results):
    """store the results provided by the user"""
    # reject hackers trying to send task results too soon

    try:
        # store the results

        try:
            user_task_results = UserTaskResults()
            user_task_results.user_id = user_id
            user_task_results.task_id = task_id
            user_task_results.results = results
            db.session.add(user_task_results)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            # this code handles the unlikely event that a user already had task results for this task, so rather
            # than INSERT, we UPDATE.
            print('store_task_results - failed to insert results. attempting to update instead. error:%s' % e)
            previous_task_results = UserTaskResults.query.filter_by(user_id=user_id).filter_by(task_id=task_id).first()
            previous_task_results.results = results
            db.session.add(previous_task_results)
            db.session.commit()
            print('store_task_results: overwritten user_id %s task %s results' % (user_id, task_id))
            increment_metric('overwrite-task-results')

        # write down the completed task-id
        from kinappserver.models import UserAppData
        user_app_data = UserAppData.query.filter_by(user_id=user_id).first()
        if user_app_data is None:
            print('cant retrieve user app data for user:%s' % user_id)
            raise InternalError('cant retrieve user app data for user:%s' % user_id)

        cat_id = get_cat_id_for_task_id(task_id)
        if not cat_id:
            print('cant find cat_id for task_id %s' % task_id)
            raise InternalError('cant find cat_id for task_id %s' % task_id)

        if cat_id in user_app_data.completed_tasks_dict:
            user_app_data.completed_tasks_dict[cat_id].append(task_id)
        else:
            user_app_data.completed_tasks_dict[cat_id] = [task_id]

        commit_json_changed_to_orm(user_app_data, ['completed_tasks_dict'])

        print('wrote user_app_data.completed_tasks for userid: %s' % user_id)

        # calculate the next valid submission time, and store it:
        delay_days = None
        # calculate the next task's valid submission time, and store it:
        # this takes into account the delay_days field on the next task.

        # note: even if we end up skipping the next task (for example, truex for iOS),
        # we should still use the original delay days value (as done here).

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

        store_next_task_results_ts(user_id, task_id, shifted_ts)

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


class Task2(db.Model):
    """the Task class represent a single task"""
    category_id = db.Column('category_id', db.String(40), db.ForeignKey("category.category_id"), primary_key=False, nullable=False)
    task_id = db.Column(db.String(40), nullable=False, primary_key=True)
    position = db.Column(db.Integer(), nullable=False, primary_key=False) # -1 for ad-hoc tasks. multiple tasks can have -1.
    task_type = db.Column(db.String(40), nullable=False, primary_key=True)
    title = db.Column(db.String(80), nullable=False, primary_key=False)
    description = db.Column(db.String(200), nullable=False, primary_key=False)
    price = db.Column(db.Integer(), nullable=False, primary_key=False)
    video_url = db.Column(db.String(100), nullable=True, primary_key=False)
    min_to_complete = db.Column(db.Float(), nullable=False, primary_key=False)
    provider_data = db.Column(db.JSON)
    excluded_country_codes = db.Column(db.JSON, default=[])
    tags = db.Column(db.JSON)
    items = db.Column(db.JSON)
    task_start_date = db.Column(ArrowType, nullable=True)  # governs when the task is available (only used in ad-hoc tasks)
    task_expiration_date = db.Column(ArrowType, nullable=True)  # a task with expiration is an ad-hoc task
    update_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now())
    delay_days = db.Column(db.Integer(), nullable=False, primary_key=False)
    min_client_version_android = db.Column(db.String(80), nullable=False, primary_key=False)
    min_client_version_ios = db.Column(db.String(80), nullable=False, primary_key=False)
    post_task_actions = db.Column(db.JSON)

    def __repr__(self):
        return '<task_id: %s, task_type: %s, title: %s' % (self.task_id, self.task_type, self.title)


def list_all_task_data():
    """returns a dict of all the tasks"""
    response = {}
    tasks = Task2.query.order_by(Task2.task_id).all()
    for task in tasks:
        response[task.task_id] = {'task_id': task.task_id, 'task_type': task.task_type, 'title': task.title}
    return response


def next_task_id_for_category(os_type, app_ver, completed_tasks, cat_id, user_id, user_country_code):
    """returns the next task id that:
     1. belongs to the given cat_id
     2. is yet un-answered by the user
     3. is not filtered by country_code

     if the next task_id requires an upgrade, send push and return an empty set
     if no task can be matched return an empty set
     """

    completed_tasks_for_cat_id = completed_tasks.get(cat_id, None)
    if not completed_tasks_for_cat_id:
        remove_previous_tasks_clause = ''
    else:
        # oh man, this is ugly: convert ['0','1'] to ["\'0\'", ...] and then to "\'0\',\'1\',\'2\'"
        completed_tasks_for_cat_id = ["\'%s\'" % id for id in completed_tasks_for_cat_id]
        remove_previous_tasks_clause = '''and task2.task_id not in (%s)''' % (",".join(completed_tasks_for_cat_id))
    # get ALL the unsolved task_ids for the category
    stmt = '''SELECT task2.task_id FROM task2 WHERE task2.category_id='%s' %s order by task2.position;''' % (cat_id, remove_previous_tasks_clause)
    print(stmt)
    res = db.engine.execute(stmt)
    unsolved_task_ids = [item[0] for item in res.fetchall()]
    print('unsolved tasks for cat_id %s: %s' % (cat_id, unsolved_task_ids))

    # go over all the yet-unsolved tasks and get the first valid one
    for task_id in unsolved_task_ids:
        task = get_task_by_id(task_id)

        # skip country-blocked tasks
        if user_country_code in task['excluded_country_codes']:
            # we're skipping this task
            print('skipping task_id %s for user %s with country-code %s' % (task_id, user_id, user_country_code))
            continue

        if not can_support_task(os_type, app_ver, task):
            send_please_upgrade_push(user_id)
            return []

        print('next_task_id_for_category: returning task_ids %s for cat_id %s and user_id %s' % (task_id, cat_id, user_id))
        return [task_id]
    # no tasks available
    print('next_task_id_for_category: no available tasks for user_id %s in cat_id %s' % (user_id, cat_id))
    return []


def get_next_tasks_for_user(user_id, source_ip=None, cat_ids=[]):
    """this function returns the next immediate task for the given user in all the categories, or just the specified category (if given).
    - the returned tasks will bear this format: {'cat_id': [task1, task2]}
    - if a source_ip was provided, the returned tasks will be filtered for country code
    - if there are no more tasks, an empty array will be returned (per category)
    - if the next task (in each category) requires upgrade, the function will send a push message to inform the user (with a cooldown).
    """
    tasks_per_category = {}
    user_app_data = get_user_app_data(user_id)
    os_type = get_user_os_type(user_id)
    app_ver = user_app_data.app_ver
    from .category import get_all_cat_ids
    for cat_id in cat_ids or get_all_cat_ids():
        print('getting tasks for cat-id: %s' % cat_id)
        task_ids = next_task_id_for_category(os_type, app_ver, user_app_data.completed_tasks_dict, cat_id, user_id, get_country_code_by_ip(source_ip))  # returns just one task in a list or empty list
        tasks_per_category[cat_id] = [get_task_by_id(task_id) for task_id in task_ids]
        # plant the memo and start date in the first task of the category:
        from .user import get_next_task_memo
        from .user import get_next_task_results_ts
        if len(tasks_per_category[cat_id]) > 0:
            tasks_per_category[cat_id][0]['memo'] = get_next_task_memo(user_id, cat_id)
            tasks_per_category[cat_id][0]['start_date'] = get_next_task_results_ts(user_id, cat_id)

        print('tasks_per_category: %s' % tasks_per_category)

    return tasks_per_category


def should_skip_truex_task(user_id, task_id, source_ip=None):
    if get_user_os_type(user_id) == OS_IOS:
        print('skipping truex task %s for ios user %s' % (task_id, user_id))
        return True

    unenc_phone_number = get_unenc_phone_number_by_user_id(user_id)

    if unenc_phone_number and unenc_phone_number.find('+1') != 0:
        print('skipping truex task %s for prefix %s' % (task_id, unenc_phone_number[:3]))
        return True

    if source_ip:
        try:
            if app.geoip_reader.get(source_ip)['country']['iso_code'] != 'US':
                print('detected non-US source IP - skipping truex task')
                return True
        except Exception as e:
            print('should_skip_task: could not figure out country from source ip %s' % source_ip)
            pass

    # TODO cache results here
    # skip selected user_ids
    if is_user_id_blacklisted_for_truex(user_id):
        print('skipping truex task %s for blacklisted user %s' % (task_id, user_id))
        return True


def should_skip_task(user_id, task_id, source_ip):
    """determines whether to skip the given task_id for the given user_id"""
    try:
        # skip truex for iOS devices, non-american android
        if get_task_type(task_id) == TASK_TYPE_TRUEX:
            if should_skip_truex_task(user_id, task_id, source_ip):
                return True
        else:  # not truex
            # skip special truex-related tasks for users that skipped the truex task
            if task_id in literal_eval(config.TRUEX_BLACKLISTED_TASKIDS) and should_skip_truex_task(user_id, task_id, source_ip):
                print('skipping blacklisted truex task %s' % task_id)
                return True

    except Exception as e:
        print('caught exception in should_skip_task, defaulting to no. e=%s' % e)

    return False


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

    task = Task2.query.filter_by(task_id=task_id).first()
    if task is None:
        return None

    # build the json object:
    task_json = {}
    task_json['id'] = task_id
    task_json['cat_id'] = task.category_id
    task_json['position'] = task.position
    task_json['title'] = task.title
    task_json['type'] = task.task_type
    task_json['desc'] = task.description
    task_json['price'] = task.price
    task_json['excluded_country_codes'] = task.excluded_country_codes
    if task.video_url is not None:
        task_json['video_url'] = task.video_url
    task_json['min_to_complete'] = task.min_to_complete
    task_json['provider'] = task.provider_data
    task_json['tags'] = task.tags
    task_json['items'] = task.items
    task_json['updated_at'] = arrow.get(task.update_at).timestamp
    task_json['start_date'] = int(shifted_ts if shifted_ts is not None else arrow.get(0).timestamp)  # return 0 if no shift was requested
    task_json['task_start_date']= task.task_start_date
    task_json['task_expiration_date'] = task.task_expiration_date
    task_json['min_client_version_android'] = task.min_client_version_android or DEFAULT_MIN_CLIENT_VERSION
    task_json['min_client_version_ios'] = task.min_client_version_ios or DEFAULT_MIN_CLIENT_VERSION
    task_json['post_task_actions'] = [] if not task.post_task_actions else task.post_task_actions

    return task_json


def add_task(task_json):

    def is_position_taken(cat_id, position):
        """determines whether there is already a task at the given category and position"""

        if position == -1:
            # position -1 is shared among all ad-hoc tasks
            return True
        try:
            Task2.query.filter(Task2.category_id == cat_id).filter(Task2.position == position).one()
        except Exception as e:
            return False
        else:
            return True

    delete_prior_to_adding = False
    task_id = str(task_json['id'])
    print('trying to add task with id %s...' % task_id)

    position = int(task_json['position'])
    task_start_date = task_json.get('task_start_date', None)
    task_expiration_date = task_json.get('task_expiration_date', None)
    category_id = task_json['cat_id']
    overwrite_task = task_json.get('overwrite', False)

    # does the task_id already exist?
    if get_task_by_id(task_id):
        if not overwrite_task:
            print('cant add task with id %s - already exists. provide the overwrite flag to overwrite the task' % task_id)
            raise InvalidUsage('task_id %s already exists' % task_id)
        else:
            print('task %s already exists - overwriting it' % task_id)
            delete_prior_to_adding = True

    # sanity for position
    if position == -1:
        if None in (task_expiration_date, task_start_date):
            print('cant add ad-hoc task w/o expiration/start date')
            raise InvalidUsage('cant add ad-hoc task w/o start/expiration dates')
    elif is_position_taken(category_id, position) and not overwrite_task:
            print('cant insert task_id %s at cat_id %s and position %s - position already taken' % (task_id, category_id, position))
            raise InvalidUsage('cant insert task - position taken')

    # sanity for task data
    for item in task_json['items']:
        if item['type'] not in ['textimage', 'text', 'textmultiple', 'textemoji', 'rating', 'tip', 'dual_image']:
            print('invalid item type:%s ' % item['type'])
            raise InvalidUsage('cant add task with invalid item-type')


        # test validity of quiz items
        try:
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
        except Exception as e:
            print('failed to verify the quiz data. aborting')
            raise InvalidUsage('cant verify quiz data for task_id %s' % task_id)

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

            post_task_actions = task_json.get('post_task_actions', None)
            if post_task_actions:
                for action in post_task_actions:
                    if action.get('type') == 'external-url':
                        icon_url = action.get('icon_url', None)
                        if icon_url and not test_image(icon_url):
                            print('icon_url url - %s - could not be verified' % icon_url)
                            fail_flag = True

            print('done testing accessibility of task urls')

        if fail_flag:
            print('cant verify the images - aborting')
            raise InvalidUsage('cant verify images')

    try:
        if delete_prior_to_adding:
            task_to_delete = Task2.query.filter_by(task_id=task_json['id']).first()
            db.session.delete(task_to_delete)

        task = Task2()
        task.delay_days = task_json.get('delay_days', 1)  # default is 1
        task.task_id = task_id
        task.category_id = category_id
        task.position = position  # unique in category, except for ad-hocs which are always -1. TODO allocate position automatically for non adhocs
        task.task_type = task_json['type']
        task.title = task_json['title']
        task.description = task_json['desc']
        task.price = int(task_json['price'])
        task.video_url = task_json.get('video_url', None)
        task.min_to_complete = float(task_json['min_to_complete'])
        task.provider_data = task_json['provider']
        task.tags = task_json['tags']
        task.items = task_json['items']
        task.excluded_country_codes = task_json.get('excluded_country_codes', [])
        task.task_start_date = task_start_date  # required for ad-hoc
        task.expiration_date = task_expiration_date  # required for ad-hoc
        task.min_client_version_ios = task_json.get('min_client_version_ios', DEFAULT_MIN_CLIENT_VERSION)
        task.min_client_version_android = task_json.get('min_client_version_android', DEFAULT_MIN_CLIENT_VERSION)
        task.post_task_actions = task_json.get('post_task_actions', None)

        db.session.add(task)
        db.session.commit()
        return True
    except Exception as e:
        print('cant add task to db with id %s. exception: %s' % (task_id, e))
        db.session.rollback()
        return False


def delete_task(task_id):
    if not get_task_by_id(task_id):
        print('no task with id %s in the db' % task_id)
        raise InvalidUsage('task_id %s doesnt exist - cant delete' % task_id)

    task_to_delete = Task2.query.filter_by(task_id=task_id).first()
    db.session.delete(task_to_delete)
    db.session.commit()


def set_delay_days(delay_days, task_id=None):
    """sets the delay days on all the tasks or optionally on one task"""
    if task_id:  # sanitize input
        task_id = int(task_id)

    where_clause = '' if not task_id else 'where task_id=\'%s\'' % task_id
    db.engine.execute("update task2 set delay_days=%d %s" % (int(delay_days), where_clause))  # safe
    return True


def get_reward_for_task(task_id):
    """return the amount of kin reward associated with this task"""
    task = Task2.query.filter_by(task_id=task_id).first()
    if not task:
        raise InternalError('no such task_id: %s' % task_id)
    return task.price


def get_task_delay(task_id):
    """return the amount of delay associated with this task"""
    task = Task2.query.filter_by(task_id=task_id).first()
    if not task:
        raise InternalError('no such task_id: %s' % task_id)
    return task.delay_days


def get_task_type(task_id):
    """get the tasks type"""
    task = Task2.query.filter_by(task_id=task_id).first()
    if not task:
        raise InternalError('no such task_id: %s' % task_id)
    return task.task_type


def get_task_details(task_id):
    """return a dict with some of the given taskid's metadata"""
    task = Task2.query.filter_by(task_id=task_id).first()
    if not task:
        print('cant find task with task_id %s. using default text' % task_id)
        return {'title': 'Delayed Kin', 'desc': '', 'provider': {"image_url": "https://cdn.kinitapp.com/brand_img/poll_logo_kin.png", "name": "Kinit Team"}}
    return {'title': task.title, 'desc': task.description, 'provider': task.provider_data}


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
    #print('trying to detect task re-submission for task-id %s and user_id %s' % (task_id, user_id))
    associated_user_ids = get_associated_user_ids(user_id)
    #print('all associated user_ids: %s' % associated_user_ids)
    memo, user_id = get_memo_for_user_ids(associated_user_ids, task_id)
    return memo, user_id


def get_truex_activity(user_id, cat_id, remote_ip, user_agent):
    """returns a truex activity for the user if she is allowed one now"""

    tasks = []

    # is the next task of type 'truex'?
    try:
        tasks = get_next_tasks_for_user(user_id, remote_ip, cat_id)
    except Exception as e:
        print('cant get activity - no such user %s' % user_id)

    if tasks[cat_id] == []:
        print('cant get activity: no next task')
        return None

    if tasks[0]['tasks'][0]['type'] != TASK_TYPE_TRUEX:
        print('cant get activity: user\'s next task isnt truex')
        return None

    # is the user eligible for a task now?
    now = arrow.utcnow()
    next_task_ts = get_next_task_results_ts(user_id, cat_id)
    if next_task_ts and now < arrow.get(next_task_ts):
        print('cant get truex activity: now: %s user\'s tx: %s' % (now, arrow.get(next_task_ts)))
        return None

    # get truex activity for user:
    from kinappserver.truex import get_activity
    #TODO should we get/convert screen size to window size? also should we bother with density?
    return get_activity(user_id, remote_ip, user_agent)  # returns status, activity


def switch_task_ids(task_id1, task_id2):
    """replaces two task ids in the db"""
    task1 = get_task_by_id(task_id1)
    task2 = get_task_by_id(task_id2)

    if None in (task1, task2):
        print('cant find task_id(s) (%s,%s)' % (task_id1, task_id2))
        raise InvalidUsage('no such task_id')

    # pick some random, unused task_id
    import random
    while True:
        temp_task_id = str(random.randint(900000, 999999))
        if not get_task_by_id(temp_task_id):
            break

    stmt = '''update task set task_id='%s' where task_id='%s';'''
    db.engine.execute('BEGIN;' + stmt % (temp_task_id, task_id1) + stmt % (task_id1, task_id2) + stmt % (task_id2, temp_task_id) + 'COMMIT;')


def add_task_to_completed_tasks(user_id, task_id):
    user_app_data = get_user_app_data(user_id)
    completed_tasks = user_app_data.completed_tasks_dict
    from .task2 import get_task_by_id
    task = get_task_by_id(task_id)
    if not task:
        print('cant find task with id %s' % task_id)
        raise InvalidUsage('no such task %s' % task_id)

    cat_id = task['cat_id']
    if cat_id in completed_tasks and task_id in completed_tasks[cat_id]:
        print('task_id %s already in completed_tasks for user_id %s - ignoring' % (task_id, user_id))
    else:
        if cat_id not in completed_tasks:
            completed_tasks[cat_id] = []
        completed_tasks[cat_id].append(task_id)
        user_app_data.completed_tasks = completed_tasks
        commit_json_changed_to_orm(user_app_data, ['completed_tasks_dict'])
        print(user_app_data.completed_tasks)
        return True


def remove_task_from_completed_tasks(user_id, task_id):
    user_app_data = get_user_app_data(user_id)
    completed_tasks = user_app_data.completed_tasks_dict
    print(completed_tasks)
    from .task2 import get_task_by_id
    task = get_task_by_id(task_id)
    if not task:
        raise InvalidUsage('no such task %s' % task_id)

    cat_id = task['cat_id']
    if cat_id not in completed_tasks or task_id not in completed_tasks[cat_id]:
        print('task_id %s not in completed_tasks for user_id %s - ignoring' % (task_id, user_id))
    else:
        completed_tasks[cat_id].remove(task_id)
        user_app_data.completed_tasks_dict = completed_tasks
        commit_json_changed_to_orm(user_app_data, ['completed_tasks_dict'])

    return True


def count_immediate_tasks(user_id):
    """given the user's task history, calculate how many tasks are readily avilable for each category"""
    # this function needs to take into account the following things:
    # 1. which tasks were already solved by the user
    # 2. the delay_days for each task
    # 3. the client's os type and app_ver
    # 4. the user's last recorded ip address
    immediate_tasks_count = 0
    now = arrow.utcnow()
    user_app_data = get_user_app_data(user_id)
    completed_tasks = user_app_data.completed_tasks_dict
    os_type = get_user_os_type(user_id)
    app_ver = user_app_data.app_ver
    country_code = get_country_code_by_ip(user_app_data.ip_address)

    tasks_per_category = get_next_tasks_for_user(user_id)
    print(tasks_per_category)
    for cat_id in tasks_per_category.keys():
        if tasks_per_category[cat_id] == []:
            # no tasks available. skip.
            pass
        elif tasks_per_category[cat_id][0]['start_date'] > now.timestamp:
            # the first task isn't available now, so skip.
            pass
        else:
            filtered_unsolved_tasks_for_user_and_cat = get_all_unsolved_tasks_delay_days_for_category(cat_id, completed_tasks.get(cat_id, []), os_type, app_ver, country_code, user_id)
            immediate_tasks_count_for_cat_id = calculate_immediate_tasks(filtered_unsolved_tasks_for_user_and_cat)
            print('counted %s immediate tasks for cat_id %s' % (immediate_tasks_count_for_cat_id, cat_id))
            immediate_tasks_count = immediate_tasks_count + immediate_tasks_count_for_cat_id

    print('count_immediate_tasks for user_id %s - %s' % (user_id, immediate_tasks_count))
    return immediate_tasks_count


def get_all_unsolved_tasks_delay_days_for_category(cat_id, completed_task_ids_for_category, os_type, client_version, user_country_code, user_id):
    """for the given category_id returns list of tasks, in order, with their delay days excluding previously completed tasks"""

    # calculate a sql clause to remove previously submitted tasks, if such exist
    remove_previous_tasks_clause = ''
    if completed_task_ids_for_category:
        completed_tasks_for_cat_id = ["\'%s\'" % id for id in completed_task_ids_for_category]
        remove_previous_tasks_clause = '''and task2.task_id not in (%s)''' % (",".join(completed_tasks_for_cat_id))

    stmt = '''select task_id, delay_days, min_client_version_android, min_client_version_ios, excluded_country_codes from Task2 where category_id='%s' %s order by position;''' % (cat_id, remove_previous_tasks_clause)
    print(stmt)
    res = db.engine.execute(stmt)

    # exclude mismatching tasks - client version
    unsolved_tasks = []
    if os_type == OS_IOS:
        client_version_index = 3
    else:
        client_version_index = 2
    from distutils.version import LooseVersion
    for task in [item for item in res.fetchall()]:
        skip_task = False
        if LooseVersion(task[client_version_index]) > LooseVersion(client_version):
            print('detected a task (%s) that doesnt match the users os_type and app_ver. user_id %s' % (task[0], user_id))
            skip_task = True
        if task[4] not in (None, []) and user_country_code and user_country_code in task[4]:
            print('detected a task (%s) that cant be served to user because of country code. user_id %s' % (task[0], user_id))
            # the task is limited to a specific country, and the user's country is different
            skip_task = True
        #TODO TASKS2.0 add Truex blacklist into the mix

        if not skip_task:
            unsolved_tasks.append(task)

    return unsolved_tasks


def calculate_immediate_tasks(filtered_unsolved_tasks_for_user):
    """return the number of immediate tasks in the given tasks array"""

    if filtered_unsolved_tasks_for_user == []:
        # its possible all the tasks were filtered by version or country code
        return 0

    # this code assumes that the first unsolved task is readily available to the user, or otherwise this called is never called.
    total_tasks = 1  # start with one, because the first task is currently available

    items_count = len(filtered_unsolved_tasks_for_user)
    for idx, task in enumerate(filtered_unsolved_tasks_for_user):
        if task.delay_days == 0 and idx != items_count-1:
            total_tasks = total_tasks + 1
        else:
            break
    return total_tasks



