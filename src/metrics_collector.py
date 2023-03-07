import docker
import concurrent.futures
from docker import errors
from docker.models.containers import Container
from prometheus_client import Gauge
from fastapi.exceptions import HTTPException
from typing import Any, Dict, List

from logger import *


class MetricsCollector:
    """
    A class for collecting Docker container metrics and exposing them via Prometheus.
    """

    def __init__(self, docker_client: docker.DockerClient):
        """
        Initializes the MetricsCollector object.

        :param docker_client: An instance of DockerClient to interact with Docker.
        """
        self.docker = docker_client
        self.labels = ['container_id', 'container_name']
        self.cpu_percent = Gauge('docker_container_cpu_percentage', 'CPU percentage usage by container', self.labels)
        self.mem_percent = Gauge('docker_container_memory_percentage', 'Memory percentage usage by container',
                                 self.labels)
        self.mem_usage = Gauge('docker_container_memory_usage_bytes', 'Memory usage by container', self.labels)
        self.mem_limit = Gauge('docker_container_memory_limit_bytes', 'Memory limit of the container', self.labels)
        self.net_rx_bytes = Gauge('docker_container_network_rx_bytes', 'Network bytes received by container',
                                  self.labels)
        self.net_tx_bytes = Gauge('docker_container_network_tx_bytes', 'Network bytes transmitted by container',
                                  self.labels)
        self.block_read_bytes = Gauge('docker_container_block_read_bytes', 'Block bytes read by container', self.labels)
        self.block_write_bytes = Gauge('docker_container_block_write_bytes', 'Block bytes written by container',
                                       self.labels)
        self.pids = Gauge('docker_container_pids', 'Number of processes by container', self.labels)

    def get_active_containers(self) -> List[Container]:
        """
        Gets a list of active Docker containers.

        :return: A list of Container objects representing active Docker containers.
        """
        try:
            containers = self.docker.containers.list()
            return containers
        except docker.errors.APIError as e:
            logger.exception(f'Failed to get active containers: {e}')
            raise HTTPException(status_code=500, detail=f'Failed to get active containers: {e}')

    def get_container_stats(self, container_id: str) -> Dict[str, Any]:
        """
        Gets stats for a specified Docker container.

        :param container_id: The ID of the container to get stats for.
        :return: A dictionary containing statistics for the specified container.
        """
        try:
            container = self.docker.containers.get(container_id)
            stats = container.stats(stream=False)
            return stats
        except docker.errors.NotFound as e:
            logger.exception(f'Failed to get container stats for {container_id}: {e}')
            raise HTTPException(status_code=500, detail=f'Failed to get container stats for {container_id}: {e}')

    @staticmethod
    def parse_container_stats(stats: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parses Docker container stats and returns a dictionary of metrics.

        :param stats: A dictionary containing Docker container stats.
        :return: A dictionary of metrics parsed from the stats.
        """
        container_name = stats['name'].lstrip('/')

        cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - stats['precpu_stats']['cpu_usage']['total_usage']
        system_delta = stats['cpu_stats']['system_cpu_usage'] - stats['precpu_stats']['system_cpu_usage']
        online_cpus = stats['cpu_stats']['online_cpus']
        cpu_percent = round((cpu_delta / system_delta) / online_cpus * 100.0, 2)

        mem_usage = stats['memory_stats']['usage']
        mem_limit = stats['memory_stats']['limit']
        mem_percent = round((mem_usage / mem_limit) * 100.0, 2)

        net_rx_bytes = stats['networks']['eth0']['rx_bytes']
        net_tx_bytes = stats['networks']['eth0']['tx_bytes']

        blkio_stats = stats['blkio_stats']['io_service_bytes_recursive']
        blkio_read_bytes = 0
        blkio_write_bytes = 0
        for stat in blkio_stats:
            if stat['major'] == 253 and stat['op'] == 'read':
                blkio_read_bytes += stat['value']
            elif stat['major'] == 253 and stat['op'] == 'write':
                blkio_write_bytes += stat['value']

        num_procs = stats['pids_stats']['current']

        return {
            'container_name': container_name,
            'cpu_percent': cpu_percent,
            'mem_usage': mem_usage,
            'mem_limit': mem_limit,
            'mem_percent': mem_percent,
            'net_rx_bytes': net_rx_bytes,
            'net_tx_bytes': net_tx_bytes,
            'blkio_read_bytes': blkio_read_bytes,
            'blkio_write_bytes': blkio_write_bytes,
            'num_procs': num_procs
        }

    def set_gauge_values(self, metrics: dict) -> None:
        """
        Sets the gauge values for the metrics collected by parsing the container stats.

        :param metrics: A dictionary containing the container metrics as returned by `parse_container_stats()`.
        :return: None
        """
        for container_id, stats in metrics.items():
            labels = [container_id, stats['container_name']]

            self.cpu_percent.labels(*labels).set(stats['cpu_percent'])
            self.mem_usage.labels(*labels).set(stats['mem_usage'])
            self.mem_limit.labels(*labels).set(stats['mem_limit'])
            self.mem_percent.labels(*labels).set(stats['mem_percent'])
            self.net_rx_bytes.labels(*labels).set(stats['net_rx_bytes'])
            self.net_tx_bytes.labels(*labels).set(stats['net_tx_bytes'])
            self.block_read_bytes.labels(*labels).set(stats['blkio_read_bytes'])
            self.block_write_bytes.labels(*labels).set(stats['blkio_write_bytes'])
            self.pids.labels(*labels).set(stats['num_procs'])

    def collect_metrics(self) -> None:
        """
        Collects Docker container metrics and updates Prometheus Gauges with the collected values.

        :return: None
        """
        containers = self.get_active_containers()
        metrics = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(containers)) as executor:
            future_to_container_id = {}
            for container in containers:
                future = executor.submit(self.get_container_stats, container.id)
                future_to_container_id[future] = container.id
            for future in concurrent.futures.as_completed(future_to_container_id):
                container_id = future_to_container_id[future]
                try:
                    stats = future.result()
                    metrics[container_id] = self.parse_container_stats(stats)
                except Exception as e:
                    logger.exception(f'Failed to collect metrics for container {container_id}: {e}')
                    raise HTTPException(status_code=500,
                                        detail=f'Failed to collect metrics for container {container_id}: {e}')

        self.set_gauge_values(metrics)
