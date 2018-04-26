install-sdk:
	#sudo pip3 install kin --upgrade
	pip3 install git+https://github.com/kinecosystem/kin-core-python.git

install:
	sudo pip3 install . --upgrade

install-travis:
	sudo pip install . --upgrade

test:
	export LC_ALL=C
	python kinappserver/tests/book_and_redeem.py
	python kinappserver/tests/three_redeems_in_a_row.py
	python kinappserver/tests/balance.py
	python kinappserver/tests/versions.py
	python kinappserver/tests/old_client_new_task.py
	python kinappserver/tests/book_and_dont_redeem.py
	python kinappserver/tests/book_and_redeem_multiple.py
	python kinappserver/tests/good_overallocation.py
	python kinappserver/tests/good.py
	python kinappserver/tests/order.py
	python kinappserver/tests/offer.py
	python kinappserver/tests/onboarding.py
	python kinappserver/tests/task.py
	python kinappserver/tests/registration.py
	python kinappserver/tests/update_token.py
	python kinappserver/tests/user_app_data.py
	python kinappserver/tests/task_results.py

all:
	install test

