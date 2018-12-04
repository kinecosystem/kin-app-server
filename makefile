install-sdk:
	#sudo pip3 install kin --upgrade
	pip3 install git+https://github.com/kinecosystem/kin-core-python.git

install:
	sudo pip3 install . --upgrade

install-travis:
	sudo pip install . --upgrade
	
test:
	export LC_ALL=C
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/captcha.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/captcha_auto_flag.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/auth_token.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/phone_verification.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/phone_verification_2.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/balance.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/versions.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/registration.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/update_token.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/user_app_data.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/backup_questions.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/backup_questions2.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/utils_test.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/phone_verification_blacklisted_phone.py
	python3 -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/blacklisted_phone_numbers.py
	# python3 -m pytest -v -rs -s -x  --disable-pytest-warnings tippicserver/tests/onboarding.py
all:
	install test

