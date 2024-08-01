import logging
from utils import SystemInteract, java_string, get_cenm_java_version
from typing import List
from services.base_services import DeploymentService

class CertificateError(Exception):
    def __init__(self, service, message):
        super().__init__("""
Certificate exception for service: {}

    The following error was found while validating certificates: {}
        """.format(service, message))

class CertificateManager:
    """Manages the certificates for the CENM deployment.

    """
    def __init__(self, cenm_version: str):
        self.logger = logging.getLogger(__name__)
        self.sysi = SystemInteract()
        self.java_version = get_cenm_java_version(cenm_version)

    def _copy(self, source, destination):
        self.sysi.run(f'cp cenm-pki/{source} {destination}')

    def _auth(self):
        # trust stores
        self._copy('trust-stores/corda-ssl-trust-store.jks', 'cenm-auth/certificates')
        # key stores
        self._copy('key-stores/corda-ssl-auth-keys.jks', 'cenm-auth/certificates')
    
    def _gateway(self):
        # trust stores
        self._copy('trust-stores/corda-ssl-trust-store.jks', 'cenm-gateway/private/certificates')
        self._copy('trust-stores/corda-ssl-trust-store.jks', 'cenm-gateway/public/certificates')
        # key stores
        self._copy('key-stores/corda-ssl-identity-manager-keys.jks', 'cenm-gateway/private/certificates')
        self._copy('key-stores/corda-ssl-identity-manager-keys.jks', 'cenm-gateway/public/certificates')

    def _idman(self):
        # trust stores
        self._copy('trust-stores/corda-ssl-trust-store.jks', 'cenm-idman/certificates')
        # key stores
        self._copy('key-stores/corda-identity-manager-keys.jks', 'cenm-idman/certificates')
        self._copy('key-stores/corda-ssl-identity-manager-keys.jks', 'cenm-idman/certificates')
        # crl files
        self._copy('crl-files/*', 'cenm-idman/crl-files')

    def _nmap(self):
        # trust stores
        self._copy('trust-stores/corda-ssl-trust-store.jks', 'cenm-nmap/certificates')
        self._copy('trust-stores/network-root-truststore.jks', 'cenm-nmap/certificates')
        # key stores
        self._copy('key-stores/corda-network-map-keys.jks', 'cenm-nmap/certificates')
        self._copy('key-stores/corda-ssl-network-map-keys.jks', 'cenm-nmap/certificates')

    def _notary(self):
        # trust stores
        self._copy('trust-stores/network-root-truststore.jks', 'cenm-notary/certificates')

    def _node(self):
        # trust stores
        self._copy('trust-stores/network-root-truststore.jks', 'cenm-node/certificates')

    def _signer(self):
        # trust stores
        self._copy('trust-stores/corda-ssl-trust-store.jks', 'cenm-signer/certificates')
        # This is not needed for local keys however might be useful if using HSM
        self._copy('trust-stores/network-root-truststore.jks', 'cenm-signer/certificates')
        # key stores
        self._copy('key-stores/corda-network-map-keys.jks', 'cenm-signer/certificates')
        self._copy('key-stores/corda-identity-manager-keys.jks', 'cenm-signer/certificates')
        self._copy('key-stores/corda-ssl-network-map-keys.jks', 'cenm-signer/certificates')
        self._copy('key-stores/corda-ssl-identity-manager-keys.jks', 'cenm-signer/certificates')
        self._copy('key-stores/corda-ssl-signer-keys.jks', 'cenm-signer/certificates')

    def _zone(self):
        # trust stores
        self._copy('trust-stores/corda-ssl-trust-store.jks', 'cenm-zone/certificates')
        # key stores
        self._copy('key-stores/corda-ssl-identity-manager-keys.jks', 'cenm-zone/certificates')

    def _distribute_certs(self):
        self.logger.info('Distributing certificates')
        self._auth()
        self._gateway()
        self._idman()
        self._nmap()
        self._notary()
        self._node()
        self._signer()
        self._zone()

    def generate(self) -> int:
        certs = {}
        exits = [0]
        for path in ['crl-files', 'key-stores', 'trust-stores']:
            if self.sysi.path_exists(f'cenm-pki/{path}'):
                self.logger.warning(f'{path} already exists. Skipping generation.')
                certs[path] = True
            else:
                certs[path] = False
        if self.sysi.path_exists(f'cenm-auth/certificates/jwt-store.jks'):
            self.logger.warning('Auth jwt-store already exists. Skipping generation.')
        else:
            self.logger.info('Generating auth jwt-store')
            exits.append(self.sysi.run_get_exit_code(f'(cd cenm-auth && keytool -genkeypair -alias oauth-test-jwt -keyalg RSA -keypass password -keystore certificates/jwt-store.jks -storepass password -dname "CN=abc1, OU=abc2, O=abc3, L=abc4, ST=abc5, C=abc6" > /dev/null 2>&1)'))

        if not all(certs.values()):
            self.logger.info('Generating certificates')
            exits.append(self.sysi.run_get_exit_code(f'(cd cenm-pki && {java_string(self.java_version)} && java -jar pkitool.jar -f pki.conf)'))
        self._distribute_certs()
        return max(exits)

    def validate(self, services: List[DeploymentService]):
        validation_errors = {}
        for service in services:
            self.logger.info(f'validating {service.artifact_name} certificates')
            validation_errors[service.artifact_name] = service.validate_certs()

        if any(validation_errors.values()):
            exceptions = []
            for service, message in validation_errors.items():
                if message:
                    self.logger.error(f'{service} certificate validation failed')
                    exceptions.append(CertificateError(service, message))
            self.logger.error("There were certificate validation errors, check the logs")
            raise ExceptionGroup("Combined certificate exceptions", exceptions)