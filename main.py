import argparse
import uvicorn
import docker

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest

from src.metrics_collector import MetricsCollector
from src.logger import log_ini_path, logger
from src.config import Config

app = FastAPI()


@app.get('/metrics', response_class=PlainTextResponse)
async def metrics() -> str:
    """
    Endpoint for returning Prometheus metrics.

    :return: Plain text containing the metrics.
    """
    docker_metrics.collect_metrics()
    return generate_latest()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run the Prometheus-Docker-Exporter')
    parser.add_argument('-c', '--config', type=str, help='Path to the config file',
                        default='/opt/docker-exporter/src/config.yml')
    args = parser.parse_args()

    config = Config(args.config)
    ip = config.get('ip')
    port = config.get('port')
    tls_cert = config.get('tls_cert')
    tls_key = config.get('tls_key')

    docker = docker.from_env()
    docker_metrics = MetricsCollector(docker)

    try:
        if tls_cert and tls_key:
            uvicorn.run(app, host=ip, port=port, ssl_keyfile=tls_key, ssl_certfile=tls_cert, log_config=log_ini_path)
        else:
            uvicorn.run(app, host=ip, port=port, log_config=log_ini_path)
    except Exception as e:
        logger.exception(f"Failed to bind the app to {ip}:{port} - {str(e)}")
