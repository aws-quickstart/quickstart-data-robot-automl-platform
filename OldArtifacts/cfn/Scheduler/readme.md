# The DataRobot EBS SnapShot Scheduler Kit

**These files are for use with DataRobot nodes only!**

## Summary

The process below will walk the user through the installation and usage of the DataRobot EBS SnapShot Scheduler CloudFormation templates.

By default, the system will take a back up on Monday - Friday at midnight, UTC.

---

## Packing list

| File Name                               | Comment      |
|:----------------------------------------|:-------------|
| DataRobot_EBS-SnapShot-Scheduler_Kit.py | Main helper script to stage all the files and prep the command |
| EBS-SnapShot-Scheduler.py               | Python file used by the Lambda function |
| EBS-SnapShot-Stack.yaml | This is the main template used by the Master Stack |
| readme.md | this file |
| StandAlone-EBS-SnapShot-Scheduler-Stack.yaml | Allows the user to apply this functionality to any datarobot cluster |

---

## Easy Install

The DataRobot_EBS-SnapShot-Scheduler_Kit.py tool provides an easy way to place the required files in the right place in the given bucket such that it does not interfere with any other code.

### Usage

```bash
./DataRobot_EBS-SnapShot-Scheduler_Kit.py create --stackname DataRobot-Test-ESBSnapShot-Stack --s3bucket datarobot-testcluster-enterprise-5.2.0-cloudformation --instances i-123,i-456,i-789,i-abc,i-def,i-hij

=== Started DataRobot_EBS-SnapShot-Scheduler_Kit.py ===
-------------------------------------------------------
Args: Namespace(action='create', debug=False, instances='i-01a70cda2f4eb4bbb,i-0b65b858fb7748c72,i-09932cf7779665fa5,i-0db655c6d6c220419,i-04155f5e717f334c8,i-0776acc0a60df0a0a', key=5619, myname='DataRobot-EBS-SnapShot-Scheduler', pyfile='EBS-SnapShot-Scheduler.py', region='us-east-1', s3bucket='datarobot-testcluster-enterprise-5.2.0-cloudformation', stackfile='EBS-SnapShot-Scheduler-Stack.yaml', stackname='TestCluster-Test-ESBSnapShot-Stack', tag=None, tags=[{'Key': 'builder', 'Value': 'testcluster'}], templateurl='https://s3.amazonaws.com/datarobot-testcluster-enterprise-5.2.0-cloudformation/Scheduler/EBS-SnapShot-Scheduler-Stack.yaml', zipfile='EBS-SnapShot-Scheduler.zip')
Applying 'EBS-SnapShot-Scheduler-Stack.yaml' to the nodes referenced by 'DataRobot-Test-ESBSnapShot-Stack'
Tags: [{'Key': 'builder', 'Value': 'bill.t.cat'}]
--------------------------------------------
Deleted old EBS-SnapShot-Scheduler.zip
Added: EBS-SnapShot-Scheduler.py | Compressed size: 2052 | Modified: 2019-10-14 09:16:20
Closed EBS-SnapShot-Scheduler.zip
Found credentials in environment variables.
Uploaded EBS-SnapShot-Scheduler.zip to datarobot-testcluster-enterprise-5.2.0-cloudformation/Scheduler/EBS-SnapShot-Scheduler.zip
Uploaded EBS-SnapShot-Scheduler-Stack.yaml to datarobot-testcluster-enterprise-5.2.0-cloudformation/Scheduler/EBS-SnapShot-Scheduler-Stack.yaml
Created CloudFormation stack: DataRobot-EBS-SnapShot-Scheduler
--------------------------------------------
EBS Create test event: { "RequestType": "Create", "StackName": "DataRobot-EBS-SnapShot-Scheduler" }
--------------------------------------------
```

---

## Manual Installation

- Log onto <https://s3.console.aws.amazon.com/s3/> and create a new bucket

- Unpack the DataRobot Scheduler tarball into a safe location

```bash
cd /my/safe/location
tar xzvf DataRobot-Scheduler-Kit.<DataStamp>.tar.gz
```

- Zip up the EBS-SnapShot-Scheduler.py file

```bash
cd /my/safe/location/Scheduler
zip EBS-SnapShot-Scheduler.zip EBS-SnapShot-Scheduler.py
```

- Copy the Scheduler directory upto the bucket

```bash
cd /my/safe/location
aws s3 sync ./Scheduler s3://<Your bucket name>/Scheduler
```

- Goto <https://console.aws.amazon.com/cloudformation>, click the `Create stack` button and in the Amazoon S3 URL input field, use the updated varient of:

```bash
https://s3.amazonaws.com/><Your bucket name>/Scheduler/EBS-SnapShot-Scheduler-Stack.yaml
```

- Enter a **stack name**, the name of our bucket and the comma seperated list of instances to put in the EBS SnapShot Scheduling system, the rest of the options can be left at the defaults and click the **Next** button

- Click the **Next** button twice, check the "**I acknowledge that AWS CloudFormation might create IAM resources.**" box and finally the **Create stack** button

- Upon completion, please refer to the `Enable EBS Snapshots` section of the `CloudFormation Installer Kit` documentation pdf for the next steps. If you do not have this file, please request it via support@datarobot.com

---

## Sample Event Configuration

```bash
{
  "RequestType": "Create",
  "StackName": "<stack name>"
}
```

## Command line reference

A mostly working set of commands to this stack from teh comand line with the AWS cli.

**Remember:** You must update the vars below to work for your emvironment.

### Working EBS Scheduler command

```bash
s3bucket=$1
instances=$2
region="${3:-us-east-1}"
owner="${4:-`whoami`}"

# This line removes any '.' from the string given above
owner="${owner//./}"

# Other variables used later
header="DataRobot-${owner}"
stackid=`od -An -N5 -i /dev/random | sed 's/[ \-]//g'`
stackname=${header}-Scheduler-${stackid}

# Make the stack
aws cloudformation create-stack --stack-name ${stackname} \
  --region ${region} \
  --template-url https://s3.amazonaws.com/${s3bucket}/Scheduler/EBS-SnapShot-Scheduler-Stack.yaml \
  --capabilities CAPABILITY_IAM \
  --parameters \
    ParameterKey=S3Bucket,ParameterValue=${s3bucket} \
    ParameterKey=Instances,ParameterValue=${instances}
  --tags \
    Key=owner,Value=${owner} \
    Key=Name,Value=${stackname} \
```

## Copyright

Copyright &copy; DataRobot 2020
