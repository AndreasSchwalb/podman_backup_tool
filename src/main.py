import json
from pathlib import Path
from typing import List, Dict
from datetime import datetime
import time
import subprocess

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
        self.time_to_run = config['backup']['time_to_run']
        self.ssh_certs_folder = config['ssh']['certs_folder']
        socket_path = config['socket']['path']

        self.running = True
        self.backup_started = False

        pod_sock = PodmanSocket(socket_path)
        self.api = PodmanApi(podman_socket=pod_sock)
        self._container_config = self._read_volume_config_file(self.backup_config_file_path)

    def _get_bool_from_string(self, value: str) -> bool:
        bool_str_upper = value.upper()

        if bool_str_upper == 'TRUE' or bool_str_upper == '1':
            return True

        return False

    def _initialisation_sequence(self) -> None:
        self._container_config = self._read_volume_config_file(self.backup_config_file_path)

    def _read_volume_config_file(self, path: str) -> List:
        with open(path, 'r') as file:
            data = file.read()
            return json.loads(data)

    def _backup_container(self, volumes: List, restore: bool = False) -> None:
        for volume in volumes:
            self._backup_volume(volume, restore)

    def _backup_volume(self, volume: Dict, restore: bool) -> None:

        volume_name = volume.get('name')

        logger.info(f'Start Backup of volume {volume_name}')

        volume_source_path = volume.get('backup_source')
        volume_destination_path = volume.get('backup_destination')
        volume_destination_remote = volume.get('remote_destination')

        if volume_destination_remote:

            command = [
                'rsync',
                '-rlptDv',
                # '-av',
                # '--numeric-ids',
                '--delete',
                '--chown=0:0',
                '-e',
                'ssh',
                f'{volume_source_path}',
                f'{volume_destination_path}'
            ]
        else:

            if volume_destination_path and not Path(volume_destination_path).exists():
                logger.error('Could not run backup')
                logger.error(f'Backup folder {volume_destination_path} does not exist!')
                return

            command = [
                'rsync',
                '-rlptDv',
                # '-av',
                # '--numeric-ids',
                '--delete',
                '--chown=0:0',

                f'{volume_source_path}',
                f'{volume_destination_path}'
            ]

        # switch last two coment items when restore is set
        if self.restore:
            cmd_part_1 = command[-1]
            cmd_part_2 = command[-2]
            command[-1] = cmd_part_2
            command[-2] = cmd_part_1

        result = subprocess.run(args=command, capture_output=True)

        if result.returncode == 0:
            logger.info(f'Finished Backup of volume {volume_name}')
        else:
            logger.error(f'Could not finish Backup of volume {volume_name}. {result.stderr.decode("utf-8")}')

        return

    def _backup_cycle(self) -> None:
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

    def run(self) -> None:
        if self.restore or self.time_to_run == 'now':
            logger.info('start container backup tool')
            logger.info('start restore run')
            self._backup_cycle()
            logger.info(
                'Remove restore flag in docker-compose for next start up')
            quit()

        logger.info('start container backup tool')
        logger.info(f'next backup at {self.time_to_run}')
        while self.running:
            actual_time = datetime.now()
            actual_time_hour_minute_str = (actual_time.strftime('%H:%M'))

            if actual_time_hour_minute_str == self.time_to_run:
                if not self.backup_started:
                    self.backup_started = True
                    self._backup_cycle()

                    logger.info('backup done')
                    logger.info(f'next backup at {self.time_to_run}')
            else:
                self.backup_started = False

            time.sleep(5)


if __name__ == '__main__':
    pb = PodmanBackup()
    pb.run()
