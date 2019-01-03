from kinappserver import db
from kinappserver.utils import test_image, InvalidUsage
import logging as log


class AppDiscovery(db.Model):
    """ the app discovery class represents a single Discoverable App """
    sid = db.Column(db.Integer(), nullable=False, primary_key=True)
    identifier = db.Column(db.String(40), nullable=False, primary_key=False)
    name = db.Column(db.String(80), nullable=False, primary_key=False)
    category_id = db.Column(db.Integer(), nullable=False, primary_key=False)
    is_active = db.Column(db.Boolean, unique=False, default=False)
    os_type = db.Column(db.String(20), primary_key=False, nullable=False)
    meta_data = db.Column(db.JSON, primary_key=False, nullable=False)
    transfer_data = db.Column(db.JSON, primary_key=False, nullable=True)

    def __repr__(self):
        return '<sid: %d, identifier: %s, name: %s, category_id: %d, meta_data: %s, transfer_data: %s>' % (
            self.sid, self.identifier, self.name, self.category_id, self.meta_data, self.transfer_data)


class AppDiscoveryCategory(db.Model):
    """ the app discovery category represents a single App Category """
    category_id = db.Column(db.Integer(), nullable=False, primary_key=True)
    category_name = db.Column(db.String(80), nullable=False, primary_key=False)


def get_address_by_destination_app_sid(destination_app_sid):
    """ return app's public address """
    app = AppDiscovery.query.filter_by(sid=destination_app_sid).first()
    if not app:
        raise InvalidUsage('no such discovery identifier')
    
    return app.meta_data['public_address']

def app_discovery_category_to_json(app_discovery_category):
    """converts app_discovery_category to a json-representation"""
    if not app_discovery_category:
        return {}

    # Build json
    json_app_discovery_category = {'category_id': app_discovery_category.category_id,
                                   'category_name': app_discovery_category.category_name}

    return json_app_discovery_category


def app_discovery_to_json(app_discovery):
    """converts app_discovery to a json-representation"""
    if not app_discovery:
        return {}

    # Build json
    json_app_discovery = {'sid': app_discovery.sid, 'identifier': app_discovery.identifier, 'name': app_discovery.name,
                          'category_id': app_discovery.category_id, 'is_active': app_discovery.is_active,
                          'os_type': app_discovery.os_type, 'meta_data': app_discovery.meta_data}
    if app_discovery.transfer_data:
        json_app_discovery['transfer_data'] = app_discovery.transfer_data

    return json_app_discovery


def add_discovery_app(discovery_app_json, set_active=False):
    """ add discovery app to the db """

    if discovery_app_json['meta_data']:
        meta_data = discovery_app_json['meta_data']
    else:
        log.error('cant add discovery app to db with id %s' % discovery_app_json['identifier'])
        return False

    skip_image_test = discovery_app_json.get('skip_image_test', False)

    if not skip_image_test:
        print('testing accessibility of discovery apps urls (this can take a few seconds...)')
        # ensure all urls are accessible:
        fail_flag = False

        image_url1,image_url2,image_url3, card_image_url, icon_url = meta_data['image_url_0'], meta_data['image_url_1'], meta_data['image_url_2'], meta_data['card_image_url'], meta_data['icon_url']

        if not test_image(image_url1):
            log.error('discovery app image_url - %s - could not be verified' % image_url1)
            fail_flag = True
        if not test_image(image_url2):
            log.error('discovery app image_url - %s - could not be verified' % image_url1)
            fail_flag = True
        if not test_image(image_url2):
            log.error('discovery app image_url - %s - could not be verified' % image_url3)
            fail_flag = True
        if not test_image(card_image_url):
            log.error('discovery app card_image_url - %s - could not be verified' % card_image_url)
            fail_flag = True
        if not test_image(icon_url):
            log.error('discovery app icon_url - %s - could not be verified' % icon_url)
            fail_flag = True

        if fail_flag:
            log.error('could not ensure accessibility of all urls. refusing to add discovery app')
            return False

        log.info('done testing accessibility of discovery app urls')

    try:
        discovery_app = AppDiscovery()
        discovery_app.sid = db.engine.execute('''select count(*) from app_discovery;''').scalar() + 1
        discovery_app.identifier = discovery_app_json['identifier']
        discovery_app.name = discovery_app_json['name']
        discovery_app.category_id = int(discovery_app_json['category_id'])
        discovery_app.os_type = discovery_app_json['os_type']
        discovery_app.meta_data = discovery_app_json['meta_data']
        discovery_app.transfer_data = discovery_app_json.get('transfer_data', None)  # Optional

        db.session.add(discovery_app)
        db.session.commit()
    except Exception as e:
        print(e)
        log.error('cant add discovery app to db with id %s' % discovery_app_json['identifier'])
        return False
    else:
        if set_active:
            set_discovery_app_active(discovery_app_json['identifier'], True)
        return True


def add_discovery_app_category(app_category_json):
    """ add a discovery app category to the db"""
    try:
        discovery_app_category = AppDiscoveryCategory()
        discovery_app_category.category_id = int(app_category_json['category_id'])
        discovery_app_category.category_name = app_category_json['category_name']

        db.session.add(discovery_app_category)
        db.session.commit()
    except Exception as e:
        print(e)
        log.error('cant add discovery category to db with id %s' % app_category_json['category_id'])
        return False
    else:
        return True


def set_discovery_app_active(identifier, is_active):
    """ show/hide discovery app"""
    app = AppDiscovery.query.filter_by(identifier=identifier).first()
    if not app:
        raise InvalidUsage('no such discovery identifier')

    app.is_active = is_active
    db.session.add(app)
    db.session.commit()
    return True


def get_discovery_apps(os_type):
    """ get discovery apps from the db, filter by platform """
    apps = AppDiscovery.query.filter_by(os_type=os_type).all() # android, iOS or both
    categories = AppDiscoveryCategory.query.order_by(AppDiscoveryCategory.category_id).all()

    categories_json_array = []
    # convert to json
    for cat in categories:
        apps_array = []
        for app in apps:
            if app.category_id == cat.category_id and app.is_active:
                json_app = app_discovery_to_json(app)
                json_app['meta_data']['category_name'] = cat.category_name
                apps_array.append(json_app)
        if apps_array:
            cat = app_discovery_category_to_json(cat)
            cat['apps'] = apps_array
            categories_json_array.append(cat)
    return categories_json_array
