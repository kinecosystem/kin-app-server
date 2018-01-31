# kin-app-server
Note: this repo is at a very early stage of work.

An internal service for the Kin App aimed at:
    - storing user data
    - oferring spend and earn opportunities for clients
    - paying clients for completing questionnaires

## Prerequisites
Make sure you have Python 3 >=3.6.4.
and ansible >= 2.4
you'll need to get the ansible-galaxy deps with
    ansible-galaxy install -r playbooks/requirements.yml

## Installation
this server is intended to be deployed on an ubuntu machine with python3. You'll need to tell Ansible to use the python3 interpreter.

run ansible (2.4.2.0) with this command:
    ansible-playbook playbooks/kin-app-server.yml -i <public_ip>, -e 'ansible_python_interpreter=/usr/bin/python3'

## Configuration
All configurations reside in the config.py.jinj2 file (in kin-app-server/kinappserver/playbooks/roles/kin-app-server/templates), which is processed by Ansible into a config.py file.

By default, the config is set to DEBUG mode, which has some pre-set values. Production/Stage values must be give in the Ansible role.

To test the service, run the unittests.

    python3 kinappserver/tester.py

note that the tester uses a local, temporary postgress db - it does not mess with prod/stage.

## Running
At the moment, you can run this service with

    flask run
    
You'll probably also need to export the service name, as following:

    export FLASK_APP=kinappserver

## Creating the db for the fisrt time:
go into python console and:

     from kinappserver import db

     db.create_all()

     if you add/remove/modify the sqlalchemy defs in the code, you'll want to modify any existing 
     prod/stage DB's as well. this needs to happen manually, unless you want to completely re-create the databases.

## External API
    POST /user/register
    - register a new user_id (valid UUID RFC 4122) to the system. 
    optionally pass a push-token.

    input: a json payload with the following fields:
                        {
                            'user_id': <UUID, picked by the client>,
                            'os': 'android/ios',
                            'device_model': 'samsung8',
                            'device_id': '<some device id like iemi>',
                            'time_zone': '+05:00',
                            'token':'optional push token'}),
                        }
    returns 200OK, 'status'='ok' on success

    POST /user/app-launch
    - update the db with the app's latest activity time and app-version

    input: a json payload with the following fields:
                        {
                            'user_id': <UUID, picked by the client>,
                            'app_ver':'1.0'}),
                        }
    returns 200OK, 'status'='ok' on success

    GET /user/quest?user_id=<uuid>
    - get this user's current questionnaire(s)

    POST /user/quest/answers
    - post answers for a questionnaire

    POST /user/update-token
    - post updates to the client's push token


## Contributions
we welcome contributions in the form of pull requests. At the moment there's very little code - 
but at some point we'll have more and your input would be welcome.

## StyleSheet
We intend to loosly follow pep8 and suggest you do too. We do not intend to obey the limit on line length.

## API Changelog
  

## A bunch of debugging tools:

1. the psql client:
a. install with:

    sudo apt-get install postgresql-client

b. run with:

    export PGPASSWORD=<the password>; psql <db url as given by amazon>

2. a useful mac ui for postgress: http://www.psequel.com/
