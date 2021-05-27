###########################################################################
#  Copyright 2020 DataRobot Inc. or its affiliates. All Rights Reserved.  #
#                                                                         #
#  This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES       #
#  OR CONDITIONS OF ANY KIND, express or implied.                         #
###########################################################################

import logging
import boto3
from botocore.exceptions import ClientError, ParamValidationError
import datetime
import json
        
#setup simple logging for INFO.
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def backup_instance(ec2, name, id, vol, stack):
    logger.debug("Create backup instance:> name: %s | id: %s | vol: %s | stack: %s" % ( name, id, vol, stack ) )
    
    # Generate the Description
    current_time = ( datetime.datetime.utcnow() ).strftime("%h %d,%H:%M")
    description = "Created by EBSSnapshotScheduler from %s (%s) at %s UTC" % ( id, vol, current_time )
    
    # schedule snapshot creation.
    try:
        snapshot = ec2.create_snapshot(
            Description=description,
            TagSpecifications=[ {
                'ResourceType': 'snapshot',
                'Tags': [ { 'Key': 'Name', 'Value': name }, { 'Key': 'MainStack', 'Value': stack } ]
            } ],
            VolumeId=vol
        )

    except Exception as e:
        logger.error( e )
    
    return snapshot

def remove_instances(ec2, name, retainfor, stack):
    deleted_snaps = list()
    
    logger.info("Remove backups of %s in stack %s older than %s days" % ( name, stack, retainfor ) )

    try:

        snapshots = ec2.describe_snapshots( OwnerIds=['self'], Filters=[ { 'Name': 'tag:MainStack', 'Values': [ stack ] } ] )
    
        now = datetime.datetime.now( datetime.timezone.utc )

        for snap in snapshots['Snapshots']:

            age = abs((snap['StartTime'] - now).days)
            logger.info("Checking %s, is %s days old" % ( snap['SnapshotId'], age) )

            if int(age) >= int(retainfor):
                response = ec2.delete_snapshot( SnapshotId=snap['SnapshotId'] )
                deleted_snaps.append( response )
                logger.debug("delete_snapshot response: %s" % ( response ))

    except ParamValidationError as e:
        logger.error("Parameter validation error: %s" % e)
    except ClientError as e:
        logger.error("Unexpected error: %s" % e)
    except Exception as e:
        logger.error("Unexpected exception: %s" % e )
    
    return deleted_snaps

def findKey( tags, key ):
    for t in tags:
        logger.debug("Tag: %s" % (t))
        if t['Key'] == key:
            return t['Value']
    return None

def getVar( key, context, event ):
    logger.debug("getVar got key: %s | context: %s | event %s" % (key, context, event ))
    if key in event:
        return event[key]
    elif key in context:
        return context[key]
    else:
        return None

def lambda_handler(event, context):
    # logger.debug("Event: %s" % (event))
    # logger.debug("Context: %s" % (context))

    def success(data=None):
        logger.info('SUCCESS: ' + json.dumps( data ) )

    def failed(e):
        logger.error('FAILED event: %s | message: %s ' % ( json.dumps( event ), e ) )

    logger.info('Request (%s) received: %s' % (type(event), json.dumps(event) ) )

    removedsnaps = {}
    createdsnaps = 0

    # Get the cloudformation client
    cf_client = boto3.client('cloudformation')
    
    # Get the stack name
    stackname = event['StackName'] if 'StackName' in event else None

    # Format the outputs
    context = {}
    for e in (cf_client.describe_stacks(StackName=stackname))['Stacks'][0]['Outputs']:
        logger.info("%s :> %s" % (e['OutputKey'], e['OutputValue']) )
        context[e['OutputKey']] = e['OutputValue']
    
    # Get the values
    autodelete = getVar('AutoSnapshotDeletion', context, event)
    rtype = getVar('RequestType', context, event)
    retainfor = getVar('ScheduleRetentionPeriod', context, event)
    tagname = getVar('ScheduleCustomTagName', context, event)
    region = getVar('RegionName', context, event)

    try:

        # Get the Boto3 AWS clients
        ec2 = boto3.client( 'ec2', region_name=region )
        ec2_resource = boto3.resource('ec2', region_name=region)

        # Start the processing
        if rtype == 'Create':
            logger.info("Create request")

            instances = ec2.describe_instances( Filters=[ { 'Name': 'tag:MainStack', 'Values': [ stackname ] }, { 'Name': 'tag-key', 'Values': [ tagname ] } ] )

            for res in instances['Reservations']:
                for inst in res['Instances']:
                    
                    # Get the name
                    name = findKey( inst['Tags'], "Name" ).replace( ("%s-" % stackname), "" )
                    name = ( "%s-Data-Volume-SnapShot" % name )
                    
                    # Make the snapshot from the given volume id
                    snap = backup_instance(ec2_resource, name, inst['InstanceId'], inst['BlockDeviceMappings'][1]['Ebs']['VolumeId'], stackname )
                    logger.info("Created %s (%s) from %s" % (name, snap.id, inst['BlockDeviceMappings'][1]['Ebs']['VolumeId']))
                    
                    createdsnaps += 1

                    # Take care of the clean up
                    if autodelete:
                        removedsnaps = remove_instances( ec2, name, retainfor, stackname )
                        logger.info("Cleaned up %s old SnapShots" % len(removedsnaps))

    except ParamValidationError as e:
        logger.error("Parameter validation error: %s" % e)
    except ClientError as e:
        logger.error("ClientError: %s" % e)
    except Exception as e:
        logger.error("Unexpected exception: %s" % e )
        failed(e)

    return {
      'created_snaps': createdsnaps,
      'statusCode': "200",
      'removed_snaps': len(removedsnaps),
      'event': event
    }