# DataRobot CloudFormation Cluster Provisioning

## Summary

These files allow for the ease of creating the various environments.

## Details

### flush-old-docker.sh

Process used to move the old docker stuff out of the way and rebuild the
docker directory and symlink using these steps:

- Move the old docker directory out of the way
- Create a temporary blank directory
- Chown it to datarobot
- Clear the old direcotry using rsync
  - Would love to use perl instead, but it is not default
- Clean up
- Mark this is being flushed

### reconf-repl.tmpl

This is the template used to rebuild the Mongo Replicant Set
Please see the '4f-RebuildMongoReplSet' section of the EC2-Restore-Parent-Stack.yaml

## Copyright

Copyright &copy; DataRobot 2020
