import glob
import logging
import multiprocessing
from typing import List, Dict
from time import sleep
from utils import SystemInteract, CenmTool
from services.base_services import DeploymentService

class DeploymentManager:
    """Deployment manager for handling a standard CENM deployment.

    Args:
        services:
            A list of services to deploy.

    """

    def __init__(self, services: List[DeploymentService]):
        self.deployment_services = {f'{s.artifact_name}-{s.dir}': s for s in services}
        self.functions = {f'{s.artifact_name}-{s.dir}': s.deploy for s in services}
        self.processes = []
        self.versions = self._get_version_dict()
        self.logger = logging.getLogger(__name__)
        self.sysi = SystemInteract()
    
    def _run_subzone_setup(self) -> bool:
        return all(service in self.deployment_services.keys() for service in ["accounts-application-cenm-auth", "gateway-service-cenm-gateway", "zone-cenm-zone"]) and (not self._node_info())

    def _get_version_dict(self) -> Dict[str, str]:
        with open(".env", 'r') as f:
            args = {key:value for (key,value) in [x.strip().split('=') for x in f.readlines()]}
        return args

    def _node_info(self) -> bool:
        return glob.glob(f'cenm-nmap/nodeInfo-*') and glob.glob(f'cenm-notary/nodeInfo*')
    
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
            self.logger.info("Setting subzone config")
            token = cenm_tool.cenm_set_subzone_config(zones[0])
            self.logger.info(f"Subzone network map token: {token}")

    def _wait_for_service_termination(self):
            def _get_processes() -> int:
                return int(self.sysi.run_get_stdout(
                    'ps | grep -E ".*(cd cenm-[a-z]+ \&\& java -jar).+(\.jar).+(\.conf)*.*" | wc -l | sed -e "s/^ *//g"'
                ))
            def _is_network_map_running() -> bool:
                return int(self.sysi.run_get_stdout(
                    'ps | grep -E ".*(java -jar networkmap\.jar.*\.conf).*" | wc -l | sed -e "s/^ *//g"'
                )) != 0
            
            java_processes = _get_processes()
            while int(java_processes) > 0:
                self.logger.info(f'Waiting for {java_processes} processes to terminate')
                sleep(5)
                java_processes = _get_processes()

            if _is_network_map_running():
                self.logger.info('Network map still running, terminating')
                nm_pid = self.sysi.run_get_stdout('ps | grep -E ".*(java -jar networkmap\.jar.*\.conf).*" | cut -d " " -f 1 | sed -e "s/^ *//g"')
                self.sysi.run(f'kill -9 {nm_pid}', silent=True)
                sleep(10)
                if _is_network_map_running():
                    nm_pid = self.sysi.run_get_stdout('ps | grep -E ".*(java -jar networkmap\.jar.*\.conf).*" | cut -d " " -f 1 | sed -e "s/^ *//g"')
                    print("""
The script failed to terminate the network map process. Please terminate the process manually by running:
    kill -9 {0}""".format(nm_pid))
                else:
                    self.logger.info('Network map terminated')

    def deploy_services(self, health_check_frequency: int):
        """Deploy services in a standard CENM deployment.
        
        """
        try:
            self.run_subzone_setup = self._run_subzone_setup()
            self.logger.info("Starting the cenm deployment")
            service_deployments = '\n'.join([f'{service}: {service_info}' for service, service_info in self.functions.items()])
            self.logger.info(f'Deploying:\n\n{service_deployments}\n')
            for service, function in self.functions.items():
                service_object = self.deployment_services[service]
                self.logger.info(f'attempting to deploy {service}')
                process = multiprocessing.Process(target=function, name=service, daemon=True)
                self.processes.append(process)
                process.start()
                self.logger.info(f'deployed {service} waiting {service_object.deployment_time} seconds until next service')
                sleep(service_object.deployment_time)

            if self.run_subzone_setup:
                self.logger.info('All services deployed, setting up subzones')
                self._setup_auth()
                self.logger.info('Subzones setup')
            
            self.logger.info('Starting health check')
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
                
            self._wait_for_service_termination()
            self.sysi.remove(".tmp-*", silent=True)
            self.logger.info('All processes terminated, exiting')
            exit(0)