export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES # https://github.com/ansible/ansible/issues/32499
ansible-playbook playbooks/tippic-server-stage-bin.yml -i tippic-server-stage, -e 'ansible_python_interpreter=/usr/bin/python3'


