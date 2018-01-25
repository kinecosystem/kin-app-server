# kin-wallet-service
An internal service for the Kin Wallet aimed at:
    - storing user data
    - oferring spend and earn opportunities for clients
    - paying clients for completing questionnaires

## Prerequisites
Make sure you have Python 3 >=3.6.4.
and ansible >= 2.4
you'll need to get the ansible-galaxy deps with
    ansible-galaxy install -r playbooks/requirements.yml

## Installation
run ansible (2.4.2.0) with this command:
    ansible-playbook playbooks/kin-wallet-service.yml -i <public_ip>,

## Configuration
All configurations reside in the config.py.jinj2 file (in kin-wallet-server/kinwalletservice/playbooks/roles/kin-wallet-service/templates), which is processed by Ansible into a config.py file.

By default, the config is set to DEBUG mode, which has some pre-set values. Production/Stage values must be give in the Ansible role.

To test the service, run the unittests.

    python3 kinwalletservice/tester.py

note that the tester uses a local, temporary postgress db - it does not mess with prod/stage.

## Running
At the moment, you can run this service with

    flask run
    
You'll probably also need to export the service name, as following:

    export FLASK_APP=kinwalletservice

## Creating the db for the fisrt time:
go into python console and:

     from kinwalletservice import db

     db.create_all()

     if you add/remove/modify the sqlalchemy defs in the code, you'll want to modify any existing 
     prod/stage DB's as well. this needs to happen manually, unless you want to completely re-create the databases.

## External API
 TODO

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
