#!/bin/bash
if [ -z "$1" ] ; then
    echo "Please pass the name of the AMI"
    exit 1
fi

IMAGE_FILTER="${1}"

for region in $(aws ec2 describe-regions --query "Regions[].{Name:RegionName}" --output text) ; do 
	#echo $region ;
	ami=$(aws ec2 describe-images --query 'Images[*].[ImageId]' --filters "Name=description,Values=${IMAGE_FILTER}" --region ${region} --output text | uniq)
	echo "${region} :> ${ami}"
done
