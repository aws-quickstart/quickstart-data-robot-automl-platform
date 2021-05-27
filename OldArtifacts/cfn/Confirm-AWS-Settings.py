#!/usr/bin/env python

###########################################################################
#  Copyright 2020 DataRobot Inc. All Rights Reserved.                     #
#                                                                         #
#  This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES       #
#  OR CONDITIONS OF ANY KIND, express or implied.                         #
###########################################################################

import argparse
import boto3
from botocore.exceptions import ClientError

import datetime
import os
import sys
import re
import random
import requests

from timeit import default_timer as timer

# https://magmax.org/python-inquirer/usage.html
import inquirer

# https://pypi.org/project/netaddr/
import netaddr
from netaddr import IPNetwork
from netaddr import IPSet

try:
  import pwd
except ImportError:
  import getpass
  pwd = None

# Environment types to prepare for
#envs = [ "SingleNode", "PoC", "PreProd", "Enterprise", "DataManagement", "QuickStart" ]


actions = [ "create", "restore", "upgrade" ]

# Set up the cluster types
cluster = {}
cluster["SingleNode"] = { "AppDataNode" }
cluster["PoC"] = [ "AppDataNode", "ModelManagement", "ESNode" ]
cluster["PreProd"] = [ "AppNode", "DataNode", "ModelManagement", "ESNode" ]
cluster["Enterprise"] = [ "AppNode1", "DataNode1", "DataNode2", "DataNode3", "ModelManagement1", "ModelManagement2", "ESNode1", "ESNode2", "ESNode3" ]
cluster["QuickStart"] = [ "AppDataNode", "ModelManagement" ]

# Create the node type to key mapping
nodekey = {}
nodekey["AppDataNode"] = "app"
nodekey["AppNode"] = "app"
nodekey["AppNode1"] = "app"
nodekey["ModelManagement"] = "mm"
nodekey["ModelManagement1"] = "mm1"
nodekey["ModelManagement2"] = "mm2"
nodekey["ModelManagement3"] = "mm3"
nodekey["DataNode"] = "data"
nodekey["DataNode1"] = "data1"
nodekey["DataNode2"] = "data2"
nodekey["DataNode3"] = "data3"
nodekey["ESNode"] = "es"
nodekey["ESNode1"] = "es1"
nodekey["ESNode2"] = "es2"
nodekey["ESNode3"] = "es3"

# Return the username in a portable way with non-alpha removed
def currentuser():
    username = None
    if pwd:
        username = pwd.getpwuid(os.geteuid()).pw_name
    else:
        username = getpass.getuser()
    return re.sub( r'\W+', '', username )

def checkS3( region ):

    # Get the S3 client
    s3client = boto3.client('s3')

    # Generate the s3 bucket name
    bucketname="datarobot-testbucket-%s" % random.randint(1,10000)

    print("= Checking permissions to manipulate '%s' in region: %s" % ( bucketname, region ))

    # Set the temporary dir name
    dirname = "./tmp/"

    # Set the file name
    filename = "datarobot.txt"

    downloadfile = os.path.join( dirname, "datarobot2.txt") 

    fullfile = os.path.join( dirname, filename)

    # Set the file text
    filetext = "One DataRobot to rule them all!"

    # Create temp Directory
    try:
        os.mkdir(dirname)
        print("== Created: %s" %( dirname ) )
    except FileExistsError as fe:
        print("== Directory %s already exists: %s" % (dirname, fe) )

    # Write the sample DataRobot file
    try:
        with open( fullfile,'w',encoding = 'utf-8') as file:
            file.write(filetext)
        print("== Wrote %s bytes to %s" % ( os.path.getsize(fullfile), fullfile))
    finally:
        file.close()

    if region == "us-east-1":
        # Create the test bucket
        response = s3client.create_bucket( Bucket=bucketname )
    else:
        # Create the test bucket
        response = s3client.create_bucket( Bucket=bucketname, CreateBucketConfiguration={ 'LocationConstraint': region } )

    print("= Created S3 bucket %s: %s" % (bucketname, response)) 

    # Upload and download a file to/from the bucket
    try:
        response = s3client.upload_file(fullfile, bucketname, filename)
        print("= Uploaded '%s' to '%s': %s" % (filename, bucketname, response))

        response = s3client.list_objects( Bucket=bucketname )
        print("= '%s' contains: %s" % (bucketname, response))

        response = s3client.download_file(bucketname, filename, downloadfile )
        print("= Downloaded '%s' from '%s': %s" % (downloadfile, bucketname, response))
        
        response = s3client.delete_object( Bucket=bucketname, Key=filename )
        print("= Removed remote file '%s/%s': %s" % (bucketname, filename, response))

    except ClientError as err:
        print("S3 CLIENT ERROR: %s" % (err))

    try: 
        response = s3client.delete_bucket( Bucket=bucketname )
        print("= Deleted S3 Bucket '%s': %s" %(bucketname, response))
    except ClientError as err:
        print("** ERROR **\nCould not delete bucket: '%s'!\nPlease contact your AWS group get get this removed.\nError Message: %s.\nResponse: %s" % ( bucketname, err, response))

    # Clean up
    try:
        os.unlink(fullfile)
        print("= Deleted local file: %s" %(fullfile))

        os.unlink(downloadfile)
        print("= Deleted local file: %s" %(downloadfile))

        os.rmdir(dirname)
        print("= Deleted local directory: %s" %(dirname))
    except OSError as err:
        print("ERROR: %s" % (err) )

def getCmdString(answers):
    cmds = ""
    # print("Answers: %s" % answers) # debug
    for key in answers:
        ## Debug line
        # print("key: %s | value: %s | type: %s" %(key, answers[key], type( answers[key] ).__name__))  # Debug

        # Apply the action
        if key == 'action':
            cmds += "%s " % answers[key]

        # Check the strings
        elif type( answers[key] ).__name__ == 'str':
            if key == "url" or key == "cidr" or key == "externalip":
                cmds += '--%s "%s" ' % (key, answers[key])
            elif key == "encryptionkey":
                if len( str(answers[key]) ) != 0 and answers['encrypted'] == True:
                    cmds += '--%s "%s" ' % (key, answers[key])
            else:
                cmds += '--%s %s ' % (key, answers[key])
        # Check any lists, order counts here
        elif type( answers[key] ).__name__ == 'list':
            for sub in answers[key]:
                cmds += '--%s %s ' % (key, sub)
        elif type( answers[key] ).__name__ == 'bool' and answers[key] == True:
            cmds += '--%s ' % (key)

    return cmds

def main():

    # Start timer
    start = timer()

    parser = argparse.ArgumentParser(
        description="Does AWS testing to ensure the user can execute the CloudFormation stack. Warning, can cause clutter if you do not have S3 bucket delete permissions.",
        epilog="DataRobot Copyright 2019"
    )
    
    parser.add_argument( '--checks3', action='store_true', help="Confirm S3 Bucket creation, modification and delete" )
    parser.add_argument( '--url', help="DataRobot download url provided by support@datarobot.com" )
    parser.add_argument( '--backuptype', help="What type of backup to configure.", choices=["none", "s3bucket", "ebssnapshot"], default="s3bucket" )
    parser.add_argument( '--s3bucket', help="S3Bucket url" )
    parser.add_argument( '--sshkey', help="SSH Private key name" )

    args = parser.parse_args()

    # Create the EC2 client
    client = boto3.client('ec2')

    # Create the KMS client
    kmsclient = boto3.client('kms')

    # S3Bucket client
    # Retrieve the list of existing buckets
    s3client = boto3.client('s3')

    # Announce what is going on
    print("=== Started %s ====" %( os.path.basename(sys.argv[0])))

    try:
        questions = [
           inquirer.List('action', message='Cluster action:', choices=actions, default="create"),
           inquirer.List('environment', message='Please define the cluster type:', choices=cluster.keys(), default="PoC"),
           inquirer.List('region', message='Please select your region', choices=[region['RegionName'] for region in client.describe_regions()['Regions']], default="us-east-1"),
           inquirer.List('sshkey', message='Select SSH Key', choices=[key['KeyName'] for key in client.describe_key_pairs()['KeyPairs']], default=args.sshkey ),
           inquirer.List('vpc', message='Select VPC', choices=[vpc['VpcId'] for vpc in client.describe_vpcs()['Vpcs']] ),
           inquirer.List('backuptype', message='Type of backup to configure:', choices=["none", "s3bucket", "ebssnapshot"], default="s3bucket")
        ]

        answers = inquirer.prompt(questions)

        if answers['backuptype'] == 's3bucket':
            questions.append( inquirer.List('backupbucket', message='S3Bucket name',  choices=[bucket['Name'] for bucket in s3client.list_buckets()["Buckets"]], default=args.s3bucket ) )
            questions.append( inquirer.Text('s3backupdir', message='backup directory name', default="backup_files" ) )

        # If not create, get the list of snapshots
        if answers['action'] != 'create':

            if answers['backuptype'] == 's3bucket':
                 print("Using backuptype: %s" %( answers['backuptype'] ))

            elif answers['backuptype'] == 'ebssnapshot':

                print("Looking for the '%s' Snapshots" %( answers['environment'] ))
                response = client.describe_snapshots()['Snapshots']

                for node in cluster[ answers['environment'] ]:
                    snaps = []
                    for obj in response:
                        if 'Tags' in obj:
                            for tag in obj['Tags']:
                                if "%s-Data-Volume-SnapShot" % node == tag['Value']:
                                    #print("%s %s %s" % (node, obj['SnapshotId'], (obj['Description']).replace( 'by EBSSnapshotScheduler ', '' ) ) )
                                    snaps.append( "%s %s %s" % (node, obj['SnapshotId'], (obj['Description']).replace( 'by EBSSnapshotScheduler ', '' ) ) )                
                    answers[ nodekey[node] ] = inquirer.list_input( 'Select %s snapshot:' % node, choices=snaps )
                    answers[ nodekey[node] ] = (answers[ nodekey[node] ]).split(" ")[1]
            else:
                print("Using unknown backuptype: %s | Answers: '%s'" %( answers['backuptype'], answers ))

        # Get the list of subnets that are actually available
        filters = [
            {'Name':'state', 'Values':['available']},
            {'Name':'vpc-id', 'Values':[answers['vpc']]}
        ]
        subnetlist = [subnet['SubnetId'] for subnet in client.describe_subnets(Filters=filters)['Subnets']]

        if answers['environment'] == 'Enterprise':
            # Get subnet list and check for 3
            answers['subnet'] = inquirer.checkbox("Choose 3 subnets for Enterprise", choices=subnetlist )
            if len(answers['subnet']) != 3:
                raise ValueError("Must use 3 subnets when building an Enterpise cluster")
            
            iplist = []
            for sn in answers['subnet']:
                filters = [{'Name':'subnet-id', 'Values':[ sn ]}]
                cidr = client.describe_subnets(Filters=filters)['Subnets'][0]['CidrBlock']
                iplist.append( IPNetwork(cidr) )
            answers['cidr'] = inquirer.text(message="Generated Cidr Block.\nIf you see multiple blocks, reduce them to the common root. (ie: A.B.0.0/16)", default=netaddr.cidr_merge(iplist) )

        else:
            answers['subnet'] = inquirer.list_input("Select a subnet", choices=subnetlist )
            filters = [{'Name':'subnet-id', 'Values':[ answers['subnet'] ]}]
            answers['cidr'] = inquirer.text(message="Generated Cidr Block", default=client.describe_subnets(Filters=filters)['Subnets'][0]['CidrBlock'] )

        # Get the IP of the network executing the cloudformation template
        answers['externalip'] = inquirer.text(message="Configure for access from:", default="%s/32" % requests.get("http://whatismyip.akamai.com/").text )

        # Get secret enforcement
        answers['secretsenforced'] = inquirer.confirm(message="Enable secret enforcement?", default=True )

        # Ask for the KMS key
        answers['encrypted'] = inquirer.confirm("Use KMS key on the DataRobot volume?", default=False)
        answers['encryptionkey'] = ""
        if answers['encrypted']:
            answers['encryptionkey'] = inquirer.list_input("Choose KMS Key", choices=[kmskey['KeyId'] for kmskey in kmsclient.list_keys()['Keys']] )

        # Get the username
        answers['owner'] = inquirer.text(message="Who is the owner of this cluster?", default=currentuser() )

        # Enable the Scheduler?
        answers['usescheduler'] = inquirer.confirm(message="Enable the EBS Snapshot Scheduler for this cluster?", default=False )

        # Use AutoScaling?
        answers['useautoscaling'] = inquirer.confirm(message="Enable Auto Scaling for this cluster?", default=False )

        if answers['useautoscaling'] == False:
            answers['storagetype'] = inquirer.list_input("Select Storage Type:", choices=[ 'gluster', 'minio', 's3bucket' ], default='s3bucket' )

        # # If not restore, get the url
        # if answers['action'] != 'restore':
        #     # Get the downlaod url
        answers['url'] = inquirer.text(message="DataRobot Download URL:", default=args.url )

        print("===========================================================")

        if args.checks3 == True:
            print("Checking S3 permissions in %s" %( answers['region'] ) )
            checkS3( answers['region'] )
            print("===========================================================")

        print("Be sure to update the --owner and --url parameters as required")
        print("===========================================================")
        print("./DataRobot_CloudFormation_Kit.py %s" % getCmdString(answers))

    except ValueError as e:
        print("Invalid parameter error: %s" % e)
        quit()
    except Exception as e:
        #logging all the others as warning
        print("Unexpected exception: %s" % e)
        quit()
    except KeyboardInterrupt as e:
        print("User pressed Ctrl-C, quitting.")
        quit()

    print("===========================================================")
    print("Buildout completed in %s" % ( str(datetime.timedelta(seconds=timer() - start)) ))


if __name__ == '__main__':
    main()