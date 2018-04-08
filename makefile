install-sdk:
	sudo pip3 install kin --upgrade

install:
	sudo pip3 install . --upgrade

test:
	export LC_ALL=C
	python3 kinappserver/tests/book_and_dont_redeem.py
	python3 kinappserver/tests/book_and_redeem.py
	python3 kinappserver/tests/good_overallocation.py
	python3 kinappserver/tests/good.py
	python3 kinappserver/tests/order.py
	python3 kinappserver/tests/offer.py
	python3 kinappserver/tests/onboarding.py
	python3 kinappserver/tests/task.py
	python3 kinappserver/tests/registration.py
	python3 kinappserver/tests/update_token.py
	python3 kinappserver/tests/user_app_data.py
	python3 kinappserver/tests/task_results.py

all:
	install test

