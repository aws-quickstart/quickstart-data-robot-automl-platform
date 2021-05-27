

Example command to build a quickstart sized deployment:

python3 ./DataRobot_CloudFormation_Kit.py create --environment QuickStart --region us-east-1 --sshkey wes.wagner_keypair --vpc vpc-f3dceb88 --backuptype s3bucket --subnet subnet-0ce21822 --cidr "10.215.20.0/22" --externalip "34.100.95.49/32" --secretsenforced --owner weswagner --storagetype s3bucket --url "https://datarobot-enterprise-releases.s3.amazonaws.com/promoted/7.0.2/dockerized/DataRobot-RELEASE-7.0.2.tar.gz?AWSAccessKeyId=AKIAQ6I23A22NIXIMKVW&Expires=1622488193&Signature=h6%2B0y3YTJx5P87DzE1FVl0mNgTQ%3D"
