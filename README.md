# kin-app-server

![](https://travis-ci.org/kinecosystem/kin-app-server.svg?branch=master)

An backend service for the Kinit App aimed at:

    - storing user data (userid, push-token, device-id etc)
    
    - offering spend and earn opportunities for clients
    
    - paying clients via the payment service (https://github.com/kinecosystem/payment-service)
    
    - push messages are sent via rabbit queues to a dedicated Eshu cluster which forwards them to GCM/APNS
    
all hosts are private in AWS. only the web-server ia accessible via a loadbalancer at port 443. Some internal services reside behind a loadbalancer (eshu, the payment service). There's even a load-balancer for the rabbit cluster (for health-checks.

there's also an additional machine (kinit-app-cron) which runs some cron'd scripts.

There's a simplified environment called stage with a single instace of every service.

## General Design
This is a straight-forward flask webapp backed with a Postgress SQL server in AWS. We use redis for syncing some operations. Payments are done asynchronously with the payment service.

- We monitor/alert with datadog/pagerduty
- Refer to the groundcontrol repo for ops data

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

By default, the config is set to DEBUG mode, which has some preset values. Production/Stage values must be give in the Ansible role.

To test the service, run the unittests.

    make install; make test

note that the tester uses a local, temporary postgress db - it does not mess with prod/stage.

## CI
we use travis to run our tests: https://travis-ci.org/kinecosystem/kin-app-server

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
just read the code.


## Contributions
we welcome contributions in the form of pull requests. 

## StyleSheet
We intend to loosly follow pep8 and suggest you do too. We do not intend to obey the limit on line length.

## A bunch of debugging tools:

1. the psql client:
a. install with:
    sudo apt-get install postgresql-client

b. run with:
    export PGPASSWORD=<the password>; psql <db url as given by amazon>
