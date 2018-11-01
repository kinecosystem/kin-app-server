install-sdk:
	#sudo pip3 install kin --upgrade
	pip3 install git+https://github.com/kinecosystem/kin-core-python.git

install:
	sudo pip3 install . --upgrade

install-travis:
	sudo pip install . --upgrade

test:
	export LC_ALL=C
	# python kinappserver/tests/task_results_out_of_order.py # disabled until we decide how to handle this
	python kinappserver/tests/category.py
	python kinappserver/tests/ad-hoc-task.py
	python kinappserver/tests/count_immediate_tasks.py
	python kinappserver/tests/captcha.py
	python kinappserver/tests/captcha_auto_flag.py
	python kinappserver/tests/migrate_user_to_tasks2.py
	python kinappserver/tests/migrate_tasks.py
	python kinappserver/tests/book_and_redeem.py
	python kinappserver/tests/task_results_resubmission_other_user.py
	python kinappserver/tests/task_results_resubmission.py
	python kinappserver/tests/auth_token.py
	python kinappserver/tests/phone_verification.py
	python kinappserver/tests/phone_verification_2.py
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
	##python kinappserver/tests/onboarding.py
	python kinappserver/tests/task.py
	python kinappserver/tests/registration.py
	python kinappserver/tests/update_token.py
	python kinappserver/tests/user_app_data.py
	python kinappserver/tests/task_results.py
	python kinappserver/tests/task_results_overwrite.py
	python kinappserver/tests/task_results_quiz.py
	python kinappserver/tests/backup_questions.py
	python kinappserver/tests/backup_questions2.py
	python kinappserver/tests/utils_test.py
	python kinappserver/tests/phone_verification_blacklisted_phone.py
	python kinappserver/tests/blacklisted_phone_numbers.py
	python kinappserver/tests/captcha.py

all:
	install test

