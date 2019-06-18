export AWS_REGION='us-east-1'
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES # https://github.com/ansible/ansible/issues/32499

ansible-playbook playbooks/kin-app-server-prod-restart-only.yml -i kinit-server-prod-kin3-2,kinit-server-prod-kin3-1, --extra-vars "kinit_prod_tg_arn='arn:aws:elasticloadbalancing:us-east-1:935522987944:targetgroup/ami-payment/b58102c0b5108c1e'"
