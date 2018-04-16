install-sdk:
	#sudo pip install kin --upgrade
	pip install git+https://github.com/kinecosystem/kin-core-python.git

install:
	sudo pip install . --upgrade

freeze: 
	sudo pip freeze

test:
	export LC_ALL=C
	python kinappserver/tests/book_and_dont_redeem.py
	python kinappserver/tests/book_and_redeem.py
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

