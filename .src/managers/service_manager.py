from services.services import *
from managers.config_manager import ConfigManager
from managers.database_manager import DatabaseManager
from managers.download_manager import DownloadManager
from managers.deployment_manager import DeploymentManager
from managers.node_manager import NodeManager
from utils import *
from typing import List, Dict, Tuple, Any

class ServiceError(Exception):
    def __init__(self, service, dir):
        super().__init__("""
{} artifact not found in {} directory, please try and download agian.
        """.format(service, dir))

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
        corda_version: str,
        node_count: int
    ):
        self.base_url = Constants.BASE_URL.value
        self.ext_package = Constants.EXT_PACKAGE.value
        self.enm_package = Constants.ENM_PACKAGE.value
        self.corda_package = Constants.CORDA_PACKAGE.value
        self.cordapp_package = Constants.CORDAPP_PACKAGE.value
        self.repos = Constants.REPOS.value
        self.db_services = Constants.DB_SERVICES.value
        self.node_count = node_count
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
            dir=            'cenm-auth',
            artifact_name=  'accounts-application',
            version=        auth_version,
            ext=            'jar',
            url=            f'{self.base_url}/{self.ext_package}/accounts',
            username=       username,
            password=       password,
            config_file=    'auth.conf',
            deployment_time=Constants.AUTH_DEPLOY_TIME.value,
            certificates=   2)
        self.CLIENT = AuthClientService(
            abb=            'client',
            dir=            'cenm-auth',
            artifact_name=  'accounts-client',
            version=        auth_version,
            ext=            'jar',
            url=            f'{self.base_url}/{self.ext_package}/accounts',
            username=       username,
            password=       password)
        self.AUTH_PLUGIN = AuthPluginService(
            abb=            'auth-plugin',
            dir=            'cenm-auth',
            artifact_name=  'accounts-baseline-cenm',
            version=        cenm_version,
            ext=            'jar',
            url=            f'{self.base_url}/{self.enm_package}',
            username=       username,
            password=       password)
        self.GATEWAY = GatewayService(
            abb=            'gateway',
            dir=            'cenm-gateway',
            artifact_name=  'gateway-service',
            version=        gateway_version,
            ext=            'jar',
            url=            f'{self.base_url}/{self.ext_package}/gateway',
            username=       username,
            password=       password,
            config_file=    'gateway.conf',
            deployment_time=Constants.GATEWAY_DEPLOY_TIME.value,
            certificates=   4)
        self.GATEWAY_PLUGIN = GatewayPluginService(
            abb=            'gateway-plugin',
            dir=            'cenm-gateway',
            artifact_name=  'cenm-gateway-plugin',
            version=        nms_visual_version,
            ext=            'jar',
            url=            f'{self.base_url}/{self.enm_package}',
            username=       username,
            password=       password)
        self.CLI = CliToolService(
            abb=            'cli',
            dir=            'cenm-gateway',
            artifact_name=  'cenm-tool',
            version=        nms_visual_version,
            ext=            'zip',
            url=            f'{self.base_url}/{self.enm_package}',
            username=       username,
            password=       password)
        self.IDMAN = IdentityManagerService(
            abb=            'idman',
            dir=            'cenm-idman',
            artifact_name=  'identitymanager',
            version=        cenm_version,
            ext=            'zip',
            url=            f'{self.base_url}/{self.enm_package}/services',
            username=       username,
            password=       password,
            config_file=    'identitymanager.conf',
            deployment_time=Constants.IDMAN_DEPLOY_TIME.value,
            certificates=   3)
        self.CRR_TOOL = CrrToolService(
            abb=            'crr-tool',
            dir=            'cenm-idman',
            artifact_name=  'crr-submission-tool',
            version=        cenm_version,
            ext=            'zip',
            url=            f'{self.base_url}/{self.enm_package}/tools',
            username=       username,
            password=       password)
        self.NMAP = NetworkMapService(
            abb=            'nmap',
            dir=            'cenm-nmap',
            artifact_name=  'networkmap',
            version=        cenm_version,
            ext=            'zip',
            url=            f'{self.base_url}/{self.enm_package}/services',
            username=       username,
            password=       password,
            config_file=    'networkmap.conf',
            deployment_time=Constants.NMAP_DEPLOY_TIME.value,
            certificates=   4)
        self.NOTARY = NotaryService(
            abb=            'notary',
            dir=            'cenm-notary',
            artifact_name=  'corda',
            version=        corda_version,
            ext=            'jar',
            url=            f'{self.base_url}/{self.corda_package}',
            username=       username,
            password=       password,
            config_file=    'notary.conf',
            deployment_time=Constants.NODE_DEPLOY_TIME.value)
        self.NODE = NodeService(
            abb=            'node',
            dir=            'cenm-node',
            artifact_name=  'corda',
            version=        corda_version,
            ext=            'jar',
            url=            f'{self.base_url}/{self.corda_package}',
            username=       username,
            password=       password,
            config_file=    'node.conf',
            deployment_time=Constants.NODE_DEPLOY_TIME.value)
        self.FINANCE_CONTRACTS_CORDAPP = FinanceContractsCordapp(
            abb=            'finance-contracts',
            dir=            'cenm-node',
            artifact_name=  'corda-finance-contracts',
            version=        corda_version,
            ext=            'jar',
            url=            f'{self.base_url}/{self.cordapp_package}',
            username=       username,
            password=       password)
        self.FINANCE_WORKFLOWS_CORDAPP = FinanceWorkflowsCordapp(
            abb=            'finance-workflows',
            dir=            'cenm-node',
            artifact_name=  'corda-finance-workflows',
            version=        corda_version,
            ext=            'jar',
            url=            f'{self.base_url}/{self.cordapp_package}',
            username=       username,
            password=       password)
        self.CORDA_SHELL = CordaShellService(
            abb=            'shell',
            dir=            'cenm-node',
            artifact_name=  'corda-shell',
            version=        corda_version,
            ext=            'jar',
            url=            f'{self.base_url}/{self.corda_package}',
            username=       username,
            password=       password)
        self.CORDA_HA_TOOLS = CordaToolsHaUtilitiesService(
            abb=            'ha-utuilities',
            dir=            'corda-tools',
            artifact_name=  'corda-tools-ha-utilities',
            version=        corda_version,
            ext=            'jar',
            url=            f'{self.base_url}/{self.corda_package}',
            username=       username,
            password=       password,
            config_file=    None,
            deployment_time=None)
        self.CORDA_BRIDGE = CordaFirewallDeploymentService(
            abb=            'bridge',
            dir=            'corda-bridge',
            artifact_name=  'corda-firewall',
            version=        corda_version,
            ext=            'jar',
            url=            f'{self.base_url}/{self.corda_package}',
            username=       username,
            password=       password,
            config_file=    'bridge.conf',
            deployment_time=Constants.FIREWALL_DEPLOY_TIME.value,
            certificates=   4)
        self.CORDA_FLOAT = CordaFirewallDeploymentService(
            abb=            'float',
            dir=            'corda-float',
            artifact_name=  'corda-firewall',
            version=        corda_version,
            ext=            'jar',
            url=            f'{self.base_url}/{self.corda_package}',
            username=       username,
            password=       password,
            config_file=    'float.conf',
            deployment_time=Constants.FIREWALL_DEPLOY_TIME.value,
            certificates=   2)
        self.ARTEMIS = ArtemisService(
            abb=            'artemis',
            dir=            'corda-artemis',
            artifact_name=  'apache-artemis-2.6.3-bin',
            version=        Constants.ARTEMIS_VERSION.value,
            ext=            'zip',
            url=            Constants.ARTEMIS_URL.value,
            username=       username,
            password=       password,
            config_file=    None,
            deployment_time=Constants.ARTEMIS_DEPLOY_TIME.value)
        self.PKI = PkiToolService(
            abb=            'pki',
            dir=            'cenm-pki',
            artifact_name=  'pki-tool',
            version=        cenm_version,
            ext=            'zip',
            url=            f'{self.base_url}/{self.enm_package}/tools',
            username=       username,
            password=       password,
            config_file=    'pki.conf',
            deployment_time=None)
        self.SIGNER = SignerService(
            abb=            'signer',
            dir=            'cenm-signer',
            artifact_name=  'signer',
            version=        cenm_version,
            ext=            'zip',
            url=            f'{self.base_url}/{self.enm_package}/services',
            username=       username,
            password=       password,
            config_file=    'signer.conf',
            deployment_time=Constants.SIGNER_DEPLOY_TIME.value,
            certificates=   6)
        self.SIGNER_CA_PLUGIN = SignerPluginCAService(
            abb=            'signer-ca-plugin',
            dir=            'cenm-signer',
            artifact_name=  'signing-service-example-plugin-ca',
            version=        cenm_version,
            ext=            'jar',
            url=            f'{self.base_url}/{self.enm_package}/signing-service-plugins',
            username=       username,
            password=       password)
        self.SIGNER_NONCA_PLUGIN = SignerPluginNonCAService(
            abb=            'signer-nonca-plugin',
            dir=            'cenm-signer',
            artifact_name=  'signing-service-example-plugin-nonca',
            version=        cenm_version,
            ext=            'jar',
            url=            f'{self.base_url}/{self.enm_package}/signing-service-plugins',
            username=       username,
            password=       password)
        self.ZONE = ZoneService(
            abb=            'zone',
            dir=            'cenm-zone',
            artifact_name=  'zone',
            version=        cenm_version,
            ext=            'zip',
            url=            f'{self.base_url}/{self.enm_package}/services',
            username=       username,
            password=       password,
            config_file=    '',
            deployment_time=Constants.ZONE_DEPLOY_TIME.value,
            certificates=   2)

        self.db_manager = DatabaseManager(self.get_database_services(), DownloadManager(username, password))
        self.config_manager = ConfigManager()
        self.deployment_manager = DeploymentManager(self.get_deployment_services())

    def _get_all_services(self, firewall: bool = False) -> List[BaseService]:
        """This is a list of all CENM services
        The order is not necessarily important

        If firewall=true then the Corda Firewall services are also added to the list
        
        """
        all_base_services = [
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
            self.FINANCE_CONTRACTS_CORDAPP,
            self.FINANCE_WORKFLOWS_CORDAPP,
            self.CORDA_SHELL,
            self.PKI,
            self.SIGNER,
            self.SIGNER_CA_PLUGIN,
            self.SIGNER_NONCA_PLUGIN,
            self.ZONE
        ]
        return [*all_base_services, *self.get_firewall_services()] if firewall else all_base_services

    def _get_node_manager(self, firewall: bool = False) -> NodeManager:
        if firewall:
            return NodeManager(
                self.NODE, 
                self.node_count, 
                self.ARTEMIS, 
                self.CORDA_HA_TOOLS, 
                self.get_firewall_services(deployment=True)
            )
        else:
            return NodeManager(self.NODE, self.node_count)

    def get_service(self, name: str) -> BaseService:
        for service in self._get_all_services(firewall=True):
            if service.artifact_name == name:
                return service
        raise ValueError(f'No service with name {name}')

    def get_deployment_services(self, pure_cenm: bool = False) -> List[DeploymentService]:
        """These services are returned in order they should be deployed

        For default deployments: do not change the order
        
        """
        if pure_cenm:
            return [
                self.IDMAN,
                self.SIGNER,
                self.NMAP,
                self.AUTH,
                self.GATEWAY,
                self.ZONE
            ]
        else:
            return [
                self.IDMAN,
                self.SIGNER,
                self.NOTARY,
                self.NMAP,
                self.AUTH,
                self.GATEWAY,
                self.ZONE
            ]
    
    def get_firewall_services(self, deployment: bool = False) -> List[CordaFirewallDeploymentService]:
        if deployment:
            return [
                self.CORDA_FLOAT,
                self.CORDA_BRIDGE
            ]
        else:
            return [
                self.ARTEMIS,
                self.CORDA_FLOAT,
                self.CORDA_BRIDGE,
                self.CORDA_HA_TOOLS
            ]

    def get_database_services(self) -> List[BaseService]:
        return [service for service in self._get_all_services() if service.abb in self.db_services]

    def _raise_exception_group(self, errors: Dict[Tuple[str, str], Any]):
        if any(errors.values()):
            exceptions = []
            for (service, dir), error in errors.items():
                if error:
                    exceptions.append(ServiceError(service, dir))
            print("There were service that were not found, check the logs")
            raise ExceptionGroup("Combined service exceptions", exceptions)

    def download_all(self, firewall: bool):
        download_errors = {}
        for service in self._get_all_services(firewall):
            download_errors[(f'{service.artifact_name}-{service.version}', service.dir)] = service.download()

        download_errors_db = self.db_manager.download()
        # self.printer.print_end_of_script_report(download_errors, download_errors_db)

        # self._raise_exception_group(download_errors)
        # self._raise_exception_group(download_errors_db)
        self.check_all(firewall)

    def check_all(self, firewall: bool):
        check_errors = {}
        print("Validating services")
        for service in self._get_all_services(firewall):
            # self.logger.info(f'validating {service.artifact_name} config')
            if (not service._check_presence()):
                check_errors[(f'{service.artifact_name}-{service.version}', service.dir)] = service.dir
                print(u'[\u274c] ' + f'{service.artifact_name}-{service.version}')
            else:
                print(u'[\u2705] ' + f'{service.artifact_name}-{service.version}')
        self._raise_exception_group(check_errors)
        print("Validating complete")
        # else:
            # self.printer.print_end_of_check_report(check_errors)

    def download_specific(self, services: List[str]):
        print("Downloading individual artifacts does not work with any other arguments, script will exit after downloading.")
        download_errors = {}
        for service in services:
            try:
                service = self.get_service(service)
                download_errors[(f'{service.artifact_name}-{service.version}', service.dir)] = service.download()
            except ValueError as e:
                print(e)
                download_errors[service] = str(e)
        download_errors_db = self.db_manager.download()
        # self.printer.print_end_of_script_report(download_errors, download_errors_db)

        # self._raise_exception_group(download_errors)
        # self._raise_exception_group(download_errors_db)
        self.check_all()

    def deploy_all(self, health_check_frequency: int):
        self.check_all(firewall=False)
        self.config_manager.validate(self.get_deployment_services())
        self.PKI.validate_certificates(self.get_deployment_services(pure_cenm=True))
        self.deployment_manager.deploy_services(health_check_frequency)

    def deploy_nodes(self, health_check_frequency: int, firewall: bool):
        node_manager = self._get_node_manager(firewall)
        self.config_manager.validate(node_manager.new_nodes)
        self.CORDA_HA_TOOLS.validate_certificates([self.CORDA_BRIDGE, self.CORDA_FLOAT])
        node_manager.deploy_nodes(health_check_frequency)

    def generate_certificates(self, firewall):
        self.check_all(firewall)
        self.config_manager.validate([*self.get_deployment_services(), self.NODE, self.PKI])
        if firewall:
            self.PKI.deploy()
            self.CORDA_HA_TOOLS.deploy()
        else:
            self.PKI.deploy()

    def clean_all(self,
        clean_deep: bool,
        clean_artifacts: bool,
        clean_certs: bool,
        clean_runtime: bool,
        clean_nodes: bool,
        clean_firewall: bool
    ):
        if clean_nodes:
            node_manager = self._get_node_manager(clean_firewall)
            node_manager.clean_deployment_nodes(
                clean_deep,
                clean_artifacts,
                clean_certs,
                clean_runtime
            )
        else:
            self.sysi.remove(".logs/*", silent=True)
            services = [*self.get_deployment_services(), *self.get_firewall_services(), self.NODE, self.PKI] if clean_firewall else [*self.get_deployment_services(), self.NODE, self.PKI]
            for service in services:
                if clean_deep:
                    service.clean_all()
                    continue
                if clean_artifacts:
                    service.clean_artifacts()
                if clean_certs:
                    service.clean_certificates()
                if clean_runtime:
                    service.clean_runtime()

    def clean_specific_artifacts(self, services: List[str]):
        print("Cleaning individual artifacts does not work with any other arguments, script will exit after downloading.")
        for service in services:
            try:
                service = self.get_service(service)
                service.clean_runtime()
                service.clean_artifacts()
            except ValueError as e:
                print(e)

        