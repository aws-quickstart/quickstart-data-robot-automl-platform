#!/bin/bash

# Create a temporary blank directory
mkdir -p /opt/datarobot/docker-tmp

# Chown it to datarobot
chown datarobot:datarobot /opt/datarobot/docker-tmp

# Do the clear
rsync --archive --delete /opt/datarobot/docker-tmp/ /opt/datarobot/docker-old/

# Clean up
rm -rf /opt/datarobot/docker-old
rm -rf /opt/datarobot/docker-tmp
