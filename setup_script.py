import os
from time import sleep
from typing import List, Any, Tuple, Dict
import argparse
# import threading
import multiprocessing
import logging
import glob

parser = argparse.ArgumentParser(description='Download CENM artifacts from Artifactory')
parser.add_argument(
    '--setup-dir-structure', 
    default=False, 
    action='store_true', 
    help='Create directory structure for CENM deployment and download all current artifacts'
)
parser.add_argument(
    '--generate-certs', 
    default=False, 
    action='store_true', 
    help='Generate certificates and distribute them to services'
)
parser.add_argument(
    '--clean', 
    default=False, 
    action='store_true', 
    help='Remove all generated run-time files'
)
parser.add_argument(
    '--clean-certs', 
    default=False, 
    action='store_true', 
    help='Remove all generated certificates'
)
parser.add_argument(
    '--clean-artifacts', 
    default=False, 
    action='store_true', 
    help='Remove all downloaded artifacts and generated certificates'
)
parser.add_argument(
    '--deep-clean', 
    default=False, 
    action='store_true', 
    help='Remove all generated service folders'
)
parser.add_argument(
    '--run-default-deployment', 
    default=False, 
    action='store_true', 
    help='Runs a default deployment, following the steps from README'
)
parser.add_argument(
    '--version', 
    default=False, 
    action='store_true', 
    help='Show current cenm version'
)

def is_wget_installed() -> bool:
    return os.system('wget --version > /dev/null 2>&1') == 0

def get_logger():
    logging.basicConfig(filename=".logs/default-deployment.log",
                    filemode='a',
                    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                    datefmt='%H:%M:%S',
                    level=logging.DEBUG)

    logger = logging.getLogger(__name__)
    return logger

# Check if .env file exists
if not os.path.exists(".env"):
    raise FileNotFoundError("No .env file found. Please create one and try again.")

with open(".env", 'r') as f:
    # dictionary comprehension to read the build.args file, split each value on '=' and create a map of key:value
    args = {key:value for (key,value) in [x.strip().split("=") for x in f.readlines()]}

try:
    # Get variables from .env file
    username = args["ARTIFACTORY_USERNAME"]
    password = args["ARTIFACTORY_API_KEY"]
    auth_version = args["AUTH_VERSION"]
    gateway_version = args["GATEWAY_VERSION"]
    cenm_version = args["CENM_VERSION"]
    nms_visual_version = args["NMS_VISUAL_VERSION"]
    corda_version = args["NOTARY_VERSION"]
except KeyError as e:
    raise KeyError(f"Missing variable in .env file: {e}")

# Useful variables
wget = is_wget_installed()
base_url = 'https://software.r3.com/artifactory'
ext_package = 'extensions-lib-release-local/com/r3/appeng'
enm_package = 'r3-enterprise-network-manager/com/r3/enm'
corda_package = 'corda-releases/net/corda'
repos = ['auth', 'gateway', 'idman', 'nmap', 'notary', 'node', 'pki', 'signer', 'zone']

class SystemInteract:

    def run(self, cmd):
        os.system(cmd)

    def rm(self, path):
        os.system(f'rm -rf {path}')

    def run_get_exit_code(self, cmd):
        return os.system(cmd)

    def run_get_stdout(self, cmd):
        os.system(f'{cmd} > .tmp')
        with open('.tmp', 'r') as f:
            out = f.read()
        os.system('rm .tmp')
        return out

class DownloadManager:
    def __init__(self, username, password, wget):
        self.username = username
        self.password = password
        self.wget = wget

    def download(self, url) -> bool:
        if self.wget:
            cmd = os.system(f'wget -q --show-progress --user {self.username} --password {self.password} {url}')
            if cmd != 0:
                cmd2 = os.system(f'wget --progress=bar:force:noscroll --user {self.username} --password {self.password} {url}')
                if cmd2 != 0:
                    return True
        else:
            cmd = os.system(f'curl --progress-bar -u {self.username}:{self.password} -O {url}')
            if cmd != 0:
                return True
        return False

class CenmTool:
    def __init__(self, version):
        self.host = 'http://127.0.0.1:8089'
        self.path = 'cenm-gateway/cenm-tool'
        self.jar = f'cenm-tool-{version}.jar'

    def _run(self, cmd):
        return sysi.run_get_stdout(f'(cd {self.path} && java -jar {self.jar} {cmd})')

    def _login(self, username, password):
        self._run(f'context login -s {self.host} -u {username} -p {password}')
    
    def _logout(self):
        self._run(f'context logout {self.host}')

    def create_zone(
        self,
        config_file, 
        network_map_address,
        network_parameters,
        label,
        label_color
    ):
        self._login('network-maintainer', 'p4ssWord')
        token = self._run(f'zone create-subzone --config-file={config_file} --network-map-address={network_map_address} --network-parameters={network_parameters} --label={label} --label-color={label_color}')
        self._logout()
        return token

    def set_config(self, service, config_file):
        self._login('config-maintainer', 'p4ssWord')
        self._run(f'{service} config set -f={config_file}')
        self._logout()

    def get_subzones(self):
        self._login('config-maintainer', 'p4ssWord')
        subzones = self._run('zone get-subzones')
        self._logout()
        zones = sysi.run_get_stdout(f"echo {subzones} | grep id | rev | cut -d ' ' -f 1 | rev | sed -e 's/\,//' | xargs").split(' ')
        return zones

dlm = DownloadManager(username, password, wget)
logger = get_logger()
sysi = SystemInteract()
cenm_tool = CenmTool(nms_visual_version)

# Define service class to handle downloading and unzipping
class Service:
    def __init__(self, abb, artifact_name, version, ext, url, dlm = None):
        self.abb = abb
        self.dir = self._build_dir(abb)
        self.plugin = 'plugin' in abb
        self.repo = abb in repos
        self.artifact_name = artifact_name
        self.ext = ext
        self.version = version
        self.url = self._build_url(url)
        self.error = False
        self.dlm = dlm

    # dir builder
    def _build_dir(self, abb):
        if abb in ['auth', 'client', 'auth-plugin']:
            return 'auth'
        elif abb in ['gateway', 'cli', 'gateway-plugin']:
            return 'gateway'
        elif abb == 'crr-tool':
            return 'idman'
        elif abb == 'shell':
            return 'node'
        else:
            return abb

    # internal url builder
    def _build_url(self, url):
        return f'{url}/{self.artifact_name}/{self.version}/{self.artifact_name}-{self.version}.{self.ext}'

    # repo cloner
    def _clone_repo(self):
        if os.path.exists(f'cenm-{self.dir}'):
            print(f'cenm-{self.dir} already exists. Skipping clone.')
        else:
            print(f'Cloning cenm-{self.dir}')
            os.system(f'git clone https://github.com/tomstark99/cenm-{self.dir}.git --quiet')

    # move plugins to correct location
    def _handle_plugin(self, zip_name):
        if self.dir == 'auth':
            if not os.path.exists(f'cenm-auth/plugins'):
                os.system(f'mkdir cenm-auth/plugins')
            os.system(f'mv {zip_name} cenm-auth/plugins/accounts-baseline-cenm.jar')
        elif self.dir == 'gateway':
            if not os.path.exists(f'cenm-gateway/public/plugins'):
                os.system(f'mkdir -p cenm-gateway/public/plugins')
            if not os.path.exists(f'cenm-gateway/private/plugins'):
                os.system(f'mkdir -p cenm-gateway/private/plugins')
            os.system(f'cp {zip_name} cenm-gateway/private/plugins/cenm-gateway-plugin.jar')
            os.system(f'mv {zip_name} cenm-gateway/public/plugins/cenm-gateway-plugin.jar')
        # if self.ext == 'zip':
        #     os.system(f'(cd cenm-{self.abb}/plugins && unzip {zip_name} && rm {zip_name})')

    # make a copy of gateway for both public and private
    def _handle_gateway(self, zip_name):
        if 'cenm-tool' in zip_name:
            os.system(f'mv {zip_name} cenm-gateway/cenm-tool')
            if self.ext == 'zip':
                os.system(f'(cd cenm-gateway/cenm-tool && unzip -q {zip_name} && rm {zip_name} && chmod +x cenm)')
        else:
            os.system(f'cp {zip_name} cenm-gateway/public')
            os.system(f'mv {zip_name} cenm-gateway/private')

    def _install_idman_tool(self, zip_name):
        os.system(f'mkdir -p cenm-idman/tools/{self.artifact_name}')
        os.system(f'mv {zip_name} cenm-idman/tools/{self.artifact_name}')
        if self.ext == 'zip':
            os.system(f'(cd cenm-idman/tools/{self.artifact_name} && unzip -q {zip_name} && rm {zip_name})')

    def _install_corda_shell(self, zip_name):
        os.system(f'mv {zip_name} cenm-node/drivers/{zip_name}')

    # download command that fetches the artifact from artifactory
    def download(self):
        zip_name = f'{self.artifact_name}-{self.version}.{self.ext}'
        if self.repo:
            self._clone_repo()
        
        # Check for existing artifact
        for _, _, files in os.walk(f'cenm-{self.dir}'):
            if self.artifact_name == "pki-tool":
                if "pkitool.jar" in files:
                    print(f'pkitool.jar already exists. Skipping download.')
                    return
            elif self.artifact_name == "crr-submission-tool":
                if "crrsubmissiontool.jar" in files:
                    print(f'crrsubmissiontool.jar already exists. Skipping download.')
                    return
            else:
                if f'{self.artifact_name}.jar' in files or f'{self.artifact_name}-{self.version}.jar' in files:
                    print(f'{self.artifact_name}.jar already exists. Skipping download.')
                    return

        # If artifact not present then download it
        print(f'Downloading {zip_name}')
        self.error = self.dlm.download(self.url)

        if self.plugin:
            self._handle_plugin(zip_name)
        elif self.dir == 'gateway':
            self._handle_gateway(zip_name)
        elif self.artifact_name in ['crr-submission-tool']:
            self._install_idman_tool(zip_name)
        elif self.artifact_name in ['corda-shell']:
            self._install_corda_shell(zip_name)
        else:
            os.system(f'mv {zip_name} cenm-{self.dir}')
            if self.ext == 'zip':
                os.system(f'(cd cenm-{self.dir} && unzip -q {zip_name} && rm {zip_name})')
        return self.error

    def _register_node(self, artifact_name):
        logger.info(f'Registering {self.dir} to the network')
        print(f"RUNNING registration COMMAND FOR {self.artifact_name}")
        os.system(f'(cd cenm-{self.dir} && java -jar {artifact_name}.jar -f {self.dir}.conf --initial-registration --network-root-truststore ./certificates/network-root-truststore.jks --network-root-truststore-password trustpass)')

    def _copy_notary_node_info(self):
        logger.info(f'Copying notary node info to nmap')
        while not glob.glob('cenm-notary/nodeInfo-*'):
            logger.info(f'Waiting for nodeInfo file to be created')
            sleep(5)
        os.system(f'cp cenm-notary/nodeInfo-* cenm-nmap')
        logger.debug(f'Updating networkparameters.conf with node info')
        os.system(f'(cd cenm-nmap && perl -i -pe "s/^.*notaryNodeInfoFile: \\"\K.*(?=\\")/$(ls nodeInfo-*)/" networkparameters.conf)')
        new_params = sysi.run_get_stdout(f'(cd cenm-nmap && cat networkparameters.conf)')
        logger.info(f'new networkparams:\n{new_params}')

    def _set_network_params(self):
        logger.info(f'Setting network parameters')
        os.system(f'cd cenm-{self.dir} && java -jar networkmap.jar -f networkmap.conf --set-network-parameters networkparameters.conf --network-truststore ./certificates/network-root-truststore.jks --truststore-password trustpass --root-alias cordarootca')

    def _create_subzone(self):
        logger.info(f'Creating subzone')
        token = cenm_tool.create_zone("../../cenm-nmap/networkmap.conf", "127.0.0.1:20000", "../../cenm-nmap/networkparameters.conf", "Main", "#941213")
        logger.info(f'Network map token: {token}')
        logger.info("Applying identity manager config to subzone")
        token = cenm_tool.set_config("identity-manager", "../../cenm-idman/identitymanager.conf")
        logger.info(f'Identity manager token: {token}')
        logger.info("Applying signer config to subzone")
        token = cenm_tool.set_config("signer", "../../cenm-signer/signer.conf")
        logger.info(f'Signer token: {token}')

    def deploy(self):
        logger.info(f'Thread started to deploy {self.artifact_name}')
        if self.dir in ['auth', 'gateway', 'notary', 'node']:
            artifact_name = f'{self.artifact_name}-{self.version}'
            logger.debug(f'Artifact name updated to {artifact_name}')
            if self.dir == 'gateway':
                logger.info(f'Running: (cd cenm-{self.dir}/private && java -jar {artifact_name}.jar -f {self.dir}.conf) to start gateway service')
                # os.system(f'(cd cenm-{self.dir}/public && java -jar {artifact_name}.jar -f {artifact_name}.conf &)')
                print(f"RUNNING COMMAND FOR {self.artifact_name}")
                os.system(f'(cd cenm-{self.dir}/private && java -jar {artifact_name}.jar -f {self.dir}.conf)')
            elif self.dir in ['notary', 'node']:
                if not glob.glob('cenm-notary/nodeInfo*'):
                    logger.info(f'Running: notary registration')
                    self._register_node(artifact_name)
                    logger.info(f'Sleeping for 2 minutes to allow registration to complete and for network parameters to be signed')
                    os.system('sleep 120')
                while True:
                    try:
                        logger.info(f'Running: (cd cenm-{self.dir} && java -jar {artifact_name}.jar -f {self.dir}.conf) to start {self.dir} service')
                        cmd = os.system(f'(cd cenm-{self.dir} && java -jar {artifact_name}.jar -f {self.dir}.conf)')
                        if cmd != 0:
                            raise RuntimeError(f'{self.dir} service stopped.')
                    except:
                        logger.warning(f'{self.dir} service stopped. Restarting...')
            else:
                logger.info(f'Running: (cd cenm-{self.dir} && java -jar {artifact_name}.jar -f {self.dir}.conf --initial-user-name admin --initial-user-password p4ssWord --keep-running --verbose) to start {self.dir} service')
                os.system(f'(cd cenm-{self.dir} && java -jar {artifact_name}.jar -f {self.dir}.conf --initial-user-name admin --initial-user-password p4ssWord --keep-running --verbose)')

        elif self.dir == 'nmap':
            logger.info(f'Service is {self.dir}')
            if not glob.glob('cenm-nmap/nodeInfo*') and not glob.glob('cenm-notary/nodeInfo*'):
                self._copy_notary_node_info()
                self._set_network_params()
            logger.info(f'Running: (cd cenm-{self.dir} && java -jar networkmap.jar -f networkmap.conf) to start networkmap service')
            os.system(f'(cd cenm-{self.dir} && java -jar {self.artifact_name}.jar -f {self.artifact_name}.conf)')
        elif self.dir == 'zone':
            logger.info(f'Service is {self.dir}')
            logger.debug(f'running setupAuth.sh')
            os.system(f'(cd cenm-auth/setup-auth && bash setupAuth.sh)')
            logger.debug(f'finished running setupAuth.sh')
            # self._create_subzone() # Can't create subzone without zone service running
            logger.info(f'Running: (cd cenm-{self.dir} && java -jar {self.artifact_name}.jar --driver-class-name=org.h2.Driver --jdbc-driver= --user=zoneuser --password=password --url="jdbc:h2:file:./h2/zone-persistence;DB_CLOSE_ON_EXIT=FALSE;LOCK_TIMEOUT=10000;WRITE_DELAY=0;AUTO_SERVER_PORT=0" --run-migration=true --enm-listener-port=5061 --admin-listener-port=5063 --auth-host=127.0.0.1 --auth-port=8081 --auth-trust-store-location certificates/corda-ssl-trust-store.jks --auth-trust-store-password trustpass --auth-issuer "http://test" --auth-leeway 5 --tls=true --tls-keystore=certificates/corda-ssl-identity-manager-keys.jks --tls-keystore-password=password --tls-truststore=certificates/corda-ssl-trust-store.jks --tls-truststore-password=trustpass) to start {self.dir} service')
            os.system(f'(cd cenm-{self.dir} && java -jar {self.artifact_name}.jar --driver-class-name=org.h2.Driver --jdbc-driver= --user=zoneuser --password=password --url="jdbc:h2:file:./h2/zone-persistence;DB_CLOSE_ON_EXIT=FALSE;LOCK_TIMEOUT=10000;WRITE_DELAY=0;AUTO_SERVER_PORT=0" --run-migration=true --enm-listener-port=5061 --admin-listener-port=5063 --auth-host=127.0.0.1 --auth-port=8081 --auth-trust-store-location certificates/corda-ssl-trust-store.jks --auth-trust-store-password trustpass --auth-issuer "http://test" --auth-leeway 5 --tls=true --tls-keystore=certificates/corda-ssl-identity-manager-keys.jks --tls-keystore-password=password --tls-truststore=certificates/corda-ssl-trust-store.jks --tls-truststore-password=trustpass)')
        else:
            logger.info(f'Running: (cd cenm-{self.dir} && java -jar {self.artifact_name}.jar -f {self.artifact_name}.conf)')
            os.system(f'(cd cenm-{self.dir} && java -jar {self.artifact_name}.jar -f {self.artifact_name}.conf)')


    def clean(self, 
        deep: bool,
        artifacts: bool,
        certs: bool,
        runtime: bool
    ):
        runtime_files = {
            'dirs': ["logs", "h2", "ssh", "shell-commands", "djvm", "artemis", "brokers", "additional-node-infos"],
            'notary_files': ["process-id", "network-parameters", "nodekeystore.jks", "truststore.jks", "sslkeystore.jks", "certificate-request-id.txt"]
        }
        os.system(f'rm .logs/* > /dev/null 2>&1')
        if deep:
            os.system(f'rm -rf cenm-{self.dir}')
            return
        for root, dirs, files in os.walk(f'cenm-{self.dir}'):
            if artifacts:
                for file in files:
                    if file.endswith('.jar'):
                        os.system(f'rm {os.path.join(root, file)}')
                    elif file.endswith('.jks'):
                        os.system(f'rm {os.path.join(root, file)}')
                    elif file.endswith('.crl'):
                        os.system(f'rm {os.path.join(root, file)}')
                    elif file in ["cenm", "cenm.cmd"]:
                        os.system(f'rm {os.path.join(root, file)}')
                for dir in dirs:
                    if self.dir == "idman":
                        if os.path.join(root, dir).split("/")[-2] == "tools":
                            os.system(f'rm -rf {os.path.join(root, dir)}')
            if certs:
                for file in files:
                    if file.endswith('.jks'):
                        os.system(f'rm {os.path.join(root, file)}')
                    elif file.endswith('.crl'):
                        os.system(f'rm {os.path.join(root, file)}')
                for dir in dirs:
                    if self.dir == "pki":
                        if dir in ["crl-files", "trust-stores", "key-stores"]:
                            os.system(f'rm -rf {os.path.join(root, dir)}')
            if runtime:
                for file in files:
                    if file.startswith("nodeInfo"):
                        os.system(f'rm {os.path.join(root, file)}')
                    elif file.startswith("networkparameters"):
                        os.system(f'perl -i -pe "s/^.*notaryNodeInfoFile: \\"\K.*(?=\\")/INSERT_NODE_INFO_FILE_NAME_HERE/" {os.path.join(root, file)}')
                    elif file in runtime_files["notary_files"] and self.dir in ['notary', 'node']:
                        os.system(f'rm {os.path.join(root, file)} > /dev/null 2>&1')
                for dir in dirs:
                    if dir in runtime_files["dirs"]:
                        os.system(f'rm -rf {os.path.join(root, dir)}')

class CertificateGenerator:
    def __init__(self, services: List[Service]):
        # self.services = services
        self.pki_service = self._get_pki_service(services)
    
    def _get_pki_service(self, services):
        return services[[service.artifact_name for service in services].index('pki-tool')]

    # def _check_for_certs(self):
    #     certs = {}
    #     for service in self.services:
    #         if service.dir == 'gateway':
    #             if os.path.exists(f'cenm-{service.dir}/public/certificates'):
    #                 print(f'Certificates already exist for {service.dir}.')
    #                 certs[f'{service.dir}/public'] = True
    #             else:
    #                 certs[f'{service.dir}/public'] = False
    #             if os.path.exists(f'cenm-{service.dir}/private/certificates'):
    #                 print(f'Certificates already exist for {service.dir}.')
    #                 certs[f'{service.dir}/private'] = True
    #             else:
    #                 certs[f'{service.dir}/private'] = False
    #         else :
    #             if os.path.exists(f'cenm-{service.dir}/certificates'):
    #                 print(f'Certificates already exist for {service.dir}.')
    #                 certs[service.dir] = True
    #             else:
    #                 certs[service.dir] = False
    #     return certs

    def _copy(self, source, destination):
        os.system(f'cp cenm-{self.pki_service.dir}/{source} {destination}')

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
        print('Distributing certificates')
        self._auth()
        self._gateway()
        self._idman()
        self._nmap()
        self._notary()
        self._node()
        self._signer()
        self._zone()

    def generate(self):
        certs = {}
        for path in ['crl-files', 'key-stores', 'trust-stores']:
            if os.path.exists(f'cenm-{self.pki_service.dir}/{path}'):
                print(f'{path} already exists. Skipping generation.')
                certs[path] = True
            else:
                certs[path] = False
        if os.path.exists(f'cenm-auth/certificates/jwt-store.jks'):
            print('Auth jwt-store already exists. Skipping generation.')
        else:
            print('Generating auth jwt-store')
            os.system(f'(cd cenm-auth && keytool -genkeypair -alias oauth-test-jwt -keyalg RSA -keypass password -keystore certificates/jwt-store.jks -storepass password -dname "CN=abc1, OU=abc2, O=abc3, L=abc4, ST=abc5, C=abc6" > /dev/null 2>&1)')

        if not all(certs.values()):
            print('Generating certificates')
            os.system(f'(cd cenm-{self.pki_service.dir} && java -jar pkitool.jar -f pki.conf)')
        self._distribute_certs()

class DatabaseManager:
    def __init__(self, services: List[Service], dlm: DownloadManager):
        self.db_services = ['auth', 'idman', 'nmap', 'notary', 'node', 'zone']
        self.db_drivers = [
            "https://repo1.maven.org/maven2/com/microsoft/sqlserver/mssql-jdbc/8.2.2.jre8/mssql-jdbc-8.2.2.jre8.jar", 
            "https://repo1.maven.org/maven2/org/postgresql/postgresql/42.5.2/postgresql-42.5.2.jar",
            "https://repo1.maven.org/maven2/com/oracle/ojdbc/ojdbc8/19.3.0.0/ojdbc8-19.3.0.0.jar"
        ]
        self.services_with_db = self._get_services_with_db(services)
        self.dlm = dlm
        
    def _get_services_with_db(self, services: List[Service]):
        return [service for service in services if service.abb in self.db_services]

    def _get_jar_name(self, url):
        return url.split('/')[-1]

    def _copy(self, source, destination):
        os.system(f'cp {source} {destination}')

    def _exists(self, driver):
        jar_file = self._get_jar_name(driver)
        exists_in_service = {}
        for service in self.db_services:
            for _, _, files in os.walk(f'cenm-{service}'):
                if jar_file in files:
                    exists_in_service[service] = True
            if service not in exists_in_service:
                exists_in_service[service] = False
        return exists_in_service

    def _cleanup(self, driver):
        os.system(f'rm {self._get_jar_name(driver)} > /dev/null 2>&1')

    def _distribute_drivers(self, exists_dict):
        for service in self.db_services:
            if not os.path.exists(f'cenm-{service}/drivers'):
                os.mkdir(f'cenm-{service}/drivers')
        for driver, exists in exists_dict.items():
            if not all(exists.values()):
                for service in self.db_services:
                    if not exists[service]:
                        self._copy(self._get_jar_name(driver), f'cenm-{service}/drivers')
            self._cleanup(driver)

    def download(self):
        download_errors = {}
        exists_dict = {}

        for driver in self.db_drivers:
            exists_dict[driver] = self._exists(driver)

        for driver, exists in exists_dict.items():
            if not all(exists.values()):
                download_errors[self._get_jar_name(driver)] = self.dlm.download(driver)
            else:
                print(f'{self._get_jar_name(driver)} already exists. Skipping download.')

        self._distribute_drivers(exists_dict)
        return download_errors

class DeploymentManager:

    def __init__(self, services, printer):
        self.deployment_services = services
        self.printer = printer
        self.functions = {s.artifact_name:s.deploy for s in self.deployment_services}
        self.processes = []

    def deploy_services(self):
        # service1 = self.deployment_services[0]
        # service2 = self.deployment_services[1]
        try:
            logger.info("Starting the cenm deployment")
            for service, function in self.functions.items():
                logger.info(f'attempting to deploy {service}')
                process = multiprocessing.Process(target=function, name=service, daemon=True)
                # thread = threading.Thread(target=function, daemon=True)
                self.processes.append(process)
                process.start()
                logger.info(f'deployed {service} waiting 30 seconds until next service')
                sleep(30)

            self.printer.print_deployment_complete()
            
            while True:
                logger.info('Running process health check')
                for process in self.processes:
                    process.join(timeout=0)
                    if process.is_alive():
                        logger.info(f'{process} is healthy')
                    else:
                        logger.error(f'{process} is unhealthy, restarting')
                        process.terminate()
                        self.processes.remove(process)
                        new_process = multiprocessing.Process(target=self.functions[process.name], name=process.name, daemon=True)
                        new_process.start()
                        self.processes.append(new_process)
                sleep(30)

        except KeyboardInterrupt:
            logger.debug('Keyboard interrupt detected, terminating processes')
            for process in self.processes:
                logger.info(f'Terminating {process}')
                process.terminate()
                logger.info(f'Waiting for {process} to exit gracefully')
                process.join()
            # for process in self.processes:
            #     process.join()
            logger.info('All processes terminated, exiting')
            exit(1)

# Define list of services to download
global_services = [
    Service('auth', 'accounts-application', auth_version, 'jar', f'{base_url}/{ext_package}/accounts', dlm),
    Service('client', 'accounts-client', auth_version, 'jar', f'{base_url}/{ext_package}/accounts', dlm),
    Service('auth-plugin', 'accounts-baseline-cenm', cenm_version, 'jar', f'{base_url}/{enm_package}', dlm),
    Service('gateway', 'gateway-service', gateway_version, 'jar', f'{base_url}/{ext_package}/gateway', dlm),
    Service('gateway-plugin', 'cenm-gateway-plugin', nms_visual_version, 'jar', f'{base_url}/{enm_package}', dlm),
    Service('cli', 'cenm-tool', nms_visual_version, 'zip', f'{base_url}/{enm_package}', dlm),
    Service('idman', 'identitymanager', cenm_version, 'zip', f'{base_url}/{enm_package}/services', dlm),
    Service('crr-tool', 'crr-submission-tool', cenm_version, 'zip', f'{base_url}/{enm_package}/tools', dlm),
    Service('nmap', 'networkmap', cenm_version, 'zip', f'{base_url}/{enm_package}/services', dlm),
    Service('notary', 'corda', corda_version, 'jar', f'{base_url}/{corda_package}', dlm),
    Service('node', 'corda', corda_version, 'jar', f'{base_url}/{corda_package}', dlm),
    Service('shell', 'corda-shell', corda_version, 'jar', f'{base_url}/{corda_package}', dlm),
    Service('pki', 'pki-tool', cenm_version, 'zip', f'{base_url}/{enm_package}/tools', dlm),
    Service('signer', 'signer', cenm_version, 'zip', f'{base_url}/{enm_package}/services', dlm),
    Service('zone', 'zone', cenm_version, 'zip', f'{base_url}/{enm_package}/services', dlm)
]

# this is the correct deployment order
deployment_services = [
    Service('idman', 'identitymanager', cenm_version, 'zip', f'{base_url}/{enm_package}/services'),
    Service('signer', 'signer', cenm_version, 'zip', f'{base_url}/{enm_package}/services'),
    Service('notary', 'corda', corda_version, 'jar', f'{base_url}/{corda_package}'),
    Service('nmap', 'networkmap', cenm_version, 'zip', f'{base_url}/{enm_package}/services'),
    Service('auth', 'accounts-application', auth_version, 'jar', f'{base_url}/{ext_package}/accounts'),
    Service('gateway', 'gateway-service', gateway_version, 'jar', f'{base_url}/{ext_package}/gateway'),
    Service('zone', 'zone', cenm_version, 'zip', f'{base_url}/{enm_package}/services')
    # Service('node', 'corda', corda_version, 'jar', f'{base_url}/{corda_package}')
]

class Printer:

    def print_cenm_version(self):
        print("")
        print("Cenm local deployment manager")
        print("=====================================")
        print(f'Current CENM version:    {cenm_version}')
        print(f'Current Auth version:    {auth_version}')
        print(f'Current Gateway version: {gateway_version}')
        print(f'Current NMS version:     {nms_visual_version}')
        print("")
        print(f'Current Corda version:   {corda_version}')

    def print_deployment_complete(self):
        print("")
        print("=== Deployment complete ===")
        print("")
        print("Deployment logs can be found under: .logs/default-deployment.log")

    def print_end_of_script_report(self, download_errors, download_errors_db):
        print("")
        print("=== End of script report ===")
        if any(download_errors.values()):
            print("The following errors were encountered when downloading artifacts:")
            for artifact_name, error in download_errors.items():
                if error:
                    print(f'Error encountered when downloading {artifact_name}, please check version and try again.')
        else:
            print("All artifacts downloaded successfully.")
        if any(download_errors_db.values()):
            print("The following errors were encountered when downloading database drivers:")
            for artifact_name, error in download_errors_db.items():
                if error:
                    print(f'Error encountered when downloading {artifact_name}, please check version and try again.')
        else:
            print("All database drivers downloaded successfully.")

def main(args: argparse.Namespace):

    printer = Printer()

    if args.version:
        printer.print_cenm_version()
        exit(0)

    clean_args = [args.clean, args.deep_clean, args.clean_artifacts, args.clean_certs]
    if sum(clean_args) > 1:
        raise ValueError("Cannot use more than one of the following flags: --clean, --deep-clean, --clean-artifacts, --clean-certs")

    if args.deep_clean:
        for service in global_services:
            service.clean(deep=True, artifacts=False, certs=False, runtime=False)
    elif args.clean_artifacts:
        for service in global_services:
            service.clean(deep=False, artifacts=True, certs=True, runtime=True)
    elif args.clean:
        for service in global_services:
            service.clean(deep=False, artifacts=False, certs=False, runtime=True)
    elif args.clean_certs:
        for service in global_services:
            service.clean(deep=False, artifacts=False, certs=True, runtime=False)

    download_errors = {}
    if args.setup_dir_structure:
        for service in global_services:
            download_errors[service.artifact_name] = service.download()
        database_manager = DatabaseManager(global_services, dlm)
        download_errors_db = database_manager.download()

    if args.generate_certs:
        cert_generator = CertificateGenerator(global_services)
        cert_generator.generate()

    if args.run_default_deployment:
        deployment_manager = DeploymentManager(deployment_services, printer)
        deployment_manager.deploy_services()

    # end of script report
    if args.setup_dir_structure:
        printer.print_end_of_script_report(download_errors, download_errors_db)

if __name__ == '__main__':
    main(parser.parse_args())
