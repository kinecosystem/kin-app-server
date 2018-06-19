export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES # https://github.com/ansible/ansible/issues/32499
# ensure you have correctly set the AWS parameters needed to decrypt the ssm paramters
export AWS_ACCESS_KEY_ID=AKIAIHWY5XYTW36LU6DQ
unset AWS_SECURITY_TOKEN
unset AWS_SESSION_TOKEN

ansible-playbook playbooks/kin-app-payment-service-stage.yml -i kin-app-payment-service-stage, -e 'ansible_python_interpreter=/usr/bin/python3'
