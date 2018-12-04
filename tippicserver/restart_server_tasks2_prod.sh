export AWS_REGION='us-east-1'
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES # https://github.com/ansible/ansible/issues/32499

ansible-playbook playbooks/kin-app-server-prod-restart-only.yml -i kin-app-server-tasks2-prod-1,kin-app-server-tasks2-prod-2 --extra-vars "kinit_prod_tg_arn='arn:aws:elasticloadbalancing:us-east-1:935522987944:targetgroup/kinit-app-task2-prod/8871fd4f874d4eb5'"
