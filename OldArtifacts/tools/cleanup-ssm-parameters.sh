#!/bin/bash

# By default, this script deletes AWS parameters where:
# parameter: "*datarobot-public-key"
# in region: us-east-1

region=${1:-'us-east-1'}
key=${2:-'datarobot-public-key'}

for element in $(aws ssm describe-parameters --region $region --query 'Parameters[].Name' --output text); do
   if [[ "$element" == *"$key" ]]; then

   	read -r -p "Delete $element [y/n]: " input
      case $input in
         [Yy]*) aws ssm delete-parameter --region $region --name $element && echo "It's gone." ;;
         [Nn]*) echo "Skipped" ;;
      esac

   fi
done
