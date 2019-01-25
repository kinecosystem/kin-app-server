install-sdk:
	#sudo pip3 install kin --upgrade
	pip3 install git+https://github.com/kinecosystem/kin-core-python.git@master

install:
	sudo pip3 install . --upgrade

install-travis:
	sudo pip install . --upgrade

install-cv-module:
	ssh-agent bash -c 'ssh-add ~/.ssh/secret; pip install git+ssh://git@github.com/kinecosystem/kinit-client-validation-server-module.git#egg=kinit-client-validation-module  --upgrade'
	
	
test:
	export LC_ALL=C
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/category.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/ad-hoc-task.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/count_immediate_tasks.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/captcha.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/captcha_auto_flag.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/migrate_user_to_tasks2.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/book_and_redeem.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/task_results_resubmission.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/auth_token.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/phone_verification.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/phone_verification_2.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/balance.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/versions.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/old_client_new_task.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/book_and_dont_redeem.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/good_overallocation.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/good.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/order.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/offer.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/task.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/registration.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/update_token.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/user_app_data.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/task_results.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/task_results_overwrite.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/task_results_quiz.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/backup_questions.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/backup_questions2.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/utils_test.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/phone_verification_blacklisted_phone.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/blacklisted_phone_numbers.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/task_results_resubmission_other_user.py
	# python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/book_and_redeem_multiple.py 
	# python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/three_redeems_in_a_row.py
	# python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/task_results_out_of_order.py 
	# python3 -m pytest -v -rs -s -x  --disable-pytest-warnings kinappserver/tests/onboarding.py
all:
	install test

