from utils import SystemInteract, Logger, Constants, java_string
from typing import List
from services.base_services import DeploymentService
import glob
import re

class FirewallCertificateError(Exception):
    def __init__(self, service, message):
        super().__init__("""
Certificate exception for service: {}

    The following error was found while validating certificates: {}
        """.format(service, message))

class FirewallCertificateManager:
    """Manages the firewall certificates for the Corda node 
    deployments using the Corda firewall.

    """
    def __init__(self):
        self.logger = Logger().get_logger(__name__)
        self.sysi = SystemInteract()
        self.java_version = 17

    def _bridge(self):
        # artemis
        self.sysi.copy('corda-tools/artemis/artemis.jks', 'corda-bridge/artemis')
        self.sysi.copy('corda-tools/artemis/artemisbridge.jks', 'corda-bridge/artemis')
        self.sysi.copy('corda-tools/artemis/artemis-truststore.jks', 'corda-bridge/artemis')
        # tunnel
        self.sysi.copy('corda-tools/tunnel/bridge.jks', 'corda-bridge/tunnel')
        self.sysi.copy('corda-tools/tunnel/tunnel-truststore.jks', 'corda-bridge/tunnel')

    def _float(self):
        # tunnel
        self.sysi.copy('corda-tools/tunnel/float.jks', 'corda-float/tunnel')
        self.sysi.copy('corda-tools/tunnel/tunnel-truststore.jks', 'corda-float/tunnel')

    def _node(self):
        existing_nodes = glob.glob("cenm-node*")
        for node in existing_nodes:
            # artemis
            self.sysi.copy('corda-tools/artemis/artemis.jks', f'{node}/artemis')
            self.sysi.copy('corda-tools/artemis/artemisnode.jks', f'{node}/artemis')
            self.sysi.copy('corda-tools/artemis/artemis-truststore.jks', f'{node}/artemis')

    def _distribute_certs(self):
        print('Distributing certificates')
        self._bridge()
        self._float()
        self._node()
        
    def _generate_internal_tunnel_ssl_keystore(self):
        self.logger.info(f'Generating internal tunnel ssl keystore')
        return self.sysi.run_get_exit_code(f'cd corda-tools && {java_string(self.java_version)} && java -jar corda-tools-ha-utilities.jar generate-internal-tunnel-ssl-keystores -p tunnelStorePass -e tunnelPrivateKeyPassword -t tunnelTrustpass')
    
    def _generate_internal_artemis_ssl_keystore(self):
        self.logger.info(f'Generating internal artemis ssl keystore')
        return self.sysi.run_get_exit_code(f'cd corda-tools && {java_string(self.java_version)} && java -jar corda-tools-ha-utilities.jar generate-internal-artemis-ssl-keystores -p artemisStorePass -t artemisTrustpass')
        
    def generate(self) -> int:
        certs = {}
        exits = [0]
        for path in ['artemis', 'tunnel']:
            if self.sysi.path_exists(f'corda-tools/{path}'):
                print(f'{path} already exists. Skipping generation.')
                certs[path] = True
            else:
                certs[path] = False
        
        if not all(certs.values()):
            print('Generating firewall certificates')
            exits.append(self._generate_internal_tunnel_ssl_keystore())
            exits.append(self._generate_internal_artemis_ssl_keystore())
        self._distribute_certs()
        return max(exits)

    def validate(self, services: List[DeploymentService]):
        pass
        validation_errors = {}
        for service in services:
            self.logger.info(f'validating {service.artifact_name} certificates')
            validation_errors[f'{service.artifact_name}-{service.abb}'] = service.validate_certs()

        if any(validation_errors.values()):
            exceptions = []
            for service, message in validation_errors.items():
                if message:
                    self.logger.error(f'{service} certificate validation failed')
                    exceptions.append(FirewallCertificateError(service, message))
            print("There were certificate validation errors, check the logs")
            raise ExceptionGroup("Combined certificate exceptions", exceptions)