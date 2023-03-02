import os
from typing import List, Any, Tuple, Dict
import argparse

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
    corda_version = '4.5.11'
except KeyError as e:
    raise KeyError(f"Missing variable in .env file: {e}")

# Useful variables
base_url = 'https://software.r3.com/artifactory'
ext_package = 'extensions-lib-release-local/com/r3/appeng'
enm_package = 'r3-enterprise-network-manager/com/r3/enm'
repos = ['auth', 'gateway', 'idman', 'nmap', 'pki', 'signer', 'zone']

# Define service class to handle downloading and unzipping
class Service:
    def __init__(self, abb, artifact_name, version, ext, url):
        self.dir = self._build_dir(abb)
        self.plugin = abb == 'plugin'
        self.repo = abb in repos
        self.artifact_name = artifact_name
        self.ext = ext
        self.version = version
        self.url = self._build_url(url)
        self.drivers = ['https://jdbc.postgresql.org/download/postgresql-42.2.9.jar']

    # dir builder
    def _build_dir(self, abb):
        if abb in ['auth', 'client', 'plugin']:
            return 'auth'
        elif abb == 'cli':
            return 'gateway'
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

    # move auth plugin to correct location
    def _handle_plugin(self, zip_name):
        if not os.path.exists(f'cenm-auth/plugins'):
            os.system(f'mkdir cenm-auth/plugins')
        os.system(f'mv {zip_name} cenm-auth/plugins')
        # if self.ext == 'zip':
        #     os.system(f'(cd cenm-{self.abb}/plugins && unzip {zip_name} && rm {zip_name})')

    # make a copy of gateway for both public and private
    def _handle_gateway(self, zip_name):
        if 'cenm-tool' in zip_name:
            os.system(f'mv {zip_name} cenm-gateway')
            if self.ext == 'zip':
                os.system(f'(cd cenm-gateway && unzip {zip_name} && rm {zip_name})')
        else:
            os.system(f'cp {zip_name} cenm-gateway/public')
            os.system(f'mv {zip_name} cenm-gateway/private')

    # download command that fetches the artifact from artifactory
    def download(self):
        zip_name = f'{self.artifact_name}-{self.version}.{self.ext}'
        if self.repo:
            self._clone_repo()
        
        # Check for existing artifact
        for _, _, files in os.walk(f'cenm-{self.dir}'):
            if f'{self.artifact_name}.jar' in files or f'{self.artifact_name}-{self.version}.jar' in files:
                print(f'{self.artifact_name}.jar already exists. Skipping download.')
                return

        # If artifact not present then download it
        print(f'Downloading {zip_name}')
        os.system(f'wget --user {username} --password {password} {self.url}')
        if self.plugin:
            self._handle_plugin(zip_name)
        elif self.dir == 'gateway':
            self._handle_gateway(zip_name)
        else:
            os.system(f'mv {zip_name} cenm-{self.dir}')
            if self.ext == 'zip':
                os.system(f'(cd cenm-{self.dir} && unzip {zip_name} && rm {zip_name})')

    # WIP download jdbc drivers
    def download_drivers(self):
        # TODO: find a way to check if driver is already downloaded
        if not os.path.exists(f'cenm-{self.dir}/drivers'):
            os.system(f'mkdir cenm-{self.dir}/drivers')
        for driver in self.drivers:
            os.system(f'wget {driver} -P cenm-{self.dir}/drivers')

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
        self._copy('key-stores/gateway-private-ssl-keys.jks', 'cenm-gateway/private/certificates')
        self._copy('key-stores/gateway-ssl-keys.jks', 'cenm-gateway/public/certificates')

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

    # def _notary(self):
    #     # trust stores
    #     self._copy('trust-stores/network-root-truststore.jks' 'cenm-notary/certificates')

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
        # self._notary()
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

        if not all(certs.values()):
            print('Generating certificates')
            os.system(f'(cd cenm-{self.pki_service.dir} && java -jar pkitool.jar -f pki.conf)')
        self._distribute_certs()
                



# Define list of services to download
global_services = [
    Service('auth', 'accounts-application', auth_version, 'jar', f'{base_url}/{ext_package}/accounts'),
    Service('client', 'accounts-client', auth_version, 'jar', f'{base_url}/{ext_package}/accounts'),
    Service('gateway', 'gateway-service', gateway_version, 'jar', f'{base_url}/{ext_package}/gateway'),
    Service('plugin', 'accounts-baseline-cenm', cenm_version, 'jar', f'{base_url}/{enm_package}'),
    Service('cli', 'cenm-tool', cenm_version, 'zip', f'{base_url}/{enm_package}'),
    Service('idman', 'identitymanager', cenm_version, 'zip', f'{base_url}/{enm_package}/services'),
    Service('nmap', 'networkmap', cenm_version, 'zip', f'{base_url}/{enm_package}/services'),
    # Service('notary', 'notary', corda_version, 'zip', f'{base_url}/{enm_package}/services'),
    Service('pki', 'pki-tool', cenm_version, 'zip', f'{base_url}/{enm_package}/tools'),
    Service('signer', 'signer', cenm_version, 'zip', f'{base_url}/{enm_package}/services'),
    Service('zone', 'zone', cenm_version, 'zip', f'{base_url}/{enm_package}/services')
]

def main(args: argparse.Namespace):

    if args.setup_dir_structure:
        for service in global_services:
            service.download()
    if args.generate_certs:
        cert_generator = CertificateGenerator(global_services)
        cert_generator.generate()

if __name__ == '__main__':
    main(parser.parse_args())