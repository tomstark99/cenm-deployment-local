import os
from abc import ABC
from pyhocon import ConfigFactory
from managers.download_manager import DownloadManager
from utils import SystemInteract, Logger, Constants
import glob
import logging

class BaseService(ABC):
    """Base service for all services to inherit.

    Args:
        abb:
            The abbreviation of the service.
        dir:
            The directory for the service.
        plugin:
            Whether the service is a plugin.
        repo:
            Whether the service has its own repository.
        artifact_name:
            The name of the artifact.
        version:
            The version of the artifact.
        ext:
            The extension of the artifact.
        url:
            The url to download the artifact from.
        dlm:
            A download manager.
        
    """
    def __init__(self,
        abb: str,
        dir: str,
        artifact_name: str, 
        version: str, 
        ext: str, 
        url: str,
        username: str,
        password: str
    ):
        self.abb = abb
        self.dir = f'cenm-{dir}'
        self.artifact_name = artifact_name
        self.ext = ext
        self.version = version
        self.url = self.__build_url(url)
        self.dlm = DownloadManager(username, password)
        self.sysi = SystemInteract()
        self.error = False

    def __str__(self) -> str:
        return f"BaseService[{self.abb}, {self.dir}, {self.artifact_name}, {self.ext}, {self.version}]"

    def __repr__(self):
        return self.__str__()
        
    # internal url builder
    def __build_url(self, url: str):
        return f'{url}/{self.artifact_name}/{self.version}/{self.artifact_name}-{self.version}.{self.ext}'

    def _zip_name(self):
        return f'{self.artifact_name}-{self.version}.{self.ext}'
    
    def _clone_repo(self):
        if not self.sysi.path_exists(self.dir):
            print(f'Cloning {self.dir}')
            self.sysi.run(f'git clone {Constants.GITHUB_URL.value}/{self.dir}.git --quiet')

    def _check_presence(self) -> bool:
        for _, _, files in os.walk(self.dir):
            if f'{self.artifact_name}.jar' in files or f'{self.artifact_name}-{self.version}.jar' in files:
                print(f'{self.artifact_name}-{self.version} already exists. Skipping.')
                return True
        return False
    
    def _move(self):
        self.sysi.run(f'mv {self._zip_name()} {self.dir}')
        if self.ext == "zip":
            self.sysi.run(f'(cd {self.dir} && unzip -q {self._zip_name()} && rm {self._zip_name()})')

    def download(self) -> bool:
        self._clone_repo()
        if self._check_presence():
            return
        # If artifact not present then download it
        print(f'Downloading {self._zip_name()}')
        self.error = self.dlm.download(self.url)
        self._move()
        return self.error
    
class DeploymentService(BaseService):
    """Base service for the the services that also can be deployed

    Args:
        first 8 args:
            passed to BaseService constructor (see above)
        config_file:
            The name of the configuration file for the service
        deployment_time:
            The time taken for the service to deploy (average)
            this gives an indication how long the deployment manager
            should sleep before starting the next service

    """
    def __init__(self,
        abb: str,
        dir: str,
        artifact_name: str, 
        version: str, 
        ext: str, 
        url: str,
        username: str,
        password: str,
        config_file: str,
        deployment_time: int
    ):
        super().__init__(
            abb, 
            dir, 
            artifact_name, 
            version, 
            ext, 
            url,
            username,
            password
        )
        logging_manager = Logger()
        self.logger = logging_manager.get_logger(dir)
        self.runtime_files = Constants.RUNTIME_FILES.value
        self.config_file = config_file
        self.deployment_time = deployment_time

    def __str__(self) -> str:
        return f"DeploymentService[{self.abb}, {self.dir}, {self.artifact_name}, {self.ext}, {self.version}]"

    def __repr__(self):
        return self.__str__()
        
    def deploy(self):
        self.logger.info(f'Thread started to deploy {self.artifact_name}')
        while True:
            try:
                self.logger.debug(f'[Running] (cd {self.dir} && java -jar {self.artifact_name}.jar -f {self.config_file}) to start {self.artifact_name} service')
                exit_code = self.sysi.run_get_exit_code(f'(cd {self.dir} && java -jar {self.artifact_name}.jar -f {self.config_file})')
                if exit_code != 0:
                    raise RuntimeError(f'{self.artifact_name} service stopped')
            except:
                self.logger.warning(f'{self.artifact_name} service stopped. Restarting...')

    def validate(self) -> str:
        try:
            ConfigFactory.parse_file(f'{self.dir}/{self.config_file}')
            return ""
        except Exception as e:
            return str(e)

    def clean_runtime(self):
        for root, dirs, files in os.walk(self.dir):
            for dir in dirs:
                if dir in self.runtime_files['dirs']:
                    self.sysi.remove(os.path.join(root, dir))

    def clean_artifacts(self):
        for root, dirs, files in os.walk(self.dir):
            for file in files:
                if file.endswith('.jar'):
                    self.sysi.remove(os.path.join(root, file))
                elif file in ["cenm", "cenm.cmd"]:
                    self.sysi.remove(os.path.join(root, file))

    def clean_certificates(self):
        for root, dirs, files in os.walk(self.dir):
            for file in files:
                if file.endswith('.jks') or file.endswith('.crl'):
                    self.sysi.remove(os.path.join(root, file))

    def clean_all(self):
        self.sysi.remove(self.dir)

class NodeDeploymentService(DeploymentService):
    """Service for Corda Node

    """
    def __str__(self) -> str:
        return f"NodeDeploymentService[{self.abb}, {self.dir}, {self.artifact_name}, {self.ext}, {self.version}]"

    def __repr__(self):
        return self.__str__()

    def _is_registered(self) -> bool:
        return glob.glob(f'cenm-notary/nodeInfo-*')

    def _register_node(self, artifact_name):
        self.logger.info('Registering node to the network')
        exit_code = -1
        while exit_code != 0:
            self.logger.debug(f'[Running] (cd {self.dir} && java -jar {artifact_name}.jar -f {self.config_file} --initial-registration --network-root-truststore ./certificates/network-root-truststore.jks --network-root-truststore-password trustpass) to start {self.artifact_name} service')
            exit_code = self.sysi.run_get_exit_code(f'(cd {self.dir} && java -jar {artifact_name}.jar -f {self.config_file} --initial-registration --network-root-truststore ./certificates/network-root-truststore.jks --network-root-truststore-password trustpass)')
        self.logger.info(f'Sleeping for 2 minutes to allow registration to complete and for network parameters to be signed')
        self.sysi.sleep(120)

    def deploy(self):
        artifact_name = f'{self.artifact_name}-{self.version}'

        if not self._is_registered():
            self._register_node(artifact_name)
        while True:
            try:
                self.logger.debug(f'[Running] (cd {self.dir} && java -jar {artifact_name}.jar -f {self.config_file}) to start {self.artifact_name} service')
                exit_code = self.sysi.run_get_exit_code(f'(cd {self.dir} && java -jar {artifact_name}.jar -f {self.config_file})')
                if exit_code != 0:
                    raise RuntimeError(f'{self.artifact_name} service stopped')
            except:
                self.logger.warning(f'{self.artifact_name} service stopped. Restarting...')

    def clean_runtime(self):
        for root, dirs, files in os.walk(self.dir):
            for file in files:
                if file.startswith("nodeInfo"):
                    self.sysi.remove(os.path.join(root, file))
                if file in self.runtime_files['notary_files']:
                    self.sysi.remove(os.path.join(root, file), silent=True)
        super().clean_runtime()