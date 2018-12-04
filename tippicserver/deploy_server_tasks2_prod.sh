export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES # https://github.com/ansible/ansible/issues/32499
ansible-playbook playbooks/tippic-server-task2-prod.yml -i tippic-server-tasks2-prod-1,tippic-server-tasks2-prod-2, -e 'ansible_python_interpreter=/usr/bin/python3'

