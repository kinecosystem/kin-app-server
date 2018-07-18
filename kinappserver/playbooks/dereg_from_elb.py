import boto3
elbv2 = boto3.client('elbv2', region_name='us-east-1')
import subprocess
import requests
import time
import json
import sys
import arrow

kinit_prod_tg_arn='arn:aws:elasticloadbalancing:us-east-1:935522987944:targetgroup/kinitapp-prod/4311f4679bb3c46b'
MIN_CHECKEDOUT_CONN = 300
DEREGISTER_TIMEOUT_SECS = 60

def get_checkout_connections():
    try:
        response = requests.get('http://localhost:8000/stats/db')
        response.raise_for_status()
        return json.loads(response.text)['stats']['checkedout']
    except Exception as e:
        print(e)
        return None


def get_target_group_instances(target_group_arn):
    response = elbv2.describe_target_health(
        TargetGroupArn=target_group_arn)
    d = {}

    #print('target group health: %s' % response)
    for item in response['TargetHealthDescriptions']:
        d[item['Target']['Id']]=item['TargetHealth']['State']
    return d


def register_instance(kinit_prod_tg_arn, instance_id):
    instances = get_target_group_instances(kinit_prod_tg_arn)

    if instance_id in instances and instances[instance_id] not in ('draining',):
        print('instance %s already in state %s. not registering' % (instance_id, instances[instance_id]))
        return True

    print('regisering instance %s' % instance_id)

    resp=elbv2.register_targets(
        TargetGroupArn=kinit_prod_tg_arn,
        Targets=[
        {
            'Id': instance_id,
        },
    ])
    print('regisering response: %s' % resp)
    return True


def deregister_instance(kinit_prod_tg_arn, instance_id):
    instances = get_target_group_instances(kinit_prod_tg_arn)

    if instance_id not in instances:
        print('no such instance_id %s' % instance_id)
        return False

    if instances[instance_id] in ('unusud',):
        print('instance %s already in state %s. not de-registering' % (instance_id, instances[instance_id]))
        return True

    print('deregisering instance %s' % instance_id)

    resp = elbv2.deregister_targets(
        TargetGroupArn=kinit_prod_tg_arn,
        Targets=[
        {
            'Id': instance_id,
        },
    ])
    print('deregisering response: %s' % resp)
    return True


def wait_for_registered(kinit_prod_tg_arn, instance_id):
    instances = get_target_group_instances(kinit_prod_tg_arn)
    if instances[instance_id] in ('healthy', 'unhealthy'):
        return True

    while True:
        if instances[instance_id] in ('initial'):
            print('current status: %s. sleeping 10 seconds' % instances[instance_id])
            time.sleep(10)
            instances = get_target_group_instances(kinit_prod_tg_arn)
        else:
            break
    return True


def wait_for_unreigstered(kinit_prod_tg_arn, instance_id):
    instances = get_target_group_instances(kinit_prod_tg_arn)
    if instance_id not in instances:
        print('instance %s already not in target group. aborting' % instance_id)
        return True

    start_time = arrow.utcnow()
    while True:

        now = arrow.utcnow()
        if (now-start_time).total_seconds() > DEREGISTER_TIMEOUT_SECS:
            print('timed out waiting for deregister')
            break

        if instance_id in instances:
            print('current status: %s. sleeping 10 seconds' % instances[instance_id])

            time.sleep(10)
            instances = get_target_group_instances(kinit_prod_tg_arn)
        else:
            break
    return True



if __name__ == '__main__':
    import sys
    if sys.argv[1] == 'dereg':
        deregister_instance(sys.argv[2], sys.argv[3])
        wait_for_unreigstered(sys.argv[2], sys.argv[3])
    else:
        register_instance(sys.argv[2], sys.argv[3])
        wait_for_registered(sys.argv[2], sys.argv[3])   	
