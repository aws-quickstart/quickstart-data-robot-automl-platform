###########################################################################
#  Copyright 2020 DataRobot Inc. or its affiliates. All Rights Reserved.  #
#                                                                         #
#  This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES       #
#  OR CONDITIONS OF ANY KIND, express or implied.                         #
###########################################################################

import logging
import json
import boto3
from botocore.exceptions import ClientError, ParamValidationError, WaiterError
from threading import Timer
import datetime

#setup simple logging for INFO.
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def getVar( key, context, event ):
  logger.debug("getVar got key: %s | context: %s | event %s" % (key, context, event ))
  if key in event:
    return event[key]
  elif key in context:
    return context[key]
  else:
    return None

def search(list, value):
    for i in range(len(list)):
      if list[i]['Key'] == value:
        return list[i]['Value']
    return None

def lambda_handler(event, context):
  # logger.debug('Event: %s' %( json.dumps( event ) ) )
  
  def success(data=None):
    logger.info('SUCCESS: ' + json.dumps( data ) )

  def failed(e):
    logger.warn('FAILED event: %s | message: %s ' % ( json.dumps( event ), e ) )

  logger.info('Request (%s) received: %s' % (type(event), json.dumps(event) ) )

  # Get the cloudformation client
  cf_client = boto3.client('cloudformation')
  
  # Get the stack name
  stackname = event['StackName'] if 'StackName' in event else None
  
  # Format the outputs
  context = {}
  for e in (cf_client.describe_stacks(StackName=stackname))['Stacks'][0]['Outputs']:
    logger.debug("%s :> %s" % (e['OutputKey'], e['OutputValue']) )
    context[e['OutputKey']] = e['OutputValue']

  # Administrative settings
  rtype = getVar('RequestType', context, event)
  ctype = getVar('ClusterType', context, event)
  region = getVar('RegionName', context, event)
  cluster = getVar( "NodeIDs%sCluster" % ctype, context, event)
  
  # AutoScaling Group Settings
  autoscalegroup = getVar( "AutoScaleGroup", context, event)
  autoscalecap = int( getVar( "AutoScaleCap", context, event) )
  autoscalemax = int( getVar( "AutoScaleMax", context, event) )
  autoscalemin = int( getVar( "AutoScaleMin", context, event) )
  evaluationperiodsadd = int( getVar( "EvaluationPeriodsAdd", context, event) )
  evaluationperiodsremove = int( getVar( "EvaluationPeriodsRemove", context, event) )
  # Launch Config Settings
  launchconfigname = getVar( "LaunchConfigName", context, event)
  metricnamespace = getVar( "MetricNamespace", context, event)  
  periodadd = int( getVar( "PeriodAdd", context, event) )
  periodremove = int( getVar( "PeriodRemove", context, event) )
  scaleupalarm = getVar( "ScaleUpAlarm", context, event)
  scaledownalarm = getVar( "ScaleDownAlarm", context, event)
  scaledownpolicy = getVar( 'ScaleDownPolicy', context, event)
  scaleuppolicy = getVar( 'ScaleUpPolicy', context, event)
  scalingadjustmentadd = int( getVar( 'ScalingAdjustmentAdd', context, event) )
  scalingadjustmentremove = int( getVar( 'ScalingAdjustmentRemove', context, event) )
  skipami = getVar( 'SkipAMI', context, event)
  subnet = getVar( 'Subnet', context, event)
  thresholdadd = float( getVar( 'ThresholdAdd', context, event) )
  thresholdremove = float( getVar( 'ThresholdRemove', context, event) )
  watchedmetric = getVar( 'WatchedMetric', context, event)
  workerimagename = getVar( 'WorkerImageName', context, event)
  workername = getVar( "WorkerName", context, event)
  workertype = getVar( "WorkerType", context, event)

  modlingonlynodeid = None
  appnodeid = None
  for node in cluster.split("|"):
    if 'AppNode' in node:
      appnodeid = (node.split(":")[1]).strip()

    if 'AppDataNode' in node:
      appnodeid = (node.split(":")[1]).strip()
      
    if 'ModelerOnly' in node:
      modlingonlynodeid = (node.split(":")[1]).strip()
  logger.info("Found appnodeid: %s | modlingonlynodeid: %s" % (appnodeid,modlingonlynodeid))

  amiresponse = None

  # The number of Amazon EC2 instances that the Auto Scaling group attempts to maintain.
  # DesiredCapacity number must be greater than or equal to the minimum size of the group and less than or equal to the maximum size of the group.
  if autoscalemin <= autoscalecap & autoscalecap <= autoscalemax:
    logger.info( "Found valid min: %s <= starting cap: %s <= max: %s" % ( autoscalemin, autoscalecap, autoscalemax ) )
  else:
    logger.error( "min: %s <= cap: %s <= max:%s FAILED!! DesiredCapacity number must be greater than or equal to the minimum size of the group and less than or equal to the maximum size of the group." % ( autoscalemin, autoscalecap, autoscalemax ) )
    exit()

  try:
    
    # Get the clients
    ec2client = boto3.client( 'ec2', region_name=region )
    logger.debug("EC2 Client: %s", ec2client)

    # Create cloudwatch client
    cwclient = boto3.client('cloudwatch')
    logger.debug("CloudWatch Client: %s", cwclient)

    # Create EC2 AutoScaling Launch Configuration
    aslclient = boto3.client('autoscaling')
    logger.debug("AutoScaling Client: %s", aslclient)
  
    ###############################
    if rtype == 'Test':
      logger.info("Test request: %s" % event )

      modlingonlynode = ec2client.describe_instances( InstanceIds=[ modlingonlynodeid ] )
      
      owner = search( modlingonlynode['Reservations'][0]['Instances'][0]['Tags'], "owner")
      mainstack = search( modlingonlynode['Reservations'][0]['Instances'][0]['Tags'], "MainStack")
      nodetype = search( modlingonlynode['Reservations'][0]['Instances'][0]['Tags'], "NodeType")

      logger.info("modlingonlynode: %s | %s | %s" % ( owner, mainstack, nodetype ))
      

    # Start the processing
    if rtype == 'Delete':
      logger.info("Delete request: %s" % event )
      
      if skipami == "true":
        logger.info("Skipping AMI Deletion: %s" % (skipami))
      elif skipami == "false":
        # Delete it if it exists, otherwise move on
        amiresponse = ec2client.describe_images( Filters=[ { 'Name': 'name', 'Values': [ workerimagename ] } ] )
        imglen = len(amiresponse['Images'])
        logger.info("amiresponse (len: %s) %s | %s" %( imglen, workerimagename, amiresponse))
        if imglen > 0:
          amiresponse = ec2client.deregister_image( ImageId=amiresponse['Images'][0]['ImageId'] )
          logger.info("Deleted AMI image: %s" % (amiresponse))
        elif imglen == 0:
          logger.info("AMI not found: %s" % (amiresponse))

      # Delete the policies
      response = aslclient.delete_policy( AutoScalingGroupName=autoscalegroup, PolicyName=scaleuppolicy )
      logger.info("Deleted Policy: %s (%s)" % ( scaleuppolicy, response ))  

      response = aslclient.delete_policy( AutoScalingGroupName=autoscalegroup, PolicyName=scaledownpolicy )
      logger.info("Deleted Policy: %s (%s)" % ( scaledownpolicy, response ))
      
      # Delete the alarms
      response = cwclient.delete_alarms( AlarmNames=[ scaleupalarm, scaledownalarm ] )
      logger.info("Deleted Alarms: %s, %s (%s)" % ( scaleupalarm, scaledownalarm, response ))

      # Delete the group
      response = aslclient.delete_auto_scaling_group( AutoScalingGroupName=autoscalegroup, ForceDelete=True )
      logger.info("Deleted AutoScaling Group: %s (%s)" % ( autoscalegroup, response ))
      
      # Delete the LC
      response = aslclient.delete_launch_configuration( LaunchConfigurationName=launchconfigname )
      logger.info("Deleted Launch Configuration: %s (%s)" % ( launchconfigname, response ))
  
    ###############################      
    if rtype == 'Rebuild':
      logger.info("Rebuild request: %s" % event )
      logger.warn("TODO :: This process will delete all existing DataRobot AutoScaling artifacts and rebuild them specific to this cluster" )

    ###############################
    if rtype == 'Create':
      logger.info("Creating DataRobot AutoScaling environment.")

      # Step 1: Get the instance info for the Modeling Only node
      modlingonlynode = ec2client.describe_instances( InstanceIds=[ modlingonlynodeid ] )

      logger.info("Modeling only node Id: %s | AMI: %s | Private Ip: %s" %( modlingonlynode['Reservations'][0]['Instances'][0]['InstanceId'], modlingonlynode['Reservations'][0]['Instances'][0]['ImageId'], modlingonlynode['Reservations'][0]['Instances'][0]['PrivateIpAddress'] ))
    
      # Get the AppNode
      appnode = ec2client.describe_instances( InstanceIds=[ appnodeid ] )
    
      # Get the Instance profile name
      arn = appnode['Reservations'][0]['Instances'][0]['IamInstanceProfile']['Arn']
      pname = arn[ arn.find("/") + 1 : ]
      logger.info("Profile Name: %s | ARN: %s" % (pname, arn))

      ############
      image_id = None

      # Build the AMI using the modling only node as the base
      try:
        amiresponse = ec2client.describe_images( Filters=[ { 'Name': 'name', 'Values': [ workerimagename ] } ] )
        image_id = amiresponse['ImageId']
        logger.info("Found AMI: %s (%s) from: '%s'" % ( workerimagename, image_id, modlingonlynode['Reservations'][0]['Instances'][0]['InstanceId'] ) )

      except Exception:
        if len(amiresponse['Images']) > 0:
          image_id = amiresponse['Images'][0]['ImageId']
          logger.info("AMI image found: %s (%s)" % (amiresponse['Images'][0]['Name'], image_id ))

        # If it does not exist, create it
        if len(amiresponse['Images']) == 0:
          amiresponse = ec2client.create_image( InstanceId=modlingonlynodeid, Name=workerimagename )
          image_id = amiresponse['ImageId']
          logger.info("Created AMI: %s (%s) from: '%s'" % ( workerimagename, image_id, modlingonlynode['Reservations'][0]['Instances'][0]['InstanceId'] ) )

      ############
      # If worker type = auto, use the instance type of the existing modeling only node
      auto = False
      if workertype == 'auto':
        workertype = modlingonlynode['Reservations'][0]['Instances'][0]['InstanceType']
        auto=True
      logger.info("Creating workertype (auto: %s): %s" % ( auto, workertype ))

      ############
      # Use the existing key name and security group. NOT the passed variables
      launch_configuration_dict = {
        'EbsOptimized': True,
        'ImageId': image_id,
        'InstanceType': workertype,
        'KeyName': modlingonlynode['Reservations'][0]['Instances'][0]['KeyName'],
        'LaunchConfigurationName': launchconfigname,
        'SecurityGroups': [modlingonlynode['Reservations'][0]['Instances'][0]['SecurityGroups'][0]['GroupId']],
      }
      
      # Try to use the same IAM Profile
      if 'IamInstanceProfile' in modlingonlynode['Reservations'][0]['Instances'][0]:
        launch_configuration_dict['IamInstanceProfile'] = modlingonlynode['Reservations'][0]['Instances'][0]['IamInstanceProfile']['Arn']

      response = aslclient.create_launch_configuration(**launch_configuration_dict)
      logger.debug("create_launch_configuration response: %s", response)
      logger.info("Created Launch Configuration: %s | instance type (auto: %s): %s | Key Name: %s | SecurityGroup: %s" % ( launchconfigname, auto, workertype, modlingonlynode['Reservations'][0]['Instances'][0]['KeyName'], modlingonlynode['Reservations'][0]['Instances'][0]['SecurityGroups'][0]['GroupId'] ) )

      ############
      # Create the AutoScaling Group
      response = aslclient.create_auto_scaling_group(
        AutoScalingGroupName=autoscalegroup,
        DefaultCooldown=180,
        DesiredCapacity=autoscalecap,
        LaunchConfigurationName=launchconfigname,
        MaxSize=autoscalemax,
        MinSize=autoscalemin,
        VPCZoneIdentifier=subnet,
      )
      logger.debug("create_auto_scaling_group response: %s", response)
      logger.info("Created Auto Scaling Group: %s | Subnet: %s | Min: %s | Max: %s | Cap: %s" % ( autoscalegroup, subnet, autoscalemin, autoscalemax, autoscalecap ) )

      # Add the assorted tags to the spawned nodes.
      # Right now they are the Name, owner, NodeType and MainStack
      owner = search( modlingonlynode['Reservations'][0]['Instances'][0]['Tags'], "owner")
      nodetype = search( modlingonlynode['Reservations'][0]['Instances'][0]['Tags'], "NodeType")
      mainstack = search( modlingonlynode['Reservations'][0]['Instances'][0]['Tags'], "MainStack")
      
      aslclient.create_or_update_tags(
        Tags=[{ 'ResourceId': autoscalegroup, 'ResourceType': 'auto-scaling-group', 'Key': 'Name', 'Value': workername, 'PropagateAtLaunch': True, },
        { 'ResourceId': autoscalegroup, 'ResourceType': 'auto-scaling-group', 'Key': 'owner', 'Value': owner, 'PropagateAtLaunch': True, },
        { 'ResourceId': autoscalegroup, 'ResourceType': 'auto-scaling-group', 'Key': 'MainStack', 'Value': mainstack, 'PropagateAtLaunch': True, },
        { 'ResourceId': autoscalegroup, 'ResourceType': 'auto-scaling-group', 'Key': 'NodeType', 'Value': nodetype, 'PropagateAtLaunch': True, }
        ]
      )
      logger.info("Taged with Name: %s | owner: %s | NodeType: %s | MainStack: %s" % (workername, owner, nodetype, mainstack))

      # Create Scale Up Policy
      response = aslclient.put_scaling_policy(
        AdjustmentType='ChangeInCapacity',
        AutoScalingGroupName=autoscalegroup,
        PolicyName=scaleuppolicy,
        ScalingAdjustment=scalingadjustmentadd,
      )
      addpolicyarn = response['PolicyARN']
      logger.debug("put_(scale_up_)scaling_policy response: %s", response)
      logger.info("Created Policy name: %s | ScalingAdjustment: %s" %( scaleuppolicy, scalingadjustmentadd ) )

      # Create the Scale up alarm
      response = cwclient.put_metric_alarm(
        AlarmActions=[ addpolicyarn, ],
        AlarmName=scaleupalarm,
        ComparisonOperator='GreaterThanOrEqualToThreshold',
        EvaluationPeriods=evaluationperiodsadd,
        MetricName=watchedmetric,
        Namespace=metricnamespace,
        Period=periodadd,
        Statistic='Average',
        Threshold=thresholdadd,       
      )
      logger.debug("put_(scale_up_)metric_alarm response: %s", response)
      logger.info("Created Scale Up Alarm name: %s | Period: %s seconds | %s::%s >= %s | Evaluations: %s" % ( scaleupalarm, periodadd, metricnamespace, watchedmetric, thresholdadd, evaluationperiodsadd ) )

      # Create Scale Down Policy
      response = aslclient.put_scaling_policy(
        AdjustmentType='ChangeInCapacity',
        AutoScalingGroupName=autoscalegroup,
        PolicyName=scaledownpolicy,
        ScalingAdjustment=scalingadjustmentremove,        
      )
      removepolicyarn = response['PolicyARN']
      logger.debug("put_(scale_down_)scaling_policy response: %s", response)
      logger.info("Created Policy name: %s | ScalingAdjustment: %s" %( scaledownpolicy, scalingadjustmentremove ) )

      # Create the Scale down alarm
      response = cwclient.put_metric_alarm(
        AlarmActions=[ removepolicyarn, ],
        AlarmName=scaledownalarm,
        ComparisonOperator='LessThanOrEqualToThreshold',
        EvaluationPeriods=evaluationperiodsremove,
        MetricName=watchedmetric,
        Namespace=metricnamespace,
        Period=periodremove,
        Statistic='Average',
        Threshold=thresholdremove,
      )
      logger.debug("put_(scale_down_)metric_alarm response: %s", response)
      logger.info("Created Scale Down Alarm name: %s | Period: %s seconds | %s::%s <= %s | Evaluations: %s" % ( scaledownalarm, periodremove, metricnamespace, watchedmetric, thresholdremove, evaluationperiodsremove ) )


  except Exception as e:
    logger.warning('Unexpected exception: %s', e )
    failed(e)

  return {
    'statusCode': "200",
    "SkipAMI": skipami,
    'RequestType': rtype
  }
