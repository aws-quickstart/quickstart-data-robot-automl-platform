# The DataRobot CloudFormation Kit Administration

## This page is for DataRobot only

Please refer to <https://trello.com/b/ePtrh0yA/customer-cloud-deployment-automation> for the status
For the source code, please refer to: <https://github.com/datarobot/cloudformation_installer/tree/base-scaling-stack>

<https://docs.google.com/document/d/1FffmKNuQMQD3lATAlnISvNuD_dKytKuwlsv8_7BGI30/edit#>

**This page is for the DataRobot CloudFormation Kit generation, distribution and how to debug the kit.**

```bash
eval $(dram token --duration 999 --profile Support)
```

## Available options

The options listed below are referencable in the Single Node and Enterprise Sample Config Guide (PoC, PreProd/UAT, Enterprise)

- **SingleNode:** Run DataRobot on a single small node
- **PoC:** Build a DataRobot PoC cluster
- **PreProd:** Generates a Pre-Production cluster, ready for further customization
- **Enterprise:** Provisions the DataRobot cluster using S3 storage, modeler autoscaling, DPE and App node load balancers

## Building The Kits

Please see the process below for how to generate the packages you can send to a customer

| Command | \|| Results |
|:-------|-|:----------|
| ./kit_builder.sh SingleNode \<Version \# \> | \| | ./tmp/DataRobot_CloudFormation_SingleNode_Kit.tar.gz |
| ./kit_builder.sh PoC \<Version \# \> | \| | ./tmp/DataRobot_CloudFormation_Poc_Kit.tar.gz |
| ./kit_builder.sh PreProd \<Version \# \> | \| | ./tmp/DataRobot_CloudFormation_PreProd_Kit.tar.gz |
| ./kit_builder.sh Enterprise \<Version \# \> | \| | ./tmp/DataRobot_CloudFormation_ENTERPRISE_Kit.tar.gz |

You can then distribute the tarball to the correct person via a ticket for tracking

### Building the AutoScaling Kit


### Building the EBS SnapShot Scheduling Kit

```bash
scheduler_kit_builder.sh
```

**Please Note:**

There is also a tool called `build_all_the_kits.sh` that will generate all the kits, including Scheduling, AutoScaling and
LoadBalancers when used like so:

```bash
./build_all_the_kits.sh X.Y.Z

where X.Y.Z = the datarobot version number
```

## Environment Map

| Environment/Type | AppData | App | Data | Modeling | DPE | ModMan |
|------------------:|:---------:|:-----:|:------:|:----------:|:-----:|:-----:|
| SingleNode       | 1       |     |      |          |     |     |
| PoC              | 1       |     |      | 4        | 1   | 1   |
| PreProd          |         | 1   | 1    | 4        | 1   | 1   |
| Enterprise       |         | 2   | 3    | 2/1      | 2   | 2   |

## Gotcha

Before you try to execute the stack a second time, you must delete the "key" directory
in the istallation bucket in S3. If you don't the system could end up in a bad state and
is used as a way to prevent the user from re-creating the DataRobot environment at will.

## TODO

- Finsh wiring up the callback

## Test files

SUSY-3M.csv - target: "Class" - 958 MB - Dataset from simulated super symmetric particles and background noise.  From the UCI machine learning repository.
https://s3.amazonaws.com/datarobot_data_science/test_data/SUSY-3M.csv

Foursquare-daytime.csv - target: "is_daytime" - 4.5 GB - A dataset of Foursquare checkins, with the goal of predicting whether or not the checkin occurred during day or night. Contains numeric data, low cardinality categorical data, high cardinality categorical, text, and geographic data.
https://s3.amazonaws.com/datarobot_data_science/test_data/Foursquare-daytime.csv

## Command line testing

A mostly working set of commands to test a specific stack.
Please note that this assumes you have a working bucket's worth of files
and named one of them config.yaml

**Remember:** You must update the vars below to work for your emvironment.

### Working AutoScaling

```bash
subnet=$1
adnid=$2
moid=$3
s3bucket=$4
region="${5:-us-east-1}"
owner="${6:-`whoami`}"

# This line removes any '.' from the string given above
owner="${owner//./}"

# Other variables used later
header="DataRobot-${owner}"
stackid=`od -An -N5 -i /dev/random | sed 's/[ \-]//g'`

# Make the stack
aws cloudformation create-stack --stack-name ${header}-AutoScaling-${stackid} \
  --region ${region} \
  --template-url https://s3.amazonaws.com/${s3bucket}/AutoScaling-Stack.yaml \
  --capabilities CAPABILITY_IAM \
  --parameters \
    ParameterKey=S3Bucket,ParameterValue=${s3bucket}
```

### PoC stack call

```bash
stackid=$(od -An -N5 -i /dev/random | sed 's/[ \-]//g')
stackname="datarobot-CreateStack-${stackid}"
s3bucket='datarobot-denniswhitney-poc-6.3.2-cloudformation'
usestack=Master-Create-Stack.yaml
region=us-east-1
version='6.3.2'
sshkey='AWSDennisWhitney'
subnet='subnet-0ce21822'
vpc='vpc-f3dceb88'
cidrblock='10.215.20.0/22'
externalipaddress='208.127.227.1/32'
clustertype=PoC
owner=$(whoami)
downloadurl="<Your download url goes here!>"

aws cloudformation create-stack --stack-name ${stackname} \
  --region ${region} \
  --template-url https://s3.amazonaws.com/${s3bucket}/${usestack} \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameters \
    ParameterKey=S3Bucket,ParameterValue=${s3bucket} \
    ParameterKey=DRVersion,ParameterValue=${version} \
    ParameterKey=SSHKey,ParameterValue=${sshkey} \
    ParameterKey=Subnet,ParameterValue=${subnet} \
    ParameterKey=VpcId,ParameterValue=${vpc} \
    ParameterKey=Region,ParameterValue=${region} \
    ParameterKey=CidrBlock,ParameterValue=${cidrblock} \
    ParameterKey=ExternalIPAddress,ParameterValue=${externalipaddress} \
    ParameterKey=ClusterType,ParameterValue=${clustertype} \
    ParameterKey=DownloadURL,ParameterValue=${downloadurl} \
  --tags \
    Key=environment,Value=DataRobot-TEST-PoC \
    Key=cost_center,Value=DataRobot-TEST-PoC-cost_center \
    Key=owner,Value=${owner} \
    Key=Name,Value=${usestack}
```

### Working SecurityGroup Stack call

```bash
stackid=`od -An -N5 -i /dev/random | sed 's/[ \-]//g'`
stackname="datarobot-securitygroupstack-${stackid}"
s3bucket=datarobot-test-poc-X.Y.Z-cloudformation # Update as required
usestack=SecurityGroup-Stack.yaml
vpc=vpc-abcd     # Update as required
cidrblock="10.X.0.0/16"        # Update as required
externalipaddress="A.B.C.D/32" # Update as required
owner=`whoami`   # Update as required
region=us-east-1 # Update as required

aws cloudformation create-stack --stack-name ${stackname} \
  --region ${region} \
  --template-url https://s3.amazonaws.com/${s3bucket}/${usestack} \
  --parameters \
    ParameterKey=MainStack,ParameterValue=${stackname} \
    ParameterKey=VpcId,ParameterValue=${vpc} \
    ParameterKey=CidrBlock,ParameterValue=${cidrblock} \
    ParameterKey=ExternalIPAddress,ParameterValue=${externalipaddress} \
  --tags \
    Key=environment,Value=DataRobot-TEST-PoC \
    Key=cost_center,Value=DataRobot-TEST-PoC-cost_center \
    Key=owner,Value=${owner} \
    Key=Name,Value=${usestack} \
```

### IAM Role Stack call

```bash
stackid=$(od -An -N5 -i /dev/random | sed 's/[ \-]//g')
stackname="datarobot-iamrolestack-${stackid}"
s3bucket='datarobot-denniswhitney-poc-6.3.2-cloudformation'
usestack=IAM-PoC-Stack.yaml
region=us-east-1

aws cloudformation create-stack --stack-name ${stackname} \
  --region ${region} \
  --template-url https://s3.amazonaws.com/${s3bucket}/${usestack} \
  --capabilities CAPABILITY_IAM \
  --parameters \
    ParameterKey=MainStack,ParameterValue=${stackname} \
    ParameterKey=S3Bucket,ParameterValue=${s3bucket} \
  --tags Key=Name,Value=${usestack}
```

### Working EC2 Standalone Stack call

For best results, do the iam role stack and use that id here

```bash
stackid=`od -An -N5 -i /dev/random | sed 's/[ \-]//g'`
stackname="datarobot-ec2stack-${stackid}"
s3bucket=datarobot-test-poc-X.Y.Z-cloudformation # Update as required
usestack=EC2-Stack.yaml # Update as required
s3bucket=datarobot-test-poc-X.Y.Z-cloudformation # Update as required
version=X.Y.Z       # Update as required
sshkey=<My SSH Key> # Update as required
subnet=subnet-1234  # Update as required
sg=sg-abc123        # Update as required
os=ami-321cba       # Update as required
region=us-east-1    # Update as required
clustertype=PoC     # Update as required
iamprofile=<IAM Profile to apply to these nodes>
owner=`whoami`

aws cloudformation create-stack --stack-name ${stackname} \
  --region ${region} \
  --template-url https://s3.amazonaws.com/${s3bucket}/${usestack} \
  --parameters \
    ParameterKey=MainStack,ParameterValue=${stackname} \
    ParameterKey=InstallationBucket,ParameterValue=${s3bucket} \
    ParameterKey=DRVersion,ParameterValue=${version} \
    ParameterKey=SSHKey,ParameterValue=${sshkey} \
    ParameterKey=SubnetId,ParameterValue=${subnet} \
    ParameterKey=SecurityGroupIds,ParameterValue=${sg} \
    ParameterKey=ImageId,ParameterValue=${os} \
    ParameterKey=InstanceType,ParameterValue=r5.2xlarge \
    ParameterKey=RunScript,ParameterValue=setup-parent.sh \
    ParameterKey=NodeVolumeSize,ParameterValue=40 \
    ParameterKey=DataVolumeSize,ParameterValue=2048 \
    ParameterKey=Region,ParameterValue=${region} \
    ParameterKey=ClusterType,ParameterValue=${clustertype} \
    ParameterKey=IAmProfile,ParameterValue=${iamprofile} \
  --tags \
    Key=environment,Value=DataRobot-TEST-PoC \
    Key=cost_center,Value=DataRobot-TEST-PoC-cost_center \
    Key=owner,Value=${owner} \
    Key=Name,Value=Test-AppDataNodeStack \
```

## 5.3.2

### Single node, no as, no lb

```bash
./DataRobot_CloudFormation_Kit.py create --environment SingleNode --region us-east-1 --sshkey MyTestingKeyPair --vpc vpc-f3dceb88 --subnet subnet-0ce21822 --cidr "10.215.0.0/16" --externalip "108.7.59.117/32" --secretsenforced --encrypted --encryptionkey "fab14ea6-cea4-4ce5-ac58-56a6869f2f97" --owner denniswhitney --url "https://s3.amazonaws.com/datarobot-enterprise-releases/promoted/5.3.2/dockerized/DataRobot-RELEASE-5.3.2.tar.gz?AWSAccessKeyId=AKIAISWVSILRYQ5V5BNQ&Expires=1580701103&Signature=339LPLOg2FkW9HeRcWXx2vtpmCc%3D"
```

### PoC, no as, no lb

```bash
./DataRobot_CloudFormation_Kit.py create --environment PoC --region us-east-1 --sshkey MyTestingKeyPair --vpc vpc-f3dceb88 --subnet subnet-0ce21822 --cidr "10.215.0.0/16" --externalip "108.7.59.117/32" --secretsenforced --encrypted --encryptionkey "fab14ea6-cea4-4ce5-ac58-56a6869f2f97" --owner denniswhitney --url "https://s3.amazonaws.com/datarobot-enterprise-releases/promoted/5.3.2/dockerized/DataRobot-RELEASE-5.3.2.tar.gz?AWSAccessKeyId=AKIAISWVSILRYQ5V5BNQ&Expires=1580701103&Signature=339LPLOg2FkW9HeRcWXx2vtpmCc%3D" --usescheduler --debug
```

### PreProd, yes AS, yes scheduler

```bash
./DataRobot_CloudFormation_Kit.py create --environment PreProd --region us-east-1 --sshkey MyTestingKeyPair --vpc vpc-f3dceb88 --subnet subnet-0ce21822 --cidr "10.215.0.0/16" --externalip "108.7.59.117/32" --secretsenforced --encrypted --encryptionkey "fab14ea6-cea4-4ce5-ac58-56a6869f2f97" --owner denniswhitney --url "https://s3.amazonaws.com/datarobot-enterprise-releases/promoted/5.3.2/dockerized/DataRobot-RELEASE-5.3.2.tar.gz?AWSAccessKeyId=AKIAISWVSILRYQ5V5BNQ&Expires=1580701103&Signature=339LPLOg2FkW9HeRcWXx2vtpmCc%3D" --usescheduler --debug --useautoscaling
```

### Enterprise, yes as, yes scheduler, yes lb, yes ebs ss

```bash
./DataRobot_CloudFormation_Kit.py create --environment Enterprise --region us-east-1 --sshkey MyTestingKeyPair --vpc vpc-f3dceb88 --subnet subnet-0ce21822 --subnet subnet-1312d074 --subnet subnet-ec42bbb0 --cidr "10.215.0.0/16" --externalip "108.7.59.117/32" --secretsenforced --encrypted --encryptionkey "fab14ea6-cea4-4ce5-ac58-56a6869f2f97" --owner denniswhitney --url "https://s3.amazonaws.com/datarobot-enterprise-releases/promoted/5.3.2/dockerized/DataRobot-RELEASE-5.3.2.tar.gz?AWSAccessKeyId=AKIAISWVSILRYQ5V5BNQ&Expires=1580701103&Signature=339LPLOg2FkW9HeRcWXx2vtpmCc%3D" --debug --useautoscaling --usescheduler --usedpelb
```

## Copyright

Copyright &copy; DataRobot 2020
