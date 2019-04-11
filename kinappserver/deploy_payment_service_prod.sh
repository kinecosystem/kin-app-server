export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES # https://github.com/ansible/ansible/issues/32499
ansible-playbook playbooks/kin-app-payment-service-prod.yml -i kin-app-payment-service-prod-4, -e 'ansible_python_interpreter=/usr/bin/python3'


