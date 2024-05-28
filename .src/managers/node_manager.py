import glob
import multiprocessing
from typing import List, Dict
from time import sleep
from utils import Logger, SystemInteract, FirewallTool
from services.base_services import DeploymentService, NodeDeploymentService

class NodeCountMismatchException(Exception):
    def __init__(self):
        super().__init__("Node count specified doesn't match the given number")

class NodeManager:
    """Deployment manager for handling a node deployments within CENM.

    Args:
        node:
            The base node used, to create new nodes
        node_count:
            The number of nodes to deploy

    """
    def __init__(self, 
        node: NodeDeploymentService, 
        node_count: int,
        artemis: DeploymentService = None,
        ha_tools: DeploymentService = None,
        firewall_services: List[DeploymentService] = None
    ):
        self.base_node = node
        self.node_count = node_count
        self.firewall = firewall_services is not None
        self.new_nodes = self._create_deployment_nodes()
        self.deployment_services = self._build_deployment_dict(artemis, firewall_services)
        self.functions = {service_name: service.deploy for service_name, service in self.deployment_services.items()}
        self.processes = []
        self.ha_tools = ha_tools
        self.versions = self._get_version_dict()
        self.logger = Logger().get_logger(__name__)
        self.sysi = SystemInteract()

    def _create_deployment_nodes(self) -> List[DeploymentService]:
        existing_nodes = glob.glob("cenm-node-*")
        if len(existing_nodes) > 0 and self.node_count == 0:
            return [self.base_node._copy(new_dir=f'node-{i}', new_firewall=self.firewall) for i in range(1, len(existing_nodes)+1)]
        else:
            if len(existing_nodes) > 0 and self.node_count > 0 and len(existing_nodes) != self.node_count:
                raise NodeCountMismatchException()
            else:
                return [self.base_node._copy(new_dir=f'node-{i}', new_firewall=self.firewall) for i in range(1, self.node_count+1)]

    def _build_deployment_dict(self, artemis: DeploymentService, firewall_services: List[DeploymentService]) -> Dict[str, DeploymentService]:
        if self.firewall:
            deployment = {artemis.artifact_name: artemis}
            for i, node in enumerate(self.new_nodes, 1):
                deployment[f'{node.artifact_name}{i}'] = node
            for i, firewall_service in enumerate(firewall_services, 1):
                deployment[f'{firewall_service.artifact_name}{i}'] = firewall_service
        else:
            deployment = {f'{s.artifact_name}{i}': s for i, s in enumerate(self.new_nodes, 1)}
        return deployment

    def _all_nodes(self) -> List[DeploymentService]:
        return [self.base_node, *self.new_nodes]

    def _get_version_dict(self) -> Dict[str, str]:
        with open(".env", 'r') as f:
            args = {key:value for (key,value) in [x.strip().split('=') for x in f.readlines()]}
        return args

    def _wait_for_service_termination(self):
            def _get_processes() -> int:
                node_processes = int(self.sysi.run_get_stdout(
                    'ps | grep -E ".*(cd cenm-node-[0-9]+ \&\&.*\&\& java -jar).+(\.jar).+(\.conf).*" | wc -l | sed -e "s/^ *//g"'
                ))
                firewall_processes = int(self.sysi.run_get_stdout(
                    'ps | grep -E ".*(cd corda-(bridge|float).+\&\& java -jar).+(\.jar).+(\.conf).*" | wc -l | sed -e "s/^ *//g"'
                ))
                return node_processes + firewall_processes if self.firewall else node_processes

            java_processes = _get_processes()
            while int(java_processes) > 0:
                self.logger.info(f'Waiting for {java_processes} processes to terminate')
                sleep(5)
                java_processes = _get_processes()

    def _setup_firewall(self):
        firewall_tool = FirewallTool(self.base_node.artifact_name, self.base_node.version)
        firewall_tool.setup_firewall()

    def deploy_nodes(self, health_check_frequency: int):
        """Deploy nodes in a standard CENM deployment.
        
        """
        try:
            self.logger.info("Starting the node deployment")
            service_deployments = '\n'.join([f'{service}: {service_info}' for service, service_info in self.functions.items()])
            self.logger.info(f'Deploying:\n\n{service_deployments}\n')
            if self.firewall:
                firewall_idx = range(len(self.functions))[-2:]
                functions_1 = {service: function for i, (service, function) in enumerate(self.functions.items()) if i not in firewall_idx}
                functions_2 = {service: function for i, (service, function) in enumerate(self.functions.items()) if i in firewall_idx}
                for service, function in functions_1.items():
                    service_object = self.deployment_services[service]
                    self.logger.info(f'attempting to deploy {service}')
                    process = multiprocessing.Process(target=function, name=service, daemon=True)
                    self.processes.append(process)
                    process.start()
                    self.logger.info(f'deployed {service} waiting {service_object.deployment_time} seconds until next service')
                    sleep(service_object.deployment_time)

                self.logger.info('Setting up firewall')
                self._setup_firewall()
                self.logger.info('Firewall setup complete, deploying firewall')

                for service, function in functions_2.items():
                    service_object = self.deployment_services[service]
                    self.logger.info(f'attempting to deploy {service}')
                    process = multiprocessing.Process(target=function, name=service, daemon=True)
                    self.processes.append(process)
                    process.start()
                    self.logger.info(f'deployed {service} waiting {service_object.deployment_time} seconds until next service')
                    sleep(service_object.deployment_time)
            else:
                for service, function in self.functions.items():
                    service_object = self.deployment_services[service]
                    self.logger.info(f'attempting to deploy {service}')
                    process = multiprocessing.Process(target=function, name=service, daemon=True)
                    self.processes.append(process)
                    process.start()
                    self.logger.info(f'deployed {service} waiting {service_object.deployment_time} seconds until next service')
                    sleep(service_object.deployment_time)
            
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
            exit(1)

    def clean_deployment_nodes(self,
        clean_deep: bool,
        clean_artifacts: bool,
        clean_certs: bool,
        clean_runtime: bool
    ):
        for service in self.deployment_services.values():
            if clean_deep:
                service.clean_all()
                try:
                    self.sysi.remove(f'cenm-{service.dir}')
                except:
                    continue
            if clean_artifacts:
                service.clean_artifacts()
            if clean_certs:
                service.clean_certificates()
            if clean_runtime:
                service.clean_runtime()
        if self.firewall and clean_certs:
            self.sysi.remove('cenm-node/artemis/artemis.jks', silent=True)
            self.sysi.remove('cenm-node/artemis/artemis-truststore.jks', silent=True)
        if self.firewall and clean_runtime:
            self.ha_tools.clean_runtime()
        if self.firewall and clean_deep:
            self.ha_tools.clean_all()
