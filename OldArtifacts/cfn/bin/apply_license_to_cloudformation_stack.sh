#!/bin/bash
#
# This script will use the given stack name to find the ssh connection string,
# then get the admin password off the app node and apply the license
#
# Update this string as required for your env
#   ?OutputKey=='SSHConnectionStringPoCCluster'
#
USAGE="USAGE: apply_license_to_cloudformation_stack.sh -s <Stack Name> -l <Path To License>"

while getopts "s:l:" opt; do
    case $opt in
        s)
            #Reading first argument
            stack=$OPTARG
        ;;
        l)
            #Reading foutrh argument
            license=$OPTARG
            if [ -f ${license} ]; then
                ldata=$(cat ${license})
                # echo "${license} contains: ${ldata}"
            else 
                echo $USAGE
                echo "License file: '${license}' does not exist!"
                exit 2
            fi
        ;;
        *)
            #Printing error message
            echo $USAGE
            echo "Invalid option or argument '$OPTARG'"
            exit 3

        ;;
        esac
done

if [ -z "$stack" ]; then
    echo $USAGE
    echo "No Stack Given! (-s)"
    exit 1
fi

if [ -z "$license" ]; then
    echo $USAGE
    echo "Path To License (-l) not given!"
    exit 1
fi

# Get the connection string
ssh_cmd=$(aws cloudformation describe-stacks --stack-name ${stack} --query "Stacks[0].Outputs[?OutputKey=='SSHConnectionStringPoCCluster'].OutputValue" --output text)

# Find the App node address
appnode=$(echo $ssh_cmd | cut -d "@" -f 2)

# Get the admin info
admin_json=$(${ssh_cmd} sudo cat /home/datarobot/admin_password)

# Get the username from the admin info
admin_user=$(echo $admin_json | cut -d '"' -f 4 )

# Get the password
admin_passwd=$(echo $admin_json | cut -d '"' -f 8)

# Add the license
/bin/bash ./add_license.sh -a $appnode -u $admin_user -p $admin_passwd -l $license
