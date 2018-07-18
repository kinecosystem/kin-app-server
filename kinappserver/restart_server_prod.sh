export AWS_REGION='us-east-1'
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES # https://github.com/ansible/ansible/issues/32499

ansible-playbook playbooks/kin-app-server-prod-restart-only.yml -i kin-app-server-prod-1,kin-app-server-prod-2
