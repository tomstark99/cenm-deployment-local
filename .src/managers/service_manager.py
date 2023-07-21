from services.services import *
from managers.database_manager import DatabaseManager
from managers.download_manager import DownloadManager
from managers.deployment_manager import DeploymentManager
from utils import *
from typing import List

class ServiceManager:
    """A manager to manage operations on all CENM services including:
        
        - Downloading Artifacts
        - Downloading Database Drivers
        - Deploying Services
        - Cleaning services

    Args:
        username:
            The username to use for the download.
        password:
            The password to use for the download.
        auth_version:
            The version of the auth service.
        gateway_version:
            The version of the gateway service.
        cenm_version:
            The version of cenm services.
        nms_visual_version:
            The version of nms visual services .
        corda_version:
            The version of Corda to be used.
    
    """
    def __init__(self,
        username: str,
        password: str,
        auth_version: str,
        gateway_version: str,
        cenm_version: str,
        nms_visual_version: str,
        corda_version: str
    ):
        self.base_url = Constants.BASE_URL.value#'https://software.r3.com/artifactory'
        self.ext_package = Constants.EXT_PACKAGE.value#'extensions-lib-release-local/com/r3/appeng'
        self.enm_package = Constants.ENM_PACKAGE.value#'r3-enterprise-network-manager/com/r3/enm'
        self.corda_package = Constants.CORDA_PACKAGE.value#'corda-releases/net/corda'
        self.repos = Constants.REPOS.value#['auth', 'gateway', 'idman', 'nmap', 'notary', 'node', 'pki', 'signer', 'zone']
        self.db_services = Constants.DB_SERVICES.value
        self.sysi = SystemInteract()
        self.printer = Printer(
            cenm_version,
            auth_version,
            gateway_version,
            nms_visual_version,
            corda_version
        )

        self.AUTH = AuthService(
            abb=            'auth',
            dir=            'auth',
            artifact_name=  'accounts-application',
            version=        auth_version,
            ext=            'jar',
            url=            f'{self.base_url}/{self.ext_package}/accounts',
            username=       username,
            password=       password,
            deployment_time=Constants.AUTH_DEPLOY_TIME.value)
        self.CLIENT = AuthClientService(
            abb=            'client',
            dir=            'auth',
            artifact_name=  'accounts-client',
            version=        auth_version,
            ext=            'jar',
            url=            f'{self.base_url}/{self.ext_package}/accounts',
            username=       username,
            password=       password)
        self.AUTH_PLUGIN = AuthPluginService(
            abb=            'auth-plugin',
            dir=            'auth',
            artifact_name=  'accounts-baseline-cenm',
            version=        cenm_version,
            ext=            'jar',
            url=            f'{self.base_url}/{self.enm_package}',
            username=       username,
            password=       password)
        self.GATEWAY = GatewayService(
            abb=            'gateway',
            dir=            'gateway',
            artifact_name=  'gateway-service',
            version=        gateway_version,
            ext=            'jar',
            url=            f'{self.base_url}/{self.ext_package}/gateway',
            username=       username,
            password=       password,
            deployment_time=Constants.GATEWAY_DEPLOY_TIME.value)
        self.GATEWAY_PLUGIN = GatewayPluginService(
            abb=            'gateway-plugin',
            dir=            'gateway',
            artifact_name=  'cenm-gateway-plugin',
            version=        nms_visual_version,
            ext=            'jar',
            url=            f'{self.base_url}/{self.enm_package}',
            username=       username,
            password=       password)
        self.CLI = CliToolService(
            abb=            'cli',
            dir=            'gateway',
            artifact_name=  'cenm-tool',
            version=        nms_visual_version,
            ext=            'zip',
            url=            f'{self.base_url}/{self.enm_package}',
            username=       username,
            password=       password)
        self.IDMAN = IdentityManagerService(
            abb=            'idman',
            dir=            'idman',
            artifact_name=  'identitymanager',
            version=        cenm_version,
            ext=            'zip',
            url=            f'{self.base_url}/{self.enm_package}/services',
            username=       username,
            password=       password,
            deployment_time=Constants.IDMAN_DEPLOY_TIME.value)
        self.CRR_TOOL = CrrToolService(
            abb=            'crr-tool',
            dir=            'idman',
            artifact_name=  'crr-submission-tool',
            version=        cenm_version,
            ext=            'zip',
            url=            f'{self.base_url}/{self.enm_package}/tools',
            username=       username,
            password=       password)
        self.NMAP = NetworkMapService(
            abb=            'nmap',
            dir=            'nmap',
            artifact_name=  'networkmap',
            version=        cenm_version,
            ext=            'zip',
            url=            f'{self.base_url}/{self.enm_package}/services',
            username=       username,
            password=       password,
            deployment_time=Constants.NMAP_DEPLOY_TIME.value)
        self.NOTARY = NotaryService(
            abb=            'notary',
            dir=            'notary',
            artifact_name=  'corda',
            version=        corda_version,
            ext=            'jar',
            url=            f'{self.base_url}/{self.corda_package}',
            username=       username,
            password=       password,
            deployment_time=Constants.NODE_DEPLOY_TIME.value)
        self.NODE = NodeService(
            abb=            'node',
            dir=            'node',
            artifact_name=  'corda',
            version=        corda_version,
            ext=            'jar',
            url=            f'{self.base_url}/{self.corda_package}',
            username=       username,
            password=       password,
            deployment_time=Constants.NODE_DEPLOY_TIME.value)
        self.CORDA_SHELL = CordaShellService(
            abb=            'shell',
            dir=            'node',
            artifact_name=  'corda-shell',
            version=        corda_version,
            ext=            'jar',
            url=            f'{self.base_url}/{self.corda_package}',
            username=       username,
            password=       password)
        self.PKI = PkiToolService(
            abb=            'pki',
            dir=            'pki',
            artifact_name=  'pki-tool',
            version=        cenm_version,
            ext=            'zip',
            url=            f'{self.base_url}/{self.enm_package}/tools',
            username=       username,
            password=       password)
        self.SIGNER = SignerService(
            abb=            'signer',
            dir=            'signer',
            artifact_name=  'signer',
            version=        cenm_version,
            ext=            'zip',
            url=            f'{self.base_url}/{self.enm_package}/services',
            username=       username,
            password=       password,
            deployment_time=Constants.SIGNER_DEPLOY_TIME.value)
        self.ZONE = ZoneService(
            abb=            'zone',
            dir=            'zone',
            artifact_name=  'zone',
            version=        cenm_version,
            ext=            'zip',
            url=            f'{self.base_url}/{self.enm_package}/services',
            username=       username,
            password=       password,
            deployment_time=Constants.ZONE_DEPLOY_TIME.value)

        self.db_manager = DatabaseManager(self.get_database_services(), DownloadManager(username, password))
        self.deployment_manager = DeploymentManager(self.get_deployment_services())

    def _get_all_services(self) -> List[BaseService]:
        return [
            self.AUTH,
            self.CLIENT,
            self.AUTH_PLUGIN,
            self.GATEWAY,
            self.GATEWAY_PLUGIN,
            self.CLI,
            self.IDMAN,
            self.CRR_TOOL,
            self.NMAP,
            self.NOTARY,
            self.NODE,
            self.CORDA_SHELL,
            self.PKI,
            self.SIGNER,
            self.ZONE
        ]

    def get_service(self, name: str) -> BaseService:
        for service in self._get_all_services():
            if service.artifact_name == name:
                return service
        raise ValueError(f'No service with name {name}')

    def get_deployment_services(self) -> List[DeploymentService]:
        """These services are returned in order they should be deployed

        For default deployments, don't change the order
        
        """
        return [
            self.IDMAN,
            self.SIGNER,
            self.NOTARY,
            self.NMAP,
            self.AUTH,
            self.GATEWAY,
            self.ZONE
        ]

    def get_database_services(self) -> List[BaseService]:
        return [service for service in self._get_all_services() if service.abb in self.db_services]

    def download_all(self):
        download_errors = {}
        for service in self._get_all_services():
            download_errors[service.artifact_name] = service.download()

        download_errors_db = self.db_manager.download()
        self.printer.print_end_of_script_report(download_errors, download_errors_db)

    def download_specific(self, services: List[str]):
        print("Downloading individual artifacts does not work with any other arguments, script will exit after downloading.")
        download_errors = {}
        for service in services:
            try:
                service = self.get_service(service)
                download_errors[service.artifact_name] = service.download()
            except ValueError as e:
                print(e)
                download_errors[service] = str(e)
        download_errors_db = self.db_manager.download()
        self.printer.print_end_of_script_report(download_errors, download_errors_db)

    def deploy_all(self, health_check_frequency: int):
        self.deployment_manager.deploy_services(health_check_frequency)

    def generate_certificates(self):
        self.PKI.generate()

    def clean_all(self,
        clean_deep: bool,
        clean_artifacts: bool,
        clean_certs: bool,
        clean_runtime: bool
    ):
        self.sysi.remove(".logs/*", silent=True)
        for service in [*self.get_deployment_services(), self.PKI]:
            if clean_deep:
                service.clean_all()
                continue
            if clean_artifacts:
                service.clean_artifacts()
            if clean_certs:
                service.clean_certificates()
            if clean_runtime:
                service.clean_runtime()

        