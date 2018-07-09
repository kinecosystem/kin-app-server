export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES # https://github.com/ansible/ansible/issues/32499
ansible-playbook playbooks/kin-app-server-stage-bin.yml -i kin-app-server-stage, -e 'ansible_python_interpreter=/usr/bin/python3'

