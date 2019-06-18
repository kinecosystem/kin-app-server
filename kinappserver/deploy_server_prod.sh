export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES # https://github.com/ansible/ansible/issues/32499
ansible-playbook playbooks/kin-app-server-prod.yml -i kinit-server-prod-kin3-2,kinit-server-prod-kin3-1, -e 'ansible_python_interpreter=/usr/bin/python3'

