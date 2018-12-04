install-sdk:
	#sudo pip3 install kin --upgrade
	pip3 install git+https://github.com/kinecosystem/kin-core-python.git

install:
	sudo pip3 install . --upgrade

install-travis:
	sudo pip install . --upgrade
	
test:
	export LC_ALL=C
	python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/category.py
	python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/ad-hoc-task.py
	python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/count_immediate_tasks.py
	python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/captcha.py
	python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/captcha_auto_flag.py
	python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/migrate_user_to_tasks2.py
	python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/book_and_redeem.py
	python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/task_results_resubmission.py
	python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/auth_token.py
	python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/phone_verification.py
	python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/phone_verification_2.py
	python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/balance.py
	python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/versions.py
	python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/old_client_new_task.py
	python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/book_and_dont_redeem.py
	python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/good_overallocation.py
	python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/good.py
	python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/order.py
	python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/offer.py
	python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/task.py
	python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/registration.py
	python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/update_token.py
	python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/user_app_data.py
	python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/task_results.py
	python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/task_results_overwrite.py
	python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/task_results_quiz.py
	python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/backup_questions.py
	python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/backup_questions2.py
	python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/utils_test.py
	python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/phone_verification_blacklisted_phone.py
	python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/blacklisted_phone_numbers.py
	python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/task_results_resubmission_other_user.py
	# python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/book_and_redeem_multiple.py
	# python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/three_redeems_in_a_row.py
	# python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/task_results_out_of_order.py
	# python -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/onboarding.py
all:
	install test

