export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES # https://github.com/ansible/ansible/issues/32499
ansible-playbook playbooks/kin-app-server-stage2-bin.yml -i kin-app-server-stage-2, -e 'ansible_python_interpreter=/usr/bin/python3'


