import glob
import multiprocessing
from typing import List, Dict
from time import sleep
from utils import Logger, SystemInteract
from services.base_services import NodeDeploymentService

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
    def __init__(self, node: NodeDeploymentService, node_count: int):
        self.base_node = node
        self.node_count = node_count
        self.new_nodes = self._create_deployment_nodes()
        self.deployment_nodes = {f'{s.artifact_name}{i}': s for i, s in enumerate(self.new_nodes, 1)}
        self.functions = {f'{s.artifact_name}{i}': s.deploy for i, s in enumerate(self.new_nodes, 1)}
        self.processes = []
        self.versions = self._get_version_dict()
        self.logger = Logger().get_logger(__name__)
        self.sysi = SystemInteract()

    def _create_deployment_nodes(self) -> List[NodeDeploymentService]:
        existing_nodes = glob.glob("cenm-node-*")
        if len(existing_nodes) > 0 and self.node_count == 0:
            return [self.base_node._copy(new_dir=f'node-{i}') for i in range(1, len(existing_nodes)+1)]
        else:
            if len(existing_nodes) > 0 and self.node_count > 0 and len(existing_nodes) != self.node_count:
                raise NodeCountMismatchException()
            else:
                return [self.base_node._copy(new_dir=f'node-{i}') for i in range(1, self.node_count+1)]

    def _all_nodes(self) -> List[NodeDeploymentService]:
        return [self.base_node, *self.new_nodes]

    def clean_deployment_nodes(self,
        clean_deep: bool,
        clean_artifacts: bool,
        clean_certs: bool,
        clean_runtime: bool
    ):
        for node in self.new_nodes:
            if clean_deep:
                node.clean_all()
                self.sysi.remove(node.dir)
                continue
            if clean_artifacts:
                node.clean_artifacts()
            if clean_certs:
                node.clean_certificates()
            if clean_runtime:
                node.clean_runtime()

    def _get_version_dict(self) -> Dict[str, str]:
        with open(".env", 'r') as f:
            args = {key:value for (key,value) in [x.strip().split('=') for x in f.readlines()]}
        return args

    def _wait_for_service_termination(self):
            def _get_processes() -> int:
                return int(self.sysi.run_get_stdout(
                    'ps | grep -E ".*(cd cenm-node-[0-9]+ \&\&.*\&\& java -jar).+(\.jar).+(\.conf).*" | wc -l | sed -e "s/^ *//g"'
                ))

            java_processes = _get_processes()
            while int(java_processes) > 0:
                self.logger.info(f'Waiting for {java_processes} processes to terminate')
                sleep(5)
                java_processes = _get_processes()

    def deploy_nodes(self, health_check_frequency: int):
        """Deploy nodes in a standard CENM deployment.
        
        """
        try:
            self.logger.info("Starting the node deployment")
            service_deployments = '\n'.join([f'{service}: {service_info}' for service, service_info in self.functions.items()])
            self.logger.info(f'Deploying:\n\n{service_deployments}\n')
            for service, function in self.functions.items():
                service_object = self.deployment_nodes[service]
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