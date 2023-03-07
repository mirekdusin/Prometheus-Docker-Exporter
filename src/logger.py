import logging.config
import os

log_ini_path = os.path.join(os.path.dirname(__file__), 'log.ini')
log_dir_path = os.path.join(os.path.dirname(__file__), '../log')

if not os.path.exists(log_dir_path):
    os.makedirs(log_dir_path)

logging.config.fileConfig(log_ini_path)
logger = logging.getLogger(__name__)
