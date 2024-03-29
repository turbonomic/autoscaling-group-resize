##This function runs based on an event generated by a Turbo instance to change the launch config for an ASG
#It first ensures the event is generated by the right Turbo instance, make sure you change the autorize_role to the Turbo target name for the AWS account you want to run this in
#Second it increased the capacity of the ASG 
#Third it sequentually terminates the older EC2 instances in the ASG allowing the ASG scaling process to ensure EC2 instance type consistency 
#Note, this uses a 60 second  grace period for changing the ASG, you could turn on CloudWatch for the ASG and use those metrics insted (e.g. GroupInServiceInstances)

import boto3
import time

region = []
asg = []
instance_ids = []
#change this authorize_role 
authorized_role = "PM.sedemo"
desired_capacity_original = 0
desired_capacity_new = 0
max_capacity_original = 0 
max_capacity_new = 0

def lambda_handler(event, context):
    #check if this is a Turbo generated change 
    str = event['detail']['userIdentity']['principalId']
    
    if authorized_role in str:

        #get the region and ASG name 
        region = event['region']
        asg = event['detail']['requestParameters']['autoScalingGroupName']

        #get the instacnes in the ASG and put them into instance_ids 
        asg_client = boto3.client('autoscaling',region_name=region)
        asg_response = asg_client.describe_auto_scaling_groups(AutoScalingGroupNames=[asg])

        for i in asg_response['AutoScalingGroups']:
            for k in i['Instances']:
                instance_ids.append(k['InstanceId'])

        #get the desired and max capacity for the group 
        desired_capacity_original = asg_client.describe_auto_scaling_groups (AutoScalingGroupNames=[asg])\
        ["AutoScalingGroups"][0]["DesiredCapacity"]

        max_capacity_original = asg_client.describe_auto_scaling_groups (AutoScalingGroupNames=[asg])\
        ["AutoScalingGroups"][0]["MaxSize"]

        desired_capacity_new = desired_capacity_original +1 

        if max_capacity_original < desired_capacity_new:
            max_capacity_new = max_capacity_original +1 
        else:
            max_capacity_new = max_capacity_original

        #increase desired capacity 
        asg_response = asg_client.update_auto_scaling_group (AutoScalingGroupName=asg, MaxSize=max_capacity_new,DesiredCapacity=desired_capacity_new)

        #give asg a chance to increase instances 
        time.sleep(60)

        #stop the instances one at a time 
        ec2_client = boto3.client('ec2', region_name=region)
        length = len(instance_ids) 
        j = 0  #which instance are we on 

        #iterate through the list of instances in the asg 

        while j < length:

            #stop instance 
            ec2_response = asg_client.terminate_instance_in_auto_scaling_group(InstanceId=instance_ids[j], ShouldDecrementDesiredCapacity=False)
            #check that the instance wasterminated 
            waiter = ec2_client.get_waiter('instance_terminated')
            #give new instance a chance to launch 
            time.sleep(60)
            j += 1

        #decrease desired capacity and max back to original 
        asg_response = asg_client.update_auto_scaling_group (AutoScalingGroupName=asg, MaxSize=max_capacity_original,DesiredCapacity=desired_capacity_original)

        #we're done 
        print ('terminated instances in: ' + region, asg)

    else:
	    print ('not a Turbo event')
