import logging
from typing import List
from services.base_services import DeploymentService
from utils import SystemInteract

class ConfigError(Exception):
    def __init__(self, service, message):
        super().__init__("""
Config exception for service: {}

    The following error was found while parsing the config file: {}
        """.format(service, message))

class ConfigManager:

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.sysi = SystemInteract()

    def validate(self, services: List[DeploymentService]):
        validation_errors = {}
        for service in services:
            self.logger.info(f'validating {service.artifact_name} config')
            validation_errors[service.artifact_name] = service.validate_config()

        if any(validation_errors.values()):
            exceptions = []
            for service, message in validation_errors.items():
                if message:
                    self.logger.error(f'{service} config validation failed')
                    exceptions.append(ConfigError(service, message))
            self.logger.error("There were config validation errors, check the logs")
            raise ExceptionGroup("Combined config exceptions", exceptions)
