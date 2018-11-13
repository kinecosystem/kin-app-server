export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES # https://github.com/ansible/ansible/issues/32499
ansible-playbook playbooks/kin-app-server-task2-prod.yml -i kin-app-server-tasks2-prod-1,kin-app-server-tasks2-prod-2, -e 'ansible_python_interpreter=/usr/bin/python3'

