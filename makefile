install:
	sudo pip3 install . --upgrade
test:
	python3 kinappserver/tests/registration.py
	python3 kinappserver/tests/update_token.py

