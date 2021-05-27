#!/usr/bin/env python
###########################################################################
#  Copyright 2020 DataRobot Inc. or its affiliates. All Rights Reserved.  #
#                                                                         #
#  This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES       #
#  OR CONDITIONS OF ANY KIND, express or implied.                         #
###########################################################################

import argparse
import boto3
import datetime
import os
import sys
import re
import requests
import random
import zipfile
import logging

from timeit import default_timer as timer
try:
  import pwd
except ImportError:
  import getpass
  pwd = None

regions = [ "ap-northeast-1", "ap-northeast-2", "ap-south-1", "ap-southeast-1", "ap-southeast-2", "ca-central-1", "eu-central-1", "eu-north-1", "eu-west-1", "eu-west-2", "eu-west-3", "sa-east-1", "us-east-1", "us-east-2", "us-west-1", "us-west-2" ]
actions = [ "create", "describe", "delete"]

stackfile="EBS-SnapShot-Scheduler-Stack.yaml"
pyfilename="EBS-SnapShot-Scheduler.py"
zipfilename="EBS-SnapShot-Scheduler.zip"
dirname="./"

MyName = "DataRobot-EBS-SnapShot-Scheduler"

#atag="<AppNodeId>"
#mtag="<ModelingOnlyNodeID>"
#stag="<ModelingOnlyNodeSubnet>"

# Return the username in a portable way
def currentUser( alpha = False ):
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
        # prog='',
        description="Deploys, Deletes and Creastes the DataRobot EBS SnapShot Scheduler Stack",
        epilog="DataRobot Copyright 2020"
    )

    subparsers = parser.add_subparsers( help='commands', dest='action' )

    # Add the create command
    create = subparsers.add_parser('create', help="Create the DataRobot EBS-SnapShot-Scheduler Stack")
    create.add_argument("--s3bucket", help="S3 bucket name used with CloudFormation.", required=True )
    create.add_argument("--region", help="AWS Region to build in. Default: %(default)s", choices=regions, default="us-east-1" )
    create.add_argument("--instances", help="Comma seperated list of instance id's", required=True )
    create.add_argument("--stackfile", help="EBS SnapShot Scheduler Stack file name. Default: %(default)s", metavar=stackfile, default=stackfile )
    create.add_argument("--stackname", help="Stack name tag for this CloudFormation execution.", required=True )
    create.add_argument("--pyfile", help="Pyhon file used in zip file. Default: %(default)s", metavar=pyfilename, default=pyfilename )
    create.add_argument("--zipfile", help="Zip file name. Default: %(default)s", metavar=zipfilename, default=zipfilename )
    create.add_argument("--tag", help="Tag to apply to this stack. 1 tag per switch. Script executer automatically applyied. ex: '--tag Foo=Bar'", action='append')
    create.add_argument("--debug", help="Allows for a debug version, with a random id attached.", action='store_true' )

    # Add the describe command
    describe = subparsers.add_parser('describe', help="Describe the DataRobot EBS-SnapShot-Scheduler Stack")
    describe.add_argument("--stackname", help="Stack name for this CloudFormation execution." )

    # Add the delete command
    delete = subparsers.add_parser('delete', help="Delete the DataRobot EBS-SnapShot-Scheduler Stack")
    delete.add_argument("--stackname", help="Stack name for this CloudFormation execution." )

    args = parser.parse_args()

    # Get the deafule names for a few things
    args.myname = MyName

    args.key = random.randint(1,10000)
    
    if args.action == 'create':

        if args.debug == True:
            args.stackname = "%s-%s" % (args.stackname, args.key)
            args.myname  = "%s-%s" % (args.myname, args.key)

        # Build out the CloudFormation stack url
        args.templateurl = "https://s3.amazonaws.com/%s/Scheduler/%s" % (args.s3bucket, args.stackfile)
    
        # Start the tags list
        args.tags = []

        # Tag everything in the cluster with the name of the account that built it.
        args.tags.append( { 'Key': 'builder', 'Value': currentUser(True) } )

        # Apply any tags given from the command line
        if type( args.tag ).__name__ != 'NoneType' and len(args.tag) > 0:
            for t in args.tag:
                t = t.split("=")
                args.tags.append( { 'Key': t[0], 'Value': t[1] } )

    return args

def getParams( args ):
    params = []
    params.append( { 'ParameterKey': 'S3Bucket', 'ParameterValue': args.s3bucket } )
    params.append( { 'ParameterKey': 'Instances', 'ParameterValue': args.instances } )
    return params

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

def main():
    # Start timer
    start = timer()

    logging.basicConfig(format='%(message)s', level=logging.INFO)
    # logging.basicConfig(format='%(asctime)s :: %(message)s', level=logging.DEBUG)

    try:
        # Announce what is going on
        logging.info("=== Started %s ===" %( os.path.basename(sys.argv[0])))
        logging.info("-------------------------------------------------------")

        # Get the arguments
        args = makeArgs()

        logging.info("Args: %s" % (args))

        # Start the heavy lifting
        if args.action == "create":
            logging.info("Applying '%s' to the nodes referenced by '%s'" %(args.stackfile, args.stackname))
            logging.info("Tags: %s" %(args.tags))
            logging.info("--------------------------------------------")

            # Remove old zip file
            try:
                os.remove(zipfilename)
                logging.info("Deleted old %s" %(args.zipfile))
            except OSError:
                logging.info("%s Not Found" %(args.zipfile))
                pass

            try:
                # Write the zip file
                zf = zipfile.ZipFile(args.zipfile, mode='w', compression=zipfile.ZIP_DEFLATED)
                logging.debug('Adding %s to %s' % ( args.pyfile, args.zipfile ) )
                zf.write(pyfilename)

                for info in zf.infolist():
                    logging.info("Added: %s | Compressed size: %s | Modified: %s" % (info.filename, info.compress_size, datetime.datetime(*info.date_time) ) )
                    logging.debug( "\tSystem: %s (0 = Windows, 3 = Unix)" % info.create_system )
                    logging.debug( "\tZIP version: %s" % info.create_version )
                    logging.debug( "\tComment: %s" % info.comment )

            except ValueError as e:
                logging.error("Invalid parameter error: %s" % e)
                quit()
            except Exception as e:
                #logging all the others as warning
                logging.error("Unexpected exception: %s" % e)
                quit()
            finally:
                zf.close()
                logging.info('Closed %s' % (args.zipfile))

            # Get the S3 resource
            s3resource = boto3.resource("s3", region_name=args.region)

            # Upload the zip file to the bucket
            # s3resource.Bucket(args.s3bucket).upload_file( args.zipfile, args.zipfile )
            path = "Scheduler/"
            path += args.zipfile
            s3resource.Bucket(args.s3bucket).upload_file( args.zipfile, path )
            logging.info("Uploaded %s to %s/Scheduler/%s" %(args.zipfile, args.s3bucket, args.zipfile))

            # Upload the cloudformation stack file
            path = "Scheduler/"
            path += args.stackfile
            s3resource.Bucket(args.s3bucket).upload_file( args.stackfile, path )
            logging.info("Uploaded %s to %s/Scheduler/%s" %(args.stackfile, args.s3bucket, args.stackfile))

            # create the CloudFormation client
            cfclient = boto3.client('cloudformation')

            # Build Production stack
            response = cfclient.create_stack(
                StackName=args.myname,
                TemplateURL=args.templateurl,
                Parameters=getParams(args),
                Capabilities=['CAPABILITY_NAMED_IAM'],
                Tags=args.tags
            )
            logging.debug("Create Stack Response: %s" % response )
            logging.info("Created CloudFormation stack: %s" % ( args.myname ))

        elif args.action == "describe":
            logging.info("Describe: %s" % args.stackname)
            # Get the CloudFormation client
            cfclient = boto3.client('cloudformation')
            
            response = cfclient.describe_stacks(StackName = args.stackname)
            response = response['Stacks'][0]
            for key in response:
                # Check any lists
                if type( response[key] ).__name__ == 'list':
                    logging.info("%s" % key)
                    for i in response[key]:
                        logging.info(" :> %s" % ( i ))
                else:
                    logging.info("%s :> %s" % (key, response[key]))

        elif args.action == "delete":
            logging.info("Delete: %s" % args.stackname)
            cfclient = boto3.client('cloudformation')
            response = cfclient.delete_stack( StackName=args.stackname )
            logging.info("Delete Response: %s" % response)

    except ValueError as e:
        logging.error("Invalid parameter error: %s" % e)
        quit()
    except Exception as e:
        #logging all the others as warning
        logging.error("Unexpected exception: %s" % e)
        quit()

    logging.info("--------------------------------------------")
    logging.info("EBS Create test event: { \"RequestType\": \"Create\", \"StackName\": \"%s\" }" % (args.myname) )
    logging.info("--------------------------------------------")
    logging.info("Buildout completed in %s" % ( str(datetime.timedelta(seconds=timer() - start)) ))

if __name__ == '__main__':
    main()