import os
import multiprocessing
from typing import List
from time import sleep
from utils import Logger
from services.base_services import DeploymentService

class DeploymentManager:
    """Deployment manager for handling a standard CENM deployment.

    Args:
        services:
            A list of services to deploy.

    """

    def __init__(self, services: List[DeploymentService]):
        self.deployment_services = services
        self.functions = {s.artifact_name: s.deploy for s in self.deployment_services}
        self.processes = []
        self.logger = Logger().get_logger(__name__)

    def deploy_services(self):
        """Deploy services in a standard CENM deployment.
        
        """
        try:
            self.logger.info("Starting the cenm deployment")
            self.logger.info(type(self.functions))
            self.logger.info(self.functions)
            for service, function in self.functions.items():
                self.logger.info(f'attempting to deploy {service}')
                process = multiprocessing.Process(target=function, name=service, daemon=True)
                self.processes.append(process)
                process.start()
                self.logger.info(f'deployed {service} waiting 30 seconds until next service')
                sleep(30)
            
            while True:
                self.logger.info('Running process health check')
                for process in self.processes:
                    process.join(timeout=0)
                    if process.is_alive():
                        self.logger.info(f'{process} is healthy')
                    else:
                        self.logger.error(f'{process} is unhealthy, restarting')
                        process.terminate()
                        self.processes.remove(process)
                        new_process = multiprocessing.Process(target=self.functions[process.name], name=process.name, daemon=True)
                        new_process.start()
                        self.processes.append(new_process)
                sleep(30)

        except KeyboardInterrupt:
            self.logger.debug('Keyboard interrupt detected, terminating processes')
            for process in self.processes:
                self.logger.info(f'Terminating {process}')
                process.terminate()
                self.logger.info(f'Waiting for {process} to exit gracefully')
                process.join()
            self.logger.info('All processes terminated, exiting')
            exit(1)