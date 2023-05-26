import os
import multiprocessing
import logging
from typing import List

class DeploymentManager:

    def __init__(self, services: List[Service]):
        self.deployment_services = services
        self.functions = {s.artifact_name:s.deploy for s in self.deployment_services}
        self.processes = []

    def deploy_services(self):
        try:
            logger.info("Starting the cenm deployment")
            logger.info(type(self.functions))
            logger.info(self.functions)
            for service, function in self.functions.items():
                logger.info(f'attempting to deploy {service}')
                process = multiprocessing.Process(target=function, name=service, daemon=True)
                self.processes.append(process)
                process.start()
                logger.info(f'deployed {service} waiting 30 seconds until next service')
                sleep(30)
            
            while True:
                logger.info('Running process health check')
                for process in self.processes:
                    process.join(timeout=0)
                    if process.is_alive():
                        logger.info(f'{process} is healthy')
                    else:
                        logger.error(f'{process} is unhealthy, restarting')
                        process.start()
                sleep(30)

        except KeyboardInterrupt:
            logger.debug('Keyboard interrupt detected, terminating processes')
            for process in self.processes:
                logger.info(f'Terminating {process}')
                process.terminate()
                logger.info(f'Waiting for {process} to exit gracefully')
                process.join()
            logger.info('All processes terminated, exiting')
            exit(1)