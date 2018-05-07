ansible-playbook playbooks/kin-app-server-prod-restart-only.yml -i kin-app-server-prod-1,kin-app-server-prod-2 -e 'ansible_python_interpreter=/usr/bin/python3'
