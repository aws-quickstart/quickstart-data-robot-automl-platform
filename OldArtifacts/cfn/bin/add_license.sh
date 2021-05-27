#!/bin/bash
#
# This script will use the Admin username and password to get a token
# from the AppNode, then apply the given license
#
# To make it work with https, find replace all http:// with https://
#
USAGE="USAGE: add_license.sh -a <AppNode IP> -u <Admin Username> -p <Admin Password> -l <Path To License>"

while getopts "a:u:p:l:" opt; do
    case $opt in
        a)
            #Reading first argument
            appnode=$OPTARG
        ;;
        u)
            #Reading second argument
            username=$OPTARG
        ;;
        p)
            #Reading third argument
            password=$OPTARG
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

if [ -z "$appnode" ]; then
    echo $USAGE
    echo "AppNode (-a) not given!"
    exit 1
fi

if [ -z "$username" ]; then
    echo $USAGE
    echo "Admin Username (-u) not given!"
    exit 1
fi

if [ -z "$password" ]; then
    echo $USAGE
    echo "Admin Password (-p) not given!"
    exit 1
fi

if [ -z "$license" ]; then
    echo $USAGE
    echo "Path To License (-l) not given!"
    exit 1
fi

echo -e "\n=== $0 started $(date -u) ==="

echo -n "Loggging in to: '${appnode}': "
output=$(curl --silent -X POST --cookie "cookies.txt" --cookie-jar "cookies.txt" -H "Content-Type: application/json" -d '{"username":"'"${username}"'","password":"'"${password}"'"}' http://${appnode}/account/login)
echo ${output}

echo -n "Getting API key for '${username}': "
apikey=$(curl --silent -X POST --cookie "cookies.txt" --cookie-jar "cookies.txt" -H "Content-Type: application/json" -d '{"name":"apiKey"}' http://${appnode}/api/v2/account/apiKeys/ | jq ".key")
echo ${apikey}

echo -n "Applying the ${#ldata} charecters in '${license}': "
returncode=$(curl --silent -w "%{http_code}\n" -X PUT -H "Content-Type: application/json" -H "HTTP/1.1" -H "Authorization: Token ${apikey}}" -d '{"licenseKey":"'"${ldata}"'"}' http://${appnode}/api/v2/clusterLicense/)

if [ $returncode -eq 200 ]; then
    echo "SUCCESS! (${returncode})"
else
    echo "FAILED! (${returncode})"
    rm -f cookies.txt
    exit 256
fi

echo "Clean up: $(rm -f cookies.txt) ... Done."
exit