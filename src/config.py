import os
import yaml

DEFAULT_CONFIG: dict = {
    'ip': 'localhost',
    'port': 9375,
    'tls_cert': None,
    'tls_key': None,
}


class Config:
    """
    A class for loading the configuration for the metrics exporter.
    """

    def __init__(self, config_path: str) -> None:
        """
        Initializes the Config object.

        :param config_path: The path to the configuration file.
        """
        self.config: dict = DEFAULT_CONFIG
        if os.path.exists(config_path):
            with open(config_path) as f:
                self.config.update(yaml.safe_load(f))

    def get(self, key: str) -> any:
        """
        Gets a value from the configuration dictionary.

        :param key: The key for the value to get.
        :return: The value associated with the key, or None if the key is not found.
        """
        return self.config.get(key)
