install:
	sudo pip3 install . --upgrade

test:
#	python3 kinappserver/tests/onboarding.py
	python3 kinappserver/tests/task.py
	python3 kinappserver/tests/task_results.py
	python3 kinappserver/tests/registration.py
	python3 kinappserver/tests/update_token.py
	python3 kinappserver/tests/user_app_data.py

all:
	install test

