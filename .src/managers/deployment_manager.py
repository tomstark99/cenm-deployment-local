import os
import multiprocessing
from typing import List, Dict
from time import sleep
from utils import Logger, SystemInteract, CenmTool
from services.base_services import DeploymentService

class DeploymentManager:
    """Deployment manager for handling a standard CENM deployment.

    Args:
        services:
            A list of services to deploy.

    """

    def __init__(self, services: List[DeploymentService]):
        self.deployment_services = {s.artifact_name: s for s in services}
        self.functions = {s.artifact_name: s.deploy for s in services}
        self.processes = []
        self.versions = self._get_version_dict()
        self.logger = Logger().get_logger(__name__)
        self.sysi = SystemInteract()

    def _get_version_dict(self) -> Dict[str, str]:
        with open(".env", 'r') as f:
            args = {key:value for (key,value) in [x.strip().split('=') for x in f.readlines()]}
        return args
    
    def _setup_auth(self):
        self.logger.info("Running initial setupAuth.sh")
        self.sysi.run("(cd cenm-auth/setup-auth && bash setupAuth.sh)")

        cenm_tool = CenmTool(self.versions['NMS_VISUAL_VERSION'])

        tokens = cenm_tool.cenm_subzone_deployment_init()
        self.logger.info(f"Subzone tokens: {tokens}")

        zones = cenm_tool.get_subzones()
        
        if len(zones) > 0:
            self.logger.info(f"Subzones: {zones}, will only set permissions for {zones[0]}")
            self.sysi.run(f'(cd cenm-auth/setup-auth/roles && for file in *.json; do perl -i -pe "s/<SUBZONE_ID>/{zones[0]}/g" $file; done)')
            self.logger.info("Running setupAuth.sh with updated zone permissions")
            self.sysi.run("(cd cenm-auth/setup-auth && bash setupAuth.sh)")

    def deploy_services(self, health_check_frequency: int):
        """Deploy services in a standard CENM deployment.
        
        """
        try:
            self.logger.info("Starting the cenm deployment")
            self.logger.info(type(self.functions))
            self.logger.info(self.functions)
            for service, function in self.functions.items():
                service_object = self.deployment_services[service]
                self.logger.info(f'attempting to deploy {service}')
                process = multiprocessing.Process(target=function, name=service, daemon=True)
                self.processes.append(process)
                process.start()
                self.logger.info(f'deployed {service} waiting {service_object.deployment_time} seconds until next service')
                sleep(service_object.deployment_time)

            self.logger.info('All services deployed, setting up subzones')
            self._setup_auth()
            self.logger.info('Subzones setup, starting health check')
            
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
                sleep(health_check_frequency)

        except KeyboardInterrupt:
            self.logger.debug('Keyboard interrupt detected, terminating processes')
            for process in self.processes:
                self.logger.info(f'Terminating {process}')
                process.terminate()
                self.logger.info(f'Waiting for {process} to exit gracefully')
                process.join()
            self.logger.info('All processes terminated, exiting')
            exit(1)