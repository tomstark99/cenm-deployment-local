import os
from abc import ABC
from pyhocon import ConfigFactory
from managers.download_manager import DownloadManager
from utils import SystemInteract, Logger, Constants
from time import sleep
import multiprocessing
import glob
import uuid

class BaseService(ABC):
    """Base service for all services to inherit.

    Args:
        abb:
            The abbreviation of the service.
        dir:
            The directory for the service.
        artifact_name:
            The name of the artifact.
        version:
            The version of the artifact.
        ext:
            The extension of the artifact.
        url:
            The url to download the artifact from.
        username:
            Username to use for download manager.
        password:
            Password to use for download manager.
        
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
        self.dir = dir
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

    def _zip_name(self, no_version: bool = False):
        return f'{self.artifact_name}.{self.ext}' if no_version else f'{self.artifact_name}-{self.version}.{self.ext}'
    
    def _clone_repo(self):
        if not self.sysi.path_exists(self.dir):
            print(f'Cloning {self.dir}')
            self.sysi.run(f'git clone {Constants.GITHUB_URL.value}/{self.dir}.git --quiet')

    def _check_presence(self) -> bool:
        for _, _, files in os.walk(self.dir):
            if f'{self.artifact_name}.jar' in files or f'{self.artifact_name}-{self.version}.jar' in files:
                # Temporarily muting this message
                # print(f'{self.artifact_name}-{self.version} already exists. Skipping.')
                return True
        return False
    
    def _move(self):
        self.sysi.run(f'mv {self._zip_name()} {self.dir}')
        if self.ext == "zip":
            self.sysi.run(f'(cd {self.dir} && unzip -q {self._zip_name()} && rm {self._zip_name()})')

    def download(self) -> bool:
        self._clone_repo()
        if self._check_presence():
            return #self.dlm.validate_download(self.url)
        # If artifact not present then download it
        print(f'Downloading {self._zip_name()}')
        self.error = self.dlm.download(self.url)
        self._move()
        return self.error


class SignerPluginService(BaseService):
    """Base service for plugins used by the Signer service

    """
    def _handle_plugin(self):
        if not self.sysi.path_exists(f'{self.dir}/plugins'):
            self.sysi.run(f'mkdir {self.dir}/plugins')
        self.sysi.run(f'mv {self._zip_name()} {self.dir}/plugins')

    def download(self) -> bool:
        if self._check_presence():
            return
        # If artifact not present then download it
        print(f'Downloading {self._zip_name()}')
        self.error = self.dlm.download(self.url)
        self._handle_plugin()
        return self.error


class CordappService(BaseService):
    """Base service for CordDapps to be used by nodes

    """
    def _handle_cordapp(self):
        if not self.sysi.path_exists(f'{self.dir}/cordapps'):
            self.sysi.run(f'mkdir {self.dir}/cordapps')
        self.sysi.run(f'mv {self._zip_name()} {self.dir}/cordapps')
    
    def download(self) -> bool:
        if self._check_presence():
            return
        # If artifact not present then download it
        print(f'Downloading {self._zip_name()}')
        self.error = self.dlm.download(self.url)
        self._handle_cordapp()
        return self.error


class DeploymentService(BaseService):
    """Base service for the the services that also can be deployed

    Args:
        first 8 args:
            passed to BaseService constructor (see above).
        config_file:
            The name of the configuration file for the service.
        deployment_time:
            The time taken for the service to deploy (average)
            this gives an indication how long the deployment manager
            should sleep before starting the next service.
        certifiactes:
            The minimum number of certificates that the service
            should have before it can be deployed.

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
        deployment_time: int,
        certificates: int = None
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
        self.certificates = certificates

    def __str__(self) -> str:
        return f"DeploymentService[{self.abb}, {self.dir}, {self.artifact_name}, {self.ext}, {self.version}]"

    def __repr__(self):
        return self.__str__()

    def _get_cert_count(self) -> bool:
        cert_count = self.sysi.run_get_stdout(f"ls {self.dir}/certificates | xargs | wc -w | sed -e 's/^ *//g'")
        return int(cert_count)
        
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

    def validate_config(self) -> str:
        try:
            ConfigFactory.parse_file(f'{self.dir}/{self.config_file}')
            return ""
        except Exception as e:
            return str(e)

    def validate_certs(self) -> str:
        if self._get_cert_count() < self.certificates:
            return f'Certificate mismatch ({self._get_cert_count()} found, {self.certificates} expected)'
        else:
            return ""

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
    """Base Service for a Corda Node (can be used for both nodes and notaries)

    Args:
        first 11 args:
            passed to BaseService constructor (see above).
        firewall:
            If the node uses the Corda firewall.

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
        deployment_time: int,
        certificates: int = None,
        firewall: bool = False
    ):
        super().__init__(
            abb, 
            dir, 
            artifact_name, 
            version, 
            ext, 
            url,
            username,
            password,
            config_file,
            deployment_time,
            certificates
        )
        self.firewall = firewall

    def __str__(self) -> str:
        return f"NodeDeploymentService[{self.abb}, {self.dir}, {self.artifact_name}, {self.ext}, {self.version}]"

    def __repr__(self):
        return self.__str__()

    def _construct_new_node_dir(self, new_dir, new_firewall):
        self.sysi.run(f'cp -r {self.dir} cenm-{new_dir}')
        if new_firewall:
            self.sysi.run(f'cd cenm-{new_dir} && git checkout release/firewall', silent=True)
        node_number = new_dir.split("-")[-1]
        perl_dir = f'cenm-{new_dir}/node.conf'
        node_uuid = uuid.uuid4().hex[:5]
        self.sysi.perl(perl_dir, 'myLegalName.*O\\=\\K.*(?=, L\\=.*)', f'TestNode{node_number}-{node_uuid}')
        if not new_firewall:
            self.sysi.perl(perl_dir, 'p2pAddress.*:\\K.*(?=\\"\\\n)', f'60{node_number}11')
        self.sysi.perl(perl_dir, '^\\s*address.*:\\K.*(?=\\"\\\n)', f'60{node_number}12')
        self.sysi.perl(perl_dir, '^\\s*adminAddress.*:\\K.*(?=\\"\\\n)', f'60{node_number}13')
        self.sysi.perl(perl_dir, '^\\s*port \\= \\K.*(?=\\\n)', f'223{node_number}')

    def _copy(self, 
        new_dir: str, 
        new_firewall: bool
    ):
        new_node = NodeDeploymentService(
            abb=self.abb,
            dir=f'cenm-{new_dir}',
            artifact_name=self.artifact_name,
            version=self.version,
            ext=self.ext,
            url=self.url,
            username=self.dlm.username,
            password=self.dlm.password,
            config_file=self.config_file,
            deployment_time=self.deployment_time,
            certificates=self.certificates,
            firewall=new_firewall
        )
        if not self.sysi.path_exists(f'cenm-{new_dir}'):
            self._construct_new_node_dir(new_dir, new_firewall)
            new_node.download()
        return new_node

    def _is_registered(self) -> bool:
        return glob.glob(f'{self.dir}/nodeInfo-*')

    def _register_node(self, artifact_name):
        self.logger.info('Registering node to the network')
        exit_code = -1
        while exit_code != 0:
            self.logger.debug(f'[Running] (cd {self.dir} && java -jar {artifact_name}.jar initial-registration --network-root-truststore ./certificates/network-root-truststore.jks --network-root-truststore-password trustpass -f {self.config_file}) to start {self.artifact_name} service')
            exit_code = self.sysi.run_get_exit_code(f'(cd {self.dir} && java -jar {artifact_name}.jar initial-registration --network-root-truststore ./certificates/network-root-truststore.jks --network-root-truststore-password trustpass -f {self.config_file})')
        self.logger.info(f'Sleeping for 2 minutes to allow registration to complete and for network parameters to be signed')
        self.sysi.sleep(120)

    def _wait_for_bridge(self):
        while int(self.sysi.run_get_stdout('ps | grep -E ".*(cd corda-bridge.+\&\& java -jar).+(\.jar).+(\.conf).*" | wc -l | sed -e "s/^ *//g"')) == 0:
            sleep(5)
            self.logger.info('Waiting for Corda Firewall (bridge) to start')
        self.logger.info('Corda Firewall (bridge) started, starting Artemis')

    def deploy(self):
        artifact_name = f'{self.artifact_name}-{self.version}'

        if not self._is_registered():
            self._register_node(artifact_name)
        if self.firewall:
            self._wait_for_bridge()
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


class CordaFirewallDeploymentService(DeploymentService):
    """Base Service for a Corda Firewall deployment
    
    """
    def _wait_for_certs(self):
        while not glob.glob(f'{self.dir}/network-parameters'):
            self.logger.info('Waiting for network-parameters file to be created')
            sleep(5)

    def _get_cert_count(self) -> bool:
        cert_count_1 = self.sysi.run_get_stdout(f"ls {self.dir}/artemis | xargs | wc -w | sed -e 's/^ *//g'")
        cert_count_2 = self.sysi.run_get_stdout(f"ls {self.dir}/tunnel | xargs | wc -w | sed -e 's/^ *//g'")
        return int(cert_count_1)+int(cert_count_2)

    def deploy(self):
        artifact_name = f'{self.artifact_name}-{self.version}'

        self.logger.info(f'Thread started to deploy {self.artifact_name}')
        self._wait_for_certs()
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
            for dir in dirs:
                if dir in self.runtime_files['firewall_dirs']:
                    self.sysi.remove(os.path.join(root, dir))
            for file in files:
                if file in self.runtime_files['firewall_files']:
                    self.sysi.remove(os.path.join(root, file))