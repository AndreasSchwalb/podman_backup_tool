# Podman container backup tool
Sychronize volume and bind mounts to a defined destination.


## Configuration

The configuration is splitted in two parts.

First is the configuration of the containers which should be synchronized and the second part is the configuration of the backup tool itself.


### Configuration backup tool

The configuration of the backup tool is done by environment variables

| variable                      | description | 
|-------------------------------|-------------|
| CONF_LOGGING_LOG_LEVEL        | the loglevel|
| CONF_HTTP_CONNECTION_RETRY    | amount of retries when a connetion could not be establised |
| CONF_SOCKET_PATH              | the path to the unix socket |
| CONF_BACKUP_CONFIG_FILE_PATH  | the path to the container configuration file|
| CONF_BACKUP_RESTORE           | set the direction of the backup tool. if set to false it will sync from local to backup otherwise it will sync from backup to local|
| CONF_BACKUP_TIME_TO_RUN       | time to run the backup or now for run the backup once but now|
| CONF_SSH_CERTS_FOLDER         | path to the ssh cert wich shhould be used for remote backup|


example .env-file:
```
CONF_LOGGING_LOG_LEVEL=debug
CONF_HTTP_CONNECTION_RETRY=3
CONF_SOCKET_PATH=/run/user/1000/podman/podman.sock
CONF_BACKUP_CONFIG_FILE_PATH=./config/example-config.json
CONF_BACKUP_DESTINATION_REMOTE=true
CONF_BACKUP_RESTORE=false
CONF_BACKUP_TIME_TO_RUN=now
#CONF_BACKUP_TIME_TO_RUN=03:05
CONF_SSH_CERTS_FOLDER=/home/andy/Dokumente/python/podman_backup/certs
```

### configuration containers/volumes

example:
```json
[
   
    {   "container_name": "test-alpine",
        "need_to_pause": false,
        "volumes":[
            {
                "name":"to_sync_bind",
                "backup_source":"/bind_mounts/to_sync_bind/",
                "backup_destination":"rsync@192.168.1.100:/volume1/backup-test/to_sync_bind/",
                "remote_destination":true
            },
            {
                "name":"to_sync_bind2",
                "backup_source":"/bind_mounts/to_sync_bind2/",
                "backup_destination":"rsync@192.168.1.100:/volume1/backup-test/to_sync_bind2/",
                "remote_destination":true
            },
            {
                "name":"test-vol",
                "backup_source":"/volumes/test-vol/",
                "backup_destination":"rsync@192.168.1.100:/volume1/backup-test/test-vol/",
                "remote_destination":true
                
            }
        ]
    }
]
```

## remote sync

to perform a remote sync the destination host must be prepared for this.

You need to add your ssh public-key to the file `<username>\.ssh\authorized_keys`

Actually the backup tool must run with root privileges inside the container. Otherwise the uid on the host will be mapped with the uid from the user namespace. So actually all restored files will have the uid from the user with wicht the podman socket/service was started.
