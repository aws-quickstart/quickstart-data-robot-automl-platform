#!/usr/bin/env python

###########################################################################
#  Copyright 2020 DataRobot Inc. All Rights Reserved.                     #
#                                                                         #
#  This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES       #
#  OR CONDITIONS OF ANY KIND, express or implied.                         #
###########################################################################

import argparse
import boto3
import botocore
from botocore.exceptions import ClientError
import datetime
import os
from urllib.parse import urlparse
import sys
import re
import random
import requests
from timeit import default_timer as timer
import logging
import zipfile
from zipfile import BadZipfile
import json

try:
  import pwd
except ImportError:
  import getpass
  pwd = None

#setup simple logging for INFO.
logger = logging.getLogger()
#logger.setLevel(logging.INFO)

# Environment types to prepare for
envs = [ "SingleNode", "PoC", "PreProd", "Enterprise", "QuickStart" ]
regions = [ "ap-northeast-1", "ap-northeast-2", "ap-south-1", "ap-southeast-1", "ap-southeast-2", "ca-central-1", "eu-central-1", "eu-north-1", "eu-west-1", "eu-west-2", "eu-west-3", "sa-east-1", "us-east-1", "us-east-2", "us-west-1", "us-west-2" ]

actions = [ "create", "describe", "restore", "delete"]

def whatsMyIp():
    url = "http://whatismyip.akamai.com/"
    text = requests.get( url ).text
    return "%s/32" % text

# Return the username in a portable way
def currentuser( alpha = False ):
    username = None
    if pwd:
        username = pwd.getpwuid(os.geteuid()).pw_name
    else:
        username = getpass.getuser()
    if alpha:
        return re.sub( r'\W+', '', username )
    return username

def makeArgs():
    parser = argparse.ArgumentParser(
        prog='PROG',
        usage='%(prog)s [options]',
        # formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        formatter_class=argparse.RawTextHelpFormatter,
        # formatter_class=argparse.RawDescriptionHelpFormatter,
        description="""Executes the CloudFormation template create, describe, restore or delete functions.

By default will build an S3 bucket named: 
<stackname>-<owner>-<environment>-<drversion>-cloudformation

Names the stack:
datarobot-<owner>-<environment>

If debug, <environment> = <environment>-<5 digit key>

Warning, can cause clutter if you do not have S3 bucket delete permissions.""",
        epilog="DataRobot Copyright 2020"
    )

    subparsers = parser.add_subparsers( help='commands', dest='action' )

    # Add the create command
    create = subparsers.add_parser('create', help="Create the DataRobot environment")
    create.add_argument("--environment", help="Environment type to provision. Default: %(default)s", choices=envs, default="PoC" )
    create.add_argument("--region", help="AWS Region for deployment. Default: %(default)s", choices=regions, default="us-east-1" )
    create.add_argument("--sshkey", help="SSH key used for connectivity", required=True )
    create.add_argument("--vpc", help="Virtual Public Cloud for the cluster", required=True )
    create.add_argument("--subnet", help="Subnets to use", action='append', required=True )
    create.add_argument("--cidr", help="Subnet Cidr Block, ex: 10.1.0.0/16 or 10.1.2.0/22", required=True )
    create.add_argument("--externalip", help="The local ip, ex: 1.2.3.4/32." )
    create.add_argument("--secretsenforced", help="Enable secrets", action='store_true' )
    create.add_argument("--encrypted", help="Use a KMS key", action='store_true' )
    create.add_argument("--encryptionkey", help="KMS Key Id or Alias, if left blank, will use default.", default="" )
    create.add_argument("--owner", help="Name of the entity that will 'own' this DataRobot cluster. Default: %(default)s", metavar=currentuser(True), default=currentuser(True), required=True )
    create.add_argument("--url", help="URL of the DataRobot download package", required=True )
    create.add_argument("--deployname", help="Override default name of this deployment" )
    create.add_argument("--publicip", help="Associate a Public IP to the app node and dpe?", action='store_true' )
    create.add_argument("--os", help="Operating System for cluster. Default: %(default)s", choices=[ "rhel", "centos"], default="centos" )
    create.add_argument("--s3bucket", help="S3 bucket name used with CloudFormation.", metavar="<stackname>-<owner>-<environment>-<drversion>-cloudformation" )
    create.add_argument("--s3storagedir", help="Directory for vertex files. Default: %(default)s", metavar="datarobot_storage", default="datarobot_storage" )
    create.add_argument("--stackname", help="Cloudformation stack name prefix. Default: %(default)s", metavar="DataRobot", default="DataRobot" )
    create.add_argument("--tag", help="1 tag per switch. Owner and builder automatically applyied. ex: '--tag Foo=Bar'", action='append')
    create.add_argument("--debug", help="Allows for a debug version of the given environment. All objects wil have an id attached.", action='store_true' )
    create.add_argument("--usescheduler", help="Deploy EBS SnapShot functionality", action='store_true' )
    create.add_argument("--useautoscaling", help="Deploy AutoScaling functionality, must not use minio", action='store_true' )
    create.add_argument("--usedpelb", help="Deploys 3 DPE to be ready for the DPE-LoadBalancer-Stack", action='store_true' )
    create.add_argument("--storagetype", help="How to save the data in this cluster. If using AutoScaling, must not use minio", choices=[ "minio", "s3bucket", "gluster"], default="s3bucket" )
    create.add_argument("--backuptype", help="Backup type to restore from", choices=[ "none", "s3bucket", "ebssnapshot"], required=False )
    create.add_argument("--backupbucket", help="S3 Bucket where backupo is stored", required=False )
    create.add_argument("--s3backupdir", help="S3 Bucket sub directory", default="backup_files", required=False )

    # Add the describe command
    describe = subparsers.add_parser('describe', help="Describe the DataRobot environment")
    describe.add_argument("--stackname", help="CloudFormation stack name." )
    describe.add_argument("--useautoscaling", help="Look For AutoScaling functionality", action='store_true' )
    describe.add_argument("--storagetype", help="Look for file storage type", choices=[ "minio", "s3bucket", "gluster"], default="s3bucket" )
    describe.add_argument("--debug", help="Allows for a debug version of the given environment. All objects wil have an id attached.", action='store_true' )

    # Add the restore command
    restore = subparsers.add_parser('restore', help="Restore a DataRobot cluster from a set of snapshots")
    restore.add_argument("--deployname", help="Override default name of this deployment" )
    restore.add_argument("--environment", help="Environment type to provision. Default: %(default)s", choices=envs, default="Enterprise" )
    # restore.add_argument("--drversion", help="DataRobot version to restore" ) # , required=True
    restore.add_argument("--owner", help="Name of the entity that will 'own' this DataRobot cluster. Default: %(default)s", metavar=currentuser(True), default=currentuser(True), required=True )
    restore.add_argument("--debug", help="Allows for a debug version of the given environment. All objects wil have an id attached", action='store_true' )
    restore.add_argument("--app", help="SnapShotId for AppNode1" ) # , required=True
    restore.add_argument("--data", help="SnapShotId for DataNode1", required=False )
    restore.add_argument("--data1", help="SnapShotId for DataNode2", required=False )
    restore.add_argument("--data2", help="SnapShotId for DataNode3", required=False )
    restore.add_argument("--mm", help="SnapShotId for Model Management Node 1", required=False ) #, required=True
    restore.add_argument("--mm1", help="SnapShotId for Model Management Node 2", required=False )
    restore.add_argument("--es", help="SnapShotId for ElasticSearch1", required=False ) #, required=True
    restore.add_argument("--es1", help="SnapShotId for ElasticSearch2", required=False )
    restore.add_argument("--es2", help="SnapShotId for ElasticSearch3", required=False )
    restore.add_argument("--s3bucket", help="S3 bucket name used with CloudFormation", metavar="<stackname>-<owner>-<environment>-<drversion>-cloudformation", required=True )
    restore.add_argument("--stackname", help="Cloudformation stack name prefix. Default: %(default)s", metavar="DataRobot", default="DataRobot" )
    restore.add_argument("--tag", help="Tag to apply to this stack. 1 tag per switch. Owner and script executer automatically applyied. ex: '--tag Foo=Bar'", action='append')
    restore.add_argument("--region", help="AWS Region to build in. Default: %(default)s", choices=regions, default="us-east-1" )
    restore.add_argument("--sshkey", help="SSH key used for connectivity", required=True )
    restore.add_argument("--vpc", help="Virtual Public Cloud for the cluster", required=True )
    restore.add_argument("--subnet", help="Subnets to use", action='append', required=True )
    restore.add_argument("--cidr", help="Cidr Block of IP's to use with the subnet. ex: 10.1.0.0/16 or 10.1.2.0/22", required=True )
    restore.add_argument("--externalip", help="The local cidr block, ex: 1.2.3.4/32." )
    restore.add_argument("--secretsenforced", help="Enable DataRobot secrets?", action='store_true' )
    restore.add_argument("--encrypted", help="Use a KMS key?", action='store_true' )
    restore.add_argument("--encryptionkey", help="KMS Key Id or Alias, if left blank, will use the default.", default="" )
    restore.add_argument("--publicip", help="Associate a Public IP to the app node and dpe?", action='store_true' )
    restore.add_argument("--os", help="Operating System for cluster. Default: %(default)s", choices=[ "rhel", "centos"], default="centos" )
    restore.add_argument("--s3storagedir", help="S3 bucket sub directory to save vertex files. Default: %(default)s", default="datarobot_storage" )
    restore.add_argument("--usescheduler", help="Deploy DataRobot EBS SnapShot functionality", action='store_true' )
    restore.add_argument("--useautoscaling", help="Deploy DataRobot AutoScaling functionality", action='store_true' )
    restore.add_argument("--storagetype", help="How to save the data in this cluster. If using AutoScaling, must not use minio", choices=[ "minio", "s3bucket", "gluster"], default="s3bucket" )

    restore.add_argument("--url", help="URL of the DataRobot download package", required=False )
    restore.add_argument("--backuptype", help="Backup type to restore from", choices=[ "none", "s3bucket", "ebssnapshot"], required=False )
    restore.add_argument("--s3backupdir", help="S3 Bucket sub directory", default="backup_files", required=False )

    # Add the delete command
    delete = subparsers.add_parser('delete', help="Delete the DataRobot environment")
    delete.add_argument("--stackname", help="CloudFormation stack name." )
    delete.add_argument("--useautoscaling", help="Look For AutoScaling functionality", action='store_true' )
    delete.add_argument("--storagetype", help="Look for file storage type", choices=[ "minio", "s3bucket", "gluster"], default="s3bucket" )
    delete.add_argument("--debug", help="Allows for a debug version of the given environment. All objects wil have an id attached.", action='store_true' )

    args = parser.parse_args()

    if args.debug == True:
        args.key = random.randint(1,10000)

    if args.action == 'create' or args.action == 'restore':

        # Start the tags list
        args.tags = []
        args.tags.append( { 'Key': 'builder', 'Value': currentuser() } )

        # Get the DR Version number based off the download url

        #if args.action == 'create':
        args.drversion = getDRVersionFromUrl(args.url)
        # Put drversion check and die if ""

        # CloudFormation Deployment name
        if "".__eq__(args.deployname):
            args.deployname = str.lower( "%s-%s-%s" % (args.stackname, args.owner, args.environment) )
            args.stackname = args.deployname

        if args.debug == True:
            args.stackname = "%s-%s" % (args.deployname, args.key)

        # S3 bucket to use for this process
        if args.action == 'create' and "".__eq__(args.s3bucket):
            args.s3bucket = str.lower( "%s-%s-cloudformation" % (args.deployname, args.drversion) )

        # Build out the CloudFormation stack url
        if args.action == 'restore':
            if args.environment == "Enterprise":
                args.templateurl = "https://s3.amazonaws.com/%s/Master-%s-Stack.yaml" % (args.s3bucket, "Restore-Enterprise")
            else:
                args.templateurl = "https://s3.amazonaws.com/%s/Master-%s-Stack.yaml" % (args.s3bucket, "Restore")
        
        elif args.action == 'create':
            if args.environment == "Enterprise":
                args.templateurl = "https://s3.amazonaws.com/%s/Master-%s-Stack.yaml" % (args.s3bucket, "Create-Enterprise")
            else:
                args.templateurl = "https://s3.amazonaws.com/%s/Master-%s-Stack.yaml" % (args.s3bucket, "Create")
        else:
            args.templateurl = "https://s3.amazonaws.com/%s/Master-%s-Stack.yaml" % (args.s3bucket, args.environment)

        # Add the tags
        args.tags.append( { 'Key': 'owner', 'Value': args.owner } )
        if type( args.tag ).__name__ != 'NoneType' and len(args.tag) > 0:
            for t in args.tag:
                t = t.split("=")
                args.tags.append( { 'Key': t[0], 'Value': t[1] } )

        # Add the metric namespace name
        args.metricnamespace = "DataRobot/AutoScaling/%sTesting" % (args.owner)

    return args

# Extracts the DataRobot version number from the download file name
def getDRVersionFromUrl(url):
    """Get the DataRobot version string from the DataRobot download URL

    :param url: string
    :return: the version number string
    """
    try:
        file = os.path.basename( urlparse(url).path )
        found = re.search('DataRobot-RELEASE-(.*).tar.gz', file, re.IGNORECASE)
        if found:
            return found.group(1)
        else:
            logging.error("Bad url patter! filename must be of pattern: DataRobot-RELEASE-(.*).tar.gz")
            quit()
    except Exception as e:
        logging.fatal("Unexpected exception: %s" % e)

def yes_or_no(question):
    """Ask the user yes or no

    :param question: string the question to ask the user
    :return: true on yes, false on no
    """
    answer = input(question + "(y/n): ").lower().strip()
    print("")
    while not(answer == "y" or answer == "yes" or answer == "n" or answer == "no"):
        print("Input yes or no")
        answer = input(question + "(y/n):").lower().strip()
        print("")
    if answer[0] == "y":
        return True
    else:
        return False

def getParams( args ):
    """Builds the Parameter set that is passed to the CloudFormation template

    :param args: object
    :return: Properly formatted parameter set
    """
    params = []

    params.append( { 'ParameterKey': 'S3Bucket', 'ParameterValue': args.s3bucket } )
    params.append( { 'ParameterKey': 'OperatingSystem', 'ParameterValue': args.os } )
    params.append( { 'ParameterKey': 'SSHKey', 'ParameterValue': args.sshkey } )
    params.append( { 'ParameterKey': 'Region', 'ParameterValue': args.region } )
    params.append( { 'ParameterKey': 'VpcId', 'ParameterValue': args.vpc } )
    params.append( { 'ParameterKey': 'Subnet', 'ParameterValue': args.subnet[0] } )
    params.append( { 'ParameterKey': 'PublicIpAddress', 'ParameterValue':("%s" % args.publicip).lower() } )
    params.append( { 'ParameterKey': 'MetricNamespace', 'ParameterValue': args.metricnamespace } )
   
    if args.environment == "Enterprise":
        params.append( { 'ParameterKey': 'Subnet1', 'ParameterValue': args.subnet[1] } )
        params.append( { 'ParameterKey': 'Subnet2', 'ParameterValue': args.subnet[2] } )
        params.append( { 'ParameterKey': 'StorageDir', 'ParameterValue': args.s3storagedir } )

        if args.usedpelb:
            params.append( { 'ParameterKey': 'UseDPELoadBalancer', 'ParameterValue': "true" } )

    params.append( { 'ParameterKey': 'CidrBlock', 'ParameterValue': args.cidr } )
    params.append( { 'ParameterKey': 'ExternalIPAddress', 'ParameterValue': args.externalip } )
    params.append( { 'ParameterKey': 'ClusterType', 'ParameterValue': args.environment } )

    params.append( { 'ParameterKey': 'DRVersion', 'ParameterValue': args.drversion } )

    params.append( { 'ParameterKey': 'DownloadURL', 'ParameterValue': args.url } )


    # if args.action != "restore":
    #     params.append( { 'ParameterKey': 'DownloadURL', 'ParameterValue': args.url } )
    # else:

    if args.backuptype == "s3bucket":
        params.append( { 'ParameterKey': 'UseS3BucketBackups', 'ParameterValue': "true" } )
        params.append( { 'ParameterKey': 'BackupDir', 'ParameterValue': ("%s" % args.s3backupdir) } )

    elif args.backuptype == "ebssnapshot": 

        if args.environment == "Enterprise":
            params.append( { 'ParameterKey': 'App1SnapShot', 'ParameterValue': ("%s" % args.app1) } )
            params.append( { 'ParameterKey': 'DataNode1SnapShot', 'ParameterValue': ("%s" % args.data1) } )
            params.append( { 'ParameterKey': 'DataNode2SnapShot', 'ParameterValue': ("%s" % args.data2) } )
            params.append( { 'ParameterKey': 'DataNode3SnapShot', 'ParameterValue': ("%s" % args.data3) } )
            params.append( { 'ParameterKey': 'ModelManagement1SnapShot', 'ParameterValue': ("%s" % args.mm1) } )
            params.append( { 'ParameterKey': 'ModelManagement2SnapShot', 'ParameterValue': ("%s" % args.mm2) } )
        if args.environment == "QuickStart":
            params.append( { 'ParameterKey': 'AppSnapShot', 'ParameterValue': ("%s" % args.app) } )
            params.append( { 'ParameterKey': 'DataNodeSnapShot', 'ParameterValue': ("%s" % args.data) } )
            params.append( { 'ParameterKey': 'ModelManagementSnapShot', 'ParameterValue': ("%s" % args.mm) } )
        if args.environment == "PoC":
            params.append( { 'ParameterKey': 'AppDataSnapShot', 'ParameterValue': ("%s" % args.app1) } )
            params.append( { 'ParameterKey': 'ModelManagementSnapShot', 'ParameterValue': ("%s" % args.mm1) } )
        if args.environment == "SingleNode":
            params.append( { 'ParameterKey': 'AppDataSnapShot', 'ParameterValue': ("%s" % args.app1) } )


    if args.debug:
        params.append( { 'ParameterKey': 'Debug', 'ParameterValue': ("%s" % "true") } )

    params.append( { 'ParameterKey': 'Encrypted', 'ParameterValue': ("%s" % args.encrypted).lower() } )
    params.append( { 'ParameterKey': 'EncryptionKey', 'ParameterValue': args.encryptionkey } )
    params.append( { 'ParameterKey': 'SecretsEnforced', 'ParameterValue': ("%s" % args.secretsenforced).lower() } )
    params.append( { 'ParameterKey': 'StorageType', 'ParameterValue': ( "%s" % args.storagetype ) } )

    if args.useautoscaling:
        params.append( { 'ParameterKey': 'UseAutoScaling', 'ParameterValue': ( "%s" % "true" ) } )
        params.append( { 'ParameterKey': 'AutoScaleGroup', 'ParameterValue': ( "%s-AutoScaling-Group" % args.stackname ) } )
        params.append( { 'ParameterKey': 'LaunchConfigName', 'ParameterValue': ( "%s-AutoScaling-LC" % args.stackname ) } )
        params.append( { 'ParameterKey': 'IAMPolicyName', 'ParameterValue': ( "%s-AutoScaling-IAMPolicy" % args.stackname ) } )
        params.append( { 'ParameterKey': 'ScaleUpAlarm', 'ParameterValue': ( "%s-ScaleUp-Modeling-Capacity-Alarm" % args.stackname ) } )
        params.append( { 'ParameterKey': 'ScaleDownAlarm', 'ParameterValue': ( "%s-ScaleDown-Modeling-Capacity-Alarm" % args.stackname ) } )
        params.append( { 'ParameterKey': 'ScaleUpPolicy', 'ParameterValue': ( "%s-ScaleUp-Policy" % args.stackname ) } )
        params.append( { 'ParameterKey': 'ScaleDownPolicy', 'ParameterValue': ( "%s-ScaleDown-Policy" % args.stackname ) } )
        params.append( { 'ParameterKey': 'WorkerImageName', 'ParameterValue': ( "%s-AutoScaledWorkerImage" % args.stackname ) } )
        params.append( { 'ParameterKey': 'WorkerName', 'ParameterValue': ( "%s-AutoScaledWorker" % args.stackname ) } )
    else:
        params.append( { 'ParameterKey': 'UseAutoScaling', 'ParameterValue': ( "%s" % "false" ) } )

    if args.environment != "SingleNode":
        params.append( { 'ParameterKey': 'UseScheduler', 'ParameterValue': ( "%s" % str(args.usescheduler).lower() ) } )

    logging.debug("Generated Parameters: %s" % ( params ))

    return params

def bucketExists(bucket):
    """Determine whether bucket exists and the user has permission to access it

    :param bucket: string
    :return: True if the referenced bucket_name exists, otherwise False
    """

    s3 = boto3.client('s3')
    try:
        response = s3.head_bucket(Bucket=bucket)
        logging.debug("*** Bucket Check Response: %s" % response)
    except ClientError as e:
        logging.debug(e)
        return False
    return True

def createBucket(bucket, region=None):
    """Create an S3 bucket in a specified region

    If a region is not specified, the bucket is created in the S3 default
    region (us-east-1).

    :param bucket: String S3 bucket to create
    :param region: String region to create bucket in, e.g., 'us-west-2'
    :return: True if bucket created, else False
    """

    try:

        if region == "us-east-1":
            region == None

        # Check if my bucket exists
        if bucketExists(bucket) is True:
            logging.debug("== Bucket '%s' already exists in '%s'" % (bucket, region) )
        else:
            if region is None:
                s3 = boto3.client( 's3' )
                response = s3.create_bucket(Bucket=bucket)
                logging.info("response: %s" % (response))

            else:
                s3 = boto3.client( 's3', region_name=region )
                response = s3.create_bucket( Bucket=bucket )

            logging.debug("== Create Bucket Response: %s" % response)
    
    except ClientError as e:
        logging.error(e)
        return False
    return True

def makeStorageDir( bucket, storagedir ):
    file = "readme.txt"
    s3 = boto3.resource('s3')
    try:
        s3.Bucket(bucket).upload_file( file, "%s/%s" % ( storagedir, file ) )
        logging.info("Created file storage directory: s3://%s/%s" % ( bucket, storagedir ))

    except ClientError as ce:
        logging.error("s3://%s/%s/%s creation error: %s" % ( bucket, storagedir, file, ce))
        return False

    return True

def uploadFiles( bucket, environment ):
    """Upload the files in the current diretory to the given bucket

    :param bucket: string
    :return: Number of files uploaded to the bucket
    """

    s3 = boto3.resource('s3')

    fcount = 0
    try:
        rootpath = "%s/" % os.getcwd()

        for path, subdirs, files in os.walk(rootpath):
            path = path.replace(rootpath, "").replace("\\","/")
            for file in files:

                if file == '.DS_Store' or path == 'debug':
                    continue

                # if environment == "Enterprise" and ( path == 'AutoScaling' or path == 'LoadBalancer' or "Scheduler" in path ):
                #     continue

                file = ("%s/%s" %(path, file)).strip("/")
                fullpath = "%s%s" %(rootpath, file)
                fcount += 1
                s3.Bucket(bucket).upload_file( fullpath, file )
                logging.info("synced ./%s -> s3://%s/%s" %(fullpath.replace(rootpath, ""), bucket, file) )

    except ClientError as ce:
        logging.error("S3 Sync Error: %s" % ce)

    return fcount

# Declare the function to return all file paths of a particular directory
def retrieve_file_paths(dirName):
    # setup file paths variable
    filePaths = []

    # Read all directory, subdirectories and file lists
    for root, directories, files in os.walk(dirName):
        for filename in files:
            # Create the full filepath by using os module.
            filePath = os.path.join(root, filename)
            filePaths.append(filePath)

    # return all paths
    return filePaths

def makeZipFile( pyfilename, zipfilename, dirname ):

    # Go to where the files are
    cwd = os.getcwd()
    
    zippath = os.path.join(os.sep, cwd, dirname, zipfilename)

    # Remove old zip file
    try:
        os.remove(zippath)
        logging.debug("Cleared %s" %(zippath))
    except OSError:
        logging.warn("%s Not Found, Skipping" %(zippath))

    # Write the zip file
    os.chdir(dirname)
    count = 0
    try:
        with zipfile.ZipFile(zippath, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(pyfilename)
            count += 1
            for info in zf.infolist():
                logging.info("Added: %s to: %s/%s | Compressed size: %s | Modified: %s" % (info.filename, dirname, zipfilename, info.compress_size, datetime.datetime(*info.date_time) ) )
                logging.debug( "\tSystem: %s (0 = Windows, 3 = Unix)" % info.create_system )
                logging.debug( "\tZIP version: %s" % info.create_version )
                logging.debug( "\tComment: %s" % info.comment )

    except BadZipfile as bz:
        logging.error ('Bad ZipFile error: %s' % bz)
    finally:
        zf.close()
        logging.debug('Closed %s with %s files' % ( zippath, count ))

    os.chdir(cwd)

def main():
    # Start timer
    start = timer()
 
    try:
        
        # Get the arguments
        args = makeArgs()

        logger.setLevel(logging.INFO)
        logging.basicConfig(format='%(message)s', level=logging.INFO)

        # Announce what is going on
        logging.info("=== Started %s ===" %( os.path.basename(sys.argv[0])))

        # # Create the S3 file storage directory
        # if args.storagetype == "s3bucket":
        #     makeStorageDir( args.s3bucket, args.s3storagedir )

        # Start the heavy lifting
        if args.action == "create":

            # Create the bucket as required
            if createBucket( args.s3bucket, args.region ):
                logging.info("Bucket '%s' in region '%s' is ready." % (args.s3bucket, args.region) )

            # Create the S3 file storage directory
            if args.storagetype == "s3bucket":
                makeStorageDir( args.s3bucket, args.s3storagedir )

            # Create the EBS SnapShot Scheduler zip file
            makeZipFile( "EBS-SnapShot-Scheduler.py", "EBS-SnapShot-Scheduler.zip", "Scheduler" )

            # Create the AutoScaling zip file
            makeZipFile( "AutoScaling.py", "AutoScaling.zip", "AutoScaling" )

            # Upload the files to the bucket
            result = uploadFiles(args.s3bucket, args.environment)
            logging.info("Uploaded %s files to s3://%s" % (result, args.s3bucket) )

            # Get the CloudFormation client
            cfclient = boto3.client('cloudformation')

            # Debug
            logging.info("CloudFormation client: %s" %( cfclient ))

            logging.info("args: %s" %( args ))

            # Build Production stack
            response = cfclient.create_stack( 
                StackName=args.stackname,
                TemplateURL=args.templateurl,
                Parameters=getParams(args), # Get my parameters
                Capabilities=['CAPABILITY_NAMED_IAM'],
                Tags=args.tags
            )
            logging.debug("Create Stack Response: %s" % response )

            logging.info("=======================================================")
            logging.info("Created (Debug: %s) %s DataRobot v%s cluster" % (args.debug, args.environment, args.drversion)) 
            logging.info("Owner: %s | Region: %s | VPC: %s | Subnets: %s" % (args.owner, args.region, args.vpc, args.subnet ))
            logging.info("OS: %s | SSH Key: %s | Subnet CIDR block: %s | External IP: %s" %( args.os, args.sshkey, args.cidr, args.externalip) )
            logging.info("Secrets Enforced: %s | Use KMS Encryption: %s | Key: %s" %( args.secretsenforced, args.encrypted, args.encryptionkey ) )
            logging.info("Use Scheduler: %s | Use AutoScaling: %s | Storage Type: %s" %( args.usescheduler, args.useautoscaling, args.storagetype ) )
            logging.info("Tags: %s" %( args.tags ) )
            logging.info("Template URL: %s" %( args.templateurl ) )
            logging.info("Download URL: %s" %( args.url ) )
            logging.info("Made CloudFormation Stack: %s" % ( args.stackname ))

        elif args.action == "describe":
            logging.info("Describe: %s" % args.stackname)
            try:
                # Get the CloudFormation client
                cfclient = boto3.client('cloudformation')

                response = cfclient.describe_stacks(StackName = args.stackname)

                logging.info("response: %s" % ( response ) )
                # for key in response:
                #     # Check any lists
                #     if type( response[key] ).__name__ == 'list':

                #         logging.info("%s" % key)
                #         for i in response[key]:
                #             logging.info("%s" % ( i ))
                #     else:
                #         logging.info("%s :> %s" % (key, response[key]))

            except ClientError as ce:
                logging.error("Describe Cluster Error: %s" % ce)

        elif args.action == "restore":

            # Create the EBS SnapShot Scheduler zip file
            makeZipFile( "EBS-SnapShot-Scheduler.py", "EBS-SnapShot-Scheduler.zip", "Scheduler" )
            
            # Create the AutoScaling zip file
            makeZipFile( "AutoScaling.py", "AutoScaling.zip", "AutoScaling" )

            # Upload the files to the bucket
            result = uploadFiles(args.s3bucket, args.environment)
            logging.info("Finished uploading %s files to s3://%s" % (result, args.s3bucket) )

            # Create the DataRobot S3 file storage directory
            if args.environment == "Enterprise":
                makeStorageDir( args.s3bucket, args.s3storagedir )
 
            # Get the CloudFormation client
            cfclient = boto3.client('cloudformation')

            # Debug
            logging.debug("CloudFormation client: %s" %( cfclient ))

            # Build Production stack
            response = cfclient.create_stack( 
                StackName=args.stackname,
                TemplateURL=args.templateurl,
                Parameters=getParams(args), # Get my parameters
                Capabilities=['CAPABILITY_NAMED_IAM'],
                Tags=args.tags
            )
            logging.debug("Restore Stack Response: %s" % response )

            logging.info("===============================================")
            logging.info("Restored a (Debug: %s) %s DataRobot v%s Cluster" % (args.debug, args.environment, args.drversion))
            logging.info("Owner: %s | Region: %s | VPC: %s | Subnets: %s" % (args.owner, args.region, args.vpc, args.subnet ))
            logging.info("OS: %s | SSH Key: %s | Subnet CIDR block: %s | External IP: %s" %( args.os, args.sshkey, args.cidr, args.externalip) )
            logging.info("Secrets Enforced: %s | Use KMS Encryption: %s | Key: %s" %( args.secretsenforced, args.encrypted, args.encryptionkey ) )
            logging.info("Use Scheduler: %s | Use AutoScaling: %s | Storage Type: %s" %( args.usescheduler, args.useautoscaling, args.storagetype ) )
            logging.info("Tags: %s" %( args.tags ) )
            logging.info("Template URL: %s" %( args.templateurl ) )
            logging.info("Download URL: %s" %( args.url ) )
            logging.info("Made CloudFormation Stack: %s" % ( args.stackname ))
            logging.info("Restoration Type: %s" % ( args.backuptype ))
            if args.backuptype == "s3bucket":
              logging.info(" - Using: s3://%s/%s" % ( args.s3bucket, args.s3backupdir ))
            elif args.backuptype == "ebssnapshot":
              logging.info("Using EBS SnapShots")
            elif args.backuptype == "none":
                  logging.info("No backup type selected")  

            # logging.info("===============================================")
            # logging.info("Restored a (Debug: %s) %s DataRobot Cluster" % (args.debug, args.environment))
            # logging.info("Using bucket: %s/%s" % (args.s3bucket, args.s3storagedir))
            # logging.info("Owner: %s | Region: %s | Stack name: %s" % (args.owner, args.region, args.stackname))
            # logging.info("VPC: %s | Subnets: %s" % (args.vpc, args.subnet))
            # logging.info("OS: %s | SSH Key: %s | Subnet CIDR block: %s | External IP: %s" %( args.os, args.sshkey, args.cidr, args.externalip) )
            # logging.info("Secrets Enforced: %s | Use KMS Encryption: %s | Key: %s" %( args.secretsenforced, args.encrypted, args.encryptionkey ) )
            # logging.info("Use Scheduler: %s | Use AutoScaling: %s | Storage Type: %s" %( args.usescheduler, args.useautoscaling, args.storagetype ) )
            # logging.info("Tags: %s" %( args.tags ) )
            # logging.info("Template URL: %s" %( args.templateurl ) )
            # logging.info("Restored CloudFormation stack: %s" % ( args.stackname ))

        elif args.action == "delete":
            logging.info("Delete: %s" % args.stackname)
            if yes_or_no("Are you sure you want to delete: '%s'?" % args.stackname ):
                try:

                    # Get the CloudFormation client
                    cfclient = boto3.client('cloudformation')

                    # Debug
                    logging.debug("CloudFormation client: %s" %( cfclient ))
                    logging.info("Deleting stack: %s" %( args.stackname ))
                    response = cfclient.delete_stack( StackName=args.stackname )
                    logging.debug("Response: %s" %( args.stackname, response ))

                except ClientError as ce:
                    logging.info("Delete Cluster Error: %s" % ce)
                logging.info("Delete Response: %s" % response)
            else:
                logging.info("Delete cancelled!")

    except ValueError as e:
        logging.error("Invalid parameter error: %s" % e)


    logging.info("=======================================================")
    logging.info("Buildout completed in %s" % ( str(datetime.timedelta(seconds=timer() - start)) ))

if __name__ == '__main__':
    main()