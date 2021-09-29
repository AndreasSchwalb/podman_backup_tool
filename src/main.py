import json
from pathlib import Path
from typing import List, Dict

from custom_logger import Logger
from dotenv import load_dotenv
from extended_config_parser import ExtendedConfigParser
from podman_api import PodmanApi, PodmanSocket

load_dotenv()

config = ExtendedConfigParser()
logger = Logger.setup('podman_backup')


class PodmanBackup:

    def __init__(self) -> None:
        self.restore = self._get_bool_from_string(config['backup']['restore'])
        self.backup_config_file_path = config['backup']['config_file_path']
        self.backup_image_name = config['backup']['image_name']
        self.backup_destination = config['backup']['destination']
        self.backup_destination_remote = config['backup']['destination_remote']
        self.ssh_certs_folder = config['ssh']['certs_folder']
        socket_path = config['socket']['path']

        pod_sock = PodmanSocket(socket_path)
        self.api = PodmanApi(podman_socket=pod_sock)

        self._initialisation_sequence()

    def _get_bool_from_string(self, value: str) -> bool:
        bool_str_upper = value.upper()

        if bool_str_upper == 'TRUE' or bool_str_upper == '1':
            return True

        return False

    def _initialisation_sequence(self) -> None:
        self._container_config = self._read_volume_config_file(self.backup_config_file_path)
        self._prepare_backup_image(self.backup_image_name)

    def _read_volume_config_file(self, path: str) -> List:
        with open(path, 'r') as file:
            data = file.read()
            return json.loads(data)

    def _prepare_backup_image(self, image_name: str) -> None:
        logger.info('Check if backup image exists')
        backup_image_exists = self.api.image_exists(image_name)
        if not backup_image_exists:
            logger.info('Backup image does not exist. Start to build backup image')
            self.api.image_build(
                tag=self.backup_image_name,
                dockerfile_path=config['backup']['image_build_source']
            )

    def _backup_container(self, volumes: List, restore: bool = False) -> None:
        for volume in volumes:
            backup_container_id = self._backup_volume(volume, restore)
            if len(backup_container_id) > 0:
                self.api.container_wait(backup_container_id)

    def _backup_volume(self, volume: Dict, restore: bool) -> str:

        volumes_parameter: List[Dict] = []
        bind_mount_parameter: List[Dict] = []

        volume_type = volume.get('type')
        volume_name = volume.get('name')
        volume_path = volume.get('path')

        if volume_type == 'volume':
            volumes_parameter.append(
                {
                    'Dest': f'/volumes/{volume_name}',
                    'Name': volume_name
                }
            )

        if volume_type == 'bind':
            if restore:
                if volume_path:
                    path = Path(volume_path)

                if not path.exists():
                    logger.warning(f'Folder {self.backup_destination} does not exist.')
                    try:
                        path.mkdir(parents=True)
                        logger.info(f'Created folder {self.backup_destination}.')
                    except FileNotFoundError or OSError:
                        logger.error(f'Could not create folder {self.backup_destination}!')
                        logger.error('Restore failed')

            bind_mount_parameter.append(
                {
                    'Destination': f'/volumes/{volume_name}',
                    'Source': volume_path,
                    'Options': ['rbind']
                }
            )
        if self.backup_destination_remote.upper() == 'FALSE':
            path = Path(self.backup_destination)
            if not path.exists():
                logger.error('Could not run backup')
                logger.error(f'Backup folder {self.backup_destination} does not exist!')
                return ''

            bind_mount_parameter.append(
                {
                    'Destination': '/destination/',
                    'Source': self.backup_destination,
                    'Options': ['rbind']
                }
            )

            command = [
                'rsync',
                '-rlptD',
                # '-av',
                # '--numeric-ids',
                '--delete',
                '--chown=0:0',
                f'/volumes/{volume_name}/',
                f'/destination/{volume_name}/{volume_name}/'
            ]
        else:

            bind_mount_parameter.append(
                {
                    'Destination': '/root/.ssh',
                    'Source': self.ssh_certs_folder,
                    'Options': ['rbind']
                }
            )

            command = [
                'rsync',
                '-rlptD',
                # '-av',
                # '--numeric-ids',
                '--delete',
                '--chown=0:0',
                '-e',
                'ssh',
                f'/volumes/{volume_name}/',
                f'{self.backup_destination}/{volume_name}/'
            ]

        # switch last two coment items when restore is set
        if self.restore:
            cmd_part_1 = command[-1]
            cmd_part_2 = command[-2]
            command[-1] = cmd_part_2
            command[-2] = cmd_part_1

        # Uncomment for test issues
        # command = ['sleep','500']
        # command = ['touch', '/volumes/to_sync_bind/test.txt']

        con = self.api.container_create(
            image=self.backup_image_name,
            volumes=volumes_parameter,
            mounts=bind_mount_parameter,
            remove=True,
            command=command,
        )

        self.api.container_start(con)
        return con

    def run(self) -> None:
        for container in self._container_config:
            container_name = container.get("container_name")
            container_need_to_pause = container.get('need_to_pause')

            if self.restore:
                logger.info(f'Start restore of container {container_name}')
                self._backup_container(
                    volumes=container.get('volumes'),
                    restore=True
                )
            else:
                logger.info(f'Start backup of container {container_name}')

                if container_need_to_pause:
                    self.api.container_pause(container_name)
                self._backup_container(
                    volumes=container.get('volumes')
                )
                if container_need_to_pause:
                    self.api.container_unpause(container_name)


if __name__ == '__main__':
    pb = PodmanBackup()
    pb.run()
