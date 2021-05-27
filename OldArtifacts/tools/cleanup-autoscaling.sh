#!/bin/sh
###########################################################################
#  Copyright 2020 DataRobot Inc. All Rights Reserved.                     #
#                                                                         #
#  This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES       #
#  OR CONDITIONS OF ANY KIND, express or implied.                         #
###########################################################################
# This script will clean up the DataRobot AutoScaling stuff left behind after removong the CloudFormation templates
#
# options are poc or preprod
envtype=${1:-$(echo poc)} 

# Use the passed value or current user name with non-alphanum removed
owner=${2:-$(echo $(whoami) | sed 's/[^a-zA-Z0-9]//g')} 

# Setting the variable names
lcname="datarobot-${owner}-${envtype}-AutoScaling-LC"
group="datarobot-${owner}-${envtype}-AutoScaling-Group"
puname="datarobot-${owner}-${envtype}-ScaleUp-Policy"
pdname="datarobot-${owner}-${envtype}-ScaleDown-Policy"
alarmup="datarobot-${owner}-${envtype}-ScaleUp-Modeling-Capacity-Alarm"
alarmdown="datarobot-${owner}-${envtype}-ScaleDown-Modeling-Capacity-Alarm"
iname="datarobot-${owner}-${envtype}-AutoScaledWorkerImage"

# Announcements!
echo "#===================="
echo "Launch Config     => ${lcname}"
echo "AutoScaling Group => ${group}"
echo "Scale Up Alarm    => ${alarmup}"
echo "Scale Up Policy   => ${puname}"
echo "Scale Down Alarm  => ${alarmdown}"
echo "Scale Down Policy => ${pdname}"
echo "Worker Image      => ${iname}"
echo ""

read -r -p "Continue Deletion [y/n]? " input
case $input in
    [Yy]*) 
        echo "$(date) : describe-images filters:\"Name=name,Values=${iname}\" query:'Images[*].{ID:ImageId}'"
        result=$(aws ec2 describe-images --filters "Name=name,Values=${iname}" --query 'Images[*].{ID:ImageId}' --output text)
        
        echo "$(date) : deregister-image image-id:${result}"
        aws ec2 deregister-image --image-id ${result}

        echo "$(date) : delete-alarms: ${alarmup}"
        aws cloudwatch delete-alarms --alarm-names ${alarmup}

        echo "$(date) : delete-policy: ${puname}"
        aws autoscaling delete-policy --auto-scaling-group-name ${group} --policy-name ${puname}

        echo "$(date) : delete-alarms: ${alarmdown}"
        aws cloudwatch delete-alarms --alarm-names ${alarmdown}

        echo "$(date) : delete-policy: ${pdname}"
        aws autoscaling delete-policy --auto-scaling-group-name ${group} --policy-name ${pdname}

        echo "$(date) : delete-auto-scaling-group: ${group}"
        aws autoscaling delete-auto-scaling-group --auto-scaling-group-name ${group} --force-delete

        echo "$(date) : delete-launch-configuration: ${lcname}"
        aws autoscaling delete-launch-configuration --launch-configuration-name ${lcname}
        ;;
    [Nn]*) echo "Quitting" ;;
esac

echo ""
