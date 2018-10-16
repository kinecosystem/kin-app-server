from kinappserver import db
from kinappserver.utils import InvalidUsage, test_image


class Category(db.Model):
    """Categories group tasks with similar type/topics"""
    category_id = db.Column(db.String(40), nullable=False, primary_key=True)
    title = db.Column(db.String(100), nullable=False, primary_key=False)
    ui_data = db.Column(db.JSON)

    def __repr__(self):
        return '<category_id: %s, title: %s>' % (self.category_id, self.title)


# TODO cache
def get_all_cat_ids():
    """returns a list of the category ids"""
    res = db.engine.execute('SELECT category_id FROM category GROUP BY category_id')
    return [item[0] for item in res.fetchall()]


def add_category(cat_json):
    """"adds a category to the db based on the given json"""
    cat_id = cat_json['id']
    overwrite_flag = bool(cat_json.get('overwrite', False))
    delete_prior_to_insertion = False

    if get_cat_by_id(cat_id):
        if not overwrite_flag:
            print('cant insert a category with id %s - one already exists' % cat_id)
            raise InvalidUsage('cant overwrite category with id %s' % cat_id)
        else:
            delete_prior_to_insertion = True


    fail_flag = False
    skip_image_test = cat_json.get('skip_image_test', False)

    if not skip_image_test:
        if not test_image(cat_json['ui_data']['image_url']):
            print("cat verify image url: %s" % cat_json['ui_data']['image_url'])
            fail_flag = True

        if not test_image(cat_json['ui_data']['header_image_url']):
            print("cat verify image url: %s" % cat_json['ui_data']['header_image_url'])
            fail_flag = True
    if fail_flag:
        print('could not verify urls. aborting')
        raise InvalidUsage('bad urls. bad!')

    try:
        if delete_prior_to_insertion:
            db.session.delete(Category.query.filter_by(category_id=cat_id).first())

        category = Category()
        category.category_id = cat_id
        category.title = cat_json['title']
        category.ui_data = cat_json['ui_data']

        db.session.add(category)
        db.session.commit()
    except Exception as e:
        print('cant add category to db with id %s, e:' % (cat_id, e))
        return False
    else:
        return True


def get_cat_by_id(cat_id):
    """return the json representation of a category with the given id"""

    category = Category.query.filter_by(category_id=cat_id).first()
    if category is None:
        return None

    # build the json object:
    cat_json = {}
    cat_json['id'] = category.category_id
    cat_json['title'] = category.title
    cat_json['ui_data'] = category.ui_data
    return cat_json


def list_all_categories():
    """returns a dict of all the categories"""
    response = {}
    cats = Category.query.order_by(Category.category_id).all()
    for cat in cats:
        response[cat.category_id] = {'id': cat.category_id, 'ui_data': cat.ui_data, 'title': cat.title}
    return response


def get_categories_for_user(user_id):
    """returns an array of categories tailored to this specific user"""
    #TODO fileter out categories for this user based on OS/Versions etc
    from .user import user_exists
    if not user_exists(user_id):
        raise InvalidUsage('no such user_id %s' % user_id)
    all_cats = list_all_categories()
    # get the number of currently available tasks for the user:
    #TODO fill this in later with actual data

    for cat_id in all_cats.keys():
        all_cats[cat_id]['available_tasks_count'] = 1

    return [cat for cat in all_cats.values()]
