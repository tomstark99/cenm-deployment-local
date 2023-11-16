from pyhocon import ConfigFactory
from services.base_services import *
from managers.certificate_manager import CertificateManager
from managers.firewall_certificate_manager import FirewallCertificateManager
from utils import Constants
from typing import List
from time import sleep
import glob
import os
import re

class AuthService(DeploymentService):

    def clean_runtime(self):
        self.sysi.run('(cd cenm-auth/setup-auth/roles && for file in *.json; do perl -0777 -i -pe "s/objectName\\": \\"global\\".*'
            + "\n".encode("unicode_escape").decode("utf-8")
            + '.*objectName\\": \\"\K.*(?=\\")/<SUBZONE_ID>/g" $file; done)')
        super().clean_runtime()

    def deploy(self):
        self.logger.info(f'Thread started to deploy {self.artifact_name}')
        artifact_name = f'{self.artifact_name}-{self.version}'
        while True:
            try:
                self.logger.debug(f'[Running] (cd {self.dir} && java -jar {artifact_name}.jar -f {self.config_file} --initial-user-name admin --initial-user-password p4ssWord --keep-running --verbose) to start {self.artifact_name} service')
                exit_code = self.sysi.run_get_exit_code(f'(cd {self.dir} && java -jar {artifact_name}.jar -f {self.config_file} --initial-user-name admin --initial-user-password p4ssWord --keep-running --verbose)')
                if exit_code != 0:
                    raise RuntimeError(f'{self.artifact_name} service stopped')
            except:
                self.logger.warning(f'{self.artifact_name} service stopped. Restarting...')

class AuthClientService(BaseService):
    pass

class AuthPluginService(BaseService):

    def _handle_plugin(self):
        if not self.sysi.path_exists(f'{self.dir}/plugins'):
            self.sysi.run(f'mkdir {self.dir}/plugins')
        self.sysi.run(f'mv {self._zip_name()} {self.dir}/plugins/accounts-baseline-cenm.jar')

    def download(self) -> bool:
        if self._check_presence():
            return
        # If artifact not present then download it
        print(f'Downloading {self._zip_name()}')
        self.error = self.dlm.download(self.url)
        self._handle_plugin()
        return self.error

class GatewayService(DeploymentService):

    def _handle_gateway(self):
        self.sysi.run(f'cp {self._zip_name()} {self.dir}/public')
        self.sysi.run(f'mv {self._zip_name()} {self.dir}/private')

    def download(self) -> bool:
        self._clone_repo()
        if self._check_presence():
            return
        # If artifact not present then download it
        print(f'Downloading {self._zip_name()}')
        self.error = self.dlm.download(self.url)
        self._handle_gateway()
        return self.error

    def _get_cert_count(self) -> bool:
        cert_count_1 = self.sysi.run_get_stdout(f"ls {self.dir}/private/certificates | xargs | wc -w | sed -e 's/^ *//g'")
        cert_count_2 = self.sysi.run_get_stdout(f"ls {self.dir}/public/certificates | xargs | wc -w | sed -e 's/^ *//g'")
        return int(cert_count_1) + int(cert_count_2)

    def deploy(self):
        self.logger.info(f'Thread started to deploy {self.artifact_name}')
        artifact_name = f'{self.artifact_name}-{self.version}'
        while True:
            try:
                self.logger.debug(f'[Running] (cd {self.dir}/private && java -jar {artifact_name}.jar -f {self.config_file}) to start {self.artifact_name} service')
                exit_code = self.sysi.run_get_exit_code(f'(cd {self.dir}/private && java -jar {artifact_name}.jar -f {self.config_file})')
                if exit_code != 0:
                    raise RuntimeError(f'{self.artifact_name} service stopped')
            except:
                self.logger.warning(f'{self.artifact_name} service stopped. Restarting...')

    def validate_config(self) -> str:
        try:
            ConfigFactory.parse_file(f'{self.dir}/private/{self.config_file}')
            ConfigFactory.parse_file(f'{self.dir}/public/{self.config_file}')
            return ""
        except Exception as e:
            return str(e)

    def validate_certs(self) -> str:
        if self._get_cert_count() < self.certificates:
            return f'Certificate mismatch ({self._get_cert_count()} found, {self.certificates} expected)'
        else:
            return ""

class GatewayPluginService(BaseService):

    def _handle_plugin(self):
        if not self.sysi.path_exists(f'{self.dir}/public/plugins'):
            self.sysi.run(f'mkdir -p {self.dir}/public/plugins')
        if not self.sysi.path_exists(f'{self.dir}/private/plugins'):
            self.sysi.run(f'mkdir -p {self.dir}/private/plugins')
        self.sysi.run(f'cp {self._zip_name()} {self.dir}/private/plugins/cenm-gateway-plugin.jar')
        self.sysi.run(f'mv {self._zip_name()} {self.dir}/public/plugins/cenm-gateway-plugin.jar')

    def download(self) -> bool:
        self._clone_repo()
        if self._check_presence():
            return
        # If artifact not present then download it
        print(f'Downloading {self._zip_name()}')
        self.error = self.dlm.download(self.url)
        self._handle_plugin()
        return self.error

class CliToolService(BaseService):

    def _handle_cli_tool(self):
        if not self.sysi.path_exists(f'{self.dir}/cenm-tool'):
            self.sysi.run(f'mkdir -p {self.dir}/cenm-tool')
        self.sysi.run(f'mv {self._zip_name()} {self.dir}/cenm-tool')
        self.sysi.run(f'(cd {self.dir}/cenm-tool && unzip -q {self._zip_name()} && rm {self._zip_name()} && chmod +x cenm)')

    def download(self):
        self._clone_repo()
        if self._check_presence():
            return
        # If artifact not present then download it
        print(f'Downloading {self._zip_name()}')
        self.error = self.dlm.download(self.url)
        self._handle_cli_tool()
        return self.error

class IdentityManagerService(DeploymentService):
    
    def clean_artifacts(self):
        for root, dirs, files in os.walk(self.dir):
            for dir in dirs:
                if os.path.join(root, dir).split("/")[-2] == "tools":
                    self.sysi.remove(os.path.join(root, dir))
        super().clean_artifacts()

class CrrToolService(BaseService):

    def _check_presence(self) -> bool:
        for _, _, files in os.walk(f'{self.dir}/tools/{self.artifact_name}'):
            if 'crrsubmissiontool.jar' in files:
                # Temporarily muting this message
                # print(f'crrsubmissiontool.jar already exists. Skipping.')
                return True
        return False

    def _handle_crr_tool(self):
        if not self.sysi.path_exists(f'{self.dir}/tools'):
            self.sysi.run(f'mkdir -p {self.dir}/tools')
        self.sysi.run(f'mkdir -p {self.dir}/tools/{self.artifact_name}')
        self.sysi.run(f'mv {self._zip_name()} {self.dir}/tools/{self.artifact_name}')
        self.sysi.run(f'(cd {self.dir}/tools/{self.artifact_name} && unzip -q {self._zip_name()} && rm {self._zip_name()})')

    def download(self):
        self._clone_repo()
        if self._check_presence():
            return
        # If artifact not present then download it
        print(f'Downloading {self._zip_name()}')
        self.error = self.dlm.download(self.url)
        self._handle_crr_tool()
        return self.error

class NetworkMapService(DeploymentService):

    def _node_info(self) -> bool:
        return glob.glob(f'cenm-nmap/nodeInfo-*') and glob.glob(f'cenm-notary/nodeInfo*')

    def _copy_notary_node_info(self):
        self.logger.info(f'Copying notary node info to nmap')
        while not glob.glob('cenm-notary/nodeInfo-*'):
            self.logger.info(f'Waiting for nodeInfo file to be created')
            sleep(5)
        self.sysi.run(f'cp cenm-notary/nodeInfo-* {self.dir}')
        self.logger.debug(f'Updating networkparameters.conf with node info')
        self.sysi.run(f'(cd cenm-nmap && perl -i -pe "s/^.*notaryNodeInfoFile: \\"\K.*(?=\\")/$(ls nodeInfo-*)/" networkparameters.conf)')
        new_params = self.sysi.run_get_stdout(f'(cd cenm-nmap && cat networkparameters.conf)')
        self.logger.info(f'new networkparams:\n{new_params}')
        
    def _set_network_params(self):
        self.logger.info(f'Setting network parameters')
        self.sysi.run(f'cd {self.dir} && java -jar networkmap.jar -f networkmap.conf --set-network-parameters networkparameters.conf --network-truststore ./certificates/network-root-truststore.jks --truststore-password trustpass --root-alias cordarootca')

    def clean_runtime(self):
        for root, dirs, files in os.walk(self.dir):
            for file in files:
                if file.startswith("nodeInfo"):
                    self.sysi.remove(os.path.join(root, file))
                if file.startswith("networkparameters"):
                    self.sysi.run(f'perl -i -pe "s/^.*notaryNodeInfoFile: \\"\K.*(?=\\")/INSERT_NODE_INFO_FILE_NAME_HERE/" {os.path.join(root, file)}')
        super().clean_runtime()

    def deploy(self):
        if not self._node_info():
            self._copy_notary_node_info()
            self._set_network_params()
        super().deploy()

class NotaryService(NodeDeploymentService):
    
    def _move(self):
        self.sysi.run(f'mv {self._zip_name()} {self.dir}/{self._zip_name()}')
        if self.sysi.path_exists('cenm-node'):
            self.sysi.run(f'mv {self._zip_name()} cenm-node/{self._zip_name()} > /dev/null 2>&1')

class NodeService(NodeDeploymentService):

    def _move(self):
        self.sysi.run(f'mv {self._zip_name()} {self.dir}/{self._zip_name()}')
        if self.sysi.path_exists('cenm-notary'):
            self.sysi.run(f'mv {self._zip_name()} cenm-notary/{self._zip_name()} > /dev/null 2>&1')

class CordaShellService(BaseService):

    def _handle_corda_shell(self):
        # if not self.sysi.path_exists(f'{self.dir}/drivers'):
        #     self.sysi.run(f'mkdir -p {self.dir}/drivers')
        self.sysi.run(f'mv {self._zip_name()} {self.dir}/drivers/{self._zip_name()} > /dev/null 2>&1')

    def download(self):
        self._clone_repo()
        if self._check_presence():
            return
        # If artifact not present then download it
        print(f'Downloading {self._zip_name()}')
        self.error = self.dlm.download(self.url)
        self._handle_corda_shell()
        return self.error

class CordaToolsHaUtilitiesService(DeploymentService):

    def _create_dir(self):
        if not self.sysi.path_exists(self.dir):
            print(f'Creating {self.dir}')
            self.sysi.run(f'mkdir {self.dir}')

    def _move(self):
        self.sysi.run(f'mv {self._zip_name()} {self.dir}/{self._zip_name(no_version=True)}')

    def download(self) -> bool:
        self._create_dir()
        if self._check_presence():
            return
        # If artifact not present then download it
        print(f'Downloading {self._zip_name()}')
        self.error = self.dlm.download(self.url)
        self._move()
        return self.error

    def deploy(self):
        cert_manager = FirewallCertificateManager()
        exit_code = -1
        try:
            while exit_code != 0:
                exit_code = cert_manager.generate()
        except KeyboardInterrupt:
            print('Certificate generation cancelled')
            exit(1)

    def validate_certificates(self, services: List[DeploymentService]):
        cert_manager = FirewallCertificateManager()
        cert_manager.validate(services)

    def clean_runtime(self):
        for root, dirs, files in os.walk(self.dir):
            for file in files:
                if file in self.runtime_files['ha-tools']:
                    self.sysi.remove(os.path.join(root, file))
    
    def clean_certificates(self):
        for root, dirs, files in os.walk(self.dir):
            for dir in dirs:
                if dir in ["artemis", "tunnel", "nodesCertificates"]:
                    self.sysi.remove(os.path.join(root, dir))
    
class FinanceContractsCordapp(CordappService):
    pass

class FinanceWorkflowsCordapp(CordappService):
    pass

class CordaBridgeService(CordaFirewallDeploymentService):
    pass

class CordaFloatService(CordaFirewallDeploymentService):
    pass

class ArtemisService(DeploymentService):

    # Overridden method not called in constructor of BaseService so have to manually call it below to update self.url
    def __build_url(self, url: str):
        return f'{url}/{self.version}/{self.artifact_name}.{self.ext}'

    def _zip_name(self, no_version: bool = False):
        return f'{self.artifact_name}.{self.ext}'

    def _create_dir(self):
        if not self.sysi.path_exists(self.dir):
            print(f'Creating {self.dir}')
            self.sysi.run(f'mkdir {self.dir}')

    def _check_presence(self):
        return self.sysi.path_exists(f'{self.dir}/apache-artemis-{self.version}')
    
    def _is_configured(self):
        return self.sysi.path_exists(f'{self.dir}/artemis-master')

    def _configure_artemis(self):
        self.sysi.run(f'cd corda-tools && java -jar corda-tools-ha-utilities.jar configure-artemis --install --distribution ../corda-artemis/apache-artemis-{self.version} --path ../corda-artemis/artemis-master --user "CN=artemis, O=Corda, L=London, C=GB" --ha MASTER --acceptor-address localhost:11005 --keystore ./artemis/artemis.jks --keystore-password artemisStorePass --truststore ./artemis/artemis-truststore.jks --truststore-password artemisTrustpass --connectors localhost:11005')

    def _copy_keystores(self):
        self.sysi.run('mkdir -p corda-artemis/artemis-master/etc/artemis', silent=True)
        self.sysi.copy('corda-tools/artemis/artemis.jks', 'corda-artemis/artemis-master/etc/artemis')
        self.sysi.copy('corda-tools/artemis/artemis-truststore.jks', 'corda-artemis/artemis-master/etc/artemis')

    def _wait_for_float(self):
        while int(self.sysi.run_get_stdout('ps | grep -E ".*(cd corda-float.+\&\& java -jar).+(\.jar).+(\.conf).*" | wc -l | sed -e "s/^ *//g"')) == 0:
            sleep(5)
            self.logger.info('Waiting for Corda Firewall (float) to start')
        self.logger.info('Corda Firewall (float) started, starting Artemis')

    def download(self) -> bool:
        self.url = self.__build_url(Constants.ARTEMIS_URL.value)
        self._create_dir()
        if self._check_presence():
            return
        # If artifact not present then download it
        print(f'Downloading {self._zip_name()}')
        self.error = self.dlm.download(self.url)
        self._move()
        return self.error

    def deploy(self):
        if not self._is_configured():
            self._configure_artemis()
            self._copy_keystores()
        self._wait_for_float()
        while True:
            try:
                self.logger.debug(f'[Running] (cd {self.dir} && ./artemis-master/bin/artemis run) to start {self.artifact_name} service')
                exit_code = self.sysi.run_get_exit_code(f'(cd {self.dir} && ./artemis-master/bin/artemis run)')
                if exit_code != 0:
                    raise RuntimeError(f'{self.artifact_name} service stopped')
            except:
                self.logger.warning(f'{self.artifact_name} service stopped. Restarting...')

    def validate_config(self) -> str:
        return ""

    def validate_certs(self) -> str:
        return ""

    def clean_runtime(self):
        for root, dirs, files in os.walk(self.dir):
            for dir in dirs:
                if dir in self.runtime_files['artemis']:
                    self.sysi.remove(os.path.join(root, dir))

    def clean_artifacts(self):
        for root, dirs, files in os.walk(self.dir):
            for dir in dirs:
                if dir in [f"apache-artemis-{Constants.ARTEMIS_VERSION.value}"]:
                    self.sysi.remove(os.path.join(root, dir))

    def clean_certificates(self):
        pass

class PkiToolService(DeploymentService):

    def _check_presence(self) -> bool:
        for _, _, files in os.walk(self.dir):
            if 'pkitool.jar' in files:
                # Temporarily muting this message
                # print(f'pkitool.jar already exists. Skipping.')
                return True
        return False

    def download(self) -> bool:
        self._clone_repo()
        if self._check_presence():
            return
        # If artifact not present then download it
        print(f'Downloading {self._zip_name()}')
        self.error = self.dlm.download(self.url)
        self._move()
        return self.error

    def deploy(self):
        cert_manager = CertificateManager()
        exit_code = -1
        try:
            while exit_code != 0:
                exit_code = cert_manager.generate()
        except KeyboardInterrupt:
            print('Certificate generation cancelled')
            exit(1)

    def validate_certificates(self, services: List[DeploymentService]):
        cert_manager = CertificateManager()
        cert_manager.validate(services)

    def validate_config(self) -> str:
        try:
            ConfigFactory.parse_file(f'{self.dir}/{self.config_file}')
            return ""
        except Exception as e:
            """this HOCON parser doesn't like default pki config e.g.
                 "::CORDA_SSL_NETWORK_MAP"
            
            This workaround finds the line number of the HOCON error and checks if the config option
            on that line matches the above pattern, if so then it bypasses the parsing error.

            """
            line_number = (int(re.search(r'line\:\d+',str(e)).group().split(':')[-1]) - 1)
            with open(f'{self.dir}/{self.config_file}', 'r') as f:
                pki_config_lines = f.readlines()
            if re.match(r'.*(\,\n|\n)?.*\"\:\:\w+\"(\,\n|\n)?.*', ''.join(pki_config_lines[line_number-1:line_number+1])):
                return ""
            else:
                return str(e)

    def clean_certificates(self):
        for root, dirs, files in os.walk(self.dir):
            for dir in dirs:
                if dir in ["crl-files", "trust-stores", "key-stores"]:
                    self.sysi.remove(os.path.join(root, dir))

class SignerService(DeploymentService):
    pass

class SignerPluginNonCAService(SignerPluginService):
    pass

class SignerPluginCAService(SignerPluginService):
    pass

class ZoneService(DeploymentService):

    def deploy(self):
        while True:
            try:
                self.logger.debug(f'Running: (cd {self.dir} && java -jar {self.artifact_name}.jar --driver-class-name=org.h2.Driver --jdbc-driver= --user=zoneuser --password=password --url="jdbc:h2:file:./h2/zone-persistence;DB_CLOSE_ON_EXIT=FALSE;LOCK_TIMEOUT=10000;WRITE_DELAY=0;AUTO_SERVER_PORT=0" --run-migration=true --enm-listener-port=5061 --admin-listener-port=5063 --auth-host=127.0.0.1 --auth-port=8081 --auth-trust-store-location certificates/corda-ssl-trust-store.jks --auth-trust-store-password trustpass --auth-issuer "http://test" --auth-leeway 5 --tls=true --tls-keystore=certificates/corda-ssl-identity-manager-keys.jks --tls-keystore-password=password --tls-truststore=certificates/corda-ssl-trust-store.jks --tls-truststore-password=trustpass) to start zone service')
                exit_code = self.sysi.run_get_exit_code(f'(cd {self.dir} && java -jar {self.artifact_name}.jar --driver-class-name=org.h2.Driver --jdbc-driver= --user=zoneuser --password=password --url="jdbc:h2:file:./h2/zone-persistence;DB_CLOSE_ON_EXIT=FALSE;LOCK_TIMEOUT=10000;WRITE_DELAY=0;AUTO_SERVER_PORT=0" --run-migration=true --enm-listener-port=5061 --admin-listener-port=5063 --auth-host=127.0.0.1 --auth-port=8081 --auth-trust-store-location certificates/corda-ssl-trust-store.jks --auth-trust-store-password trustpass --auth-issuer "http://test" --auth-leeway 5 --tls=true --tls-keystore=certificates/corda-ssl-identity-manager-keys.jks --tls-keystore-password=password --tls-truststore=certificates/corda-ssl-trust-store.jks --tls-truststore-password=trustpass)')
                if exit_code != 0:
                    raise RuntimeError(f'{self.artifact_name} service stopped')
            except:
                self.logger.warning(f'{self.artifact_name} service stopped. Restarting...')
    
    def validate_config(self) -> str:
        return ""