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
parser.add_argument(
    '--clean', 
    default=False, 
    action='store_true', 
    help='Remove all generated run-time files'
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
base_url = 'https://software.r3.com/artifactory'
ext_package = 'extensions-lib-release-local/com/r3/appeng'
enm_package = 'r3-enterprise-network-manager/com/r3/enm'
corda_package = 'corda-releases/net/corda'
repos = ['auth', 'gateway', 'idman', 'nmap', 'notary', 'pki', 'signer', 'zone']

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
        # self.drivers = ['https://jdbc.postgresql.org/download/postgresql-42.2.9.jar']
        self.error = False

    # dir builder
    def _build_dir(self, abb):
        if abb in ['auth', 'client', 'plugin']:
            return 'auth'
        elif abb == 'cli':
            return 'gateway'
        elif abb == 'crr-tool':
            return 'idman'
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
        os.system(f'mv {zip_name} cenm-auth/plugins/accounts-baseline-cenm.jar')
        # if self.ext == 'zip':
        #     os.system(f'(cd cenm-{self.abb}/plugins && unzip {zip_name} && rm {zip_name})')

    # make a copy of gateway for both public and private
    def _handle_gateway(self, zip_name):
        if 'cenm-tool' in zip_name:
            os.system(f'mv {zip_name} cenm-gateway/cenm-tool')
            if self.ext == 'zip':
                os.system(f'(cd cenm-gateway/cenm-tool && unzip {zip_name} && rm {zip_name} && chmod +x cenm)')
        else:
            os.system(f'cp {zip_name} cenm-gateway/public')
            os.system(f'mv {zip_name} cenm-gateway/private')

    def _install_idman_tool(self, zip_name):
        os.system(f'mkdir -p cenm-idman/tools/{self.artifact_name}')
        os.system(f'mv {zip_name} cenm-idman/tools/{self.artifact_name}')
        if self.ext == 'zip':
            os.system(f'(cd cenm-idman/tools/{self.artifact_name} && unzip {zip_name} && rm {zip_name})')

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

        cmd = os.system(f'wget -q --show-progress --user {username} --password {password} {self.url}')
        if os.WEXITSTATUS(cmd) != 0:
            cmd2 = os.system(f'wget --progress=bar:force:noscroll --user {username} --password {password} {self.url}')
            if os.WEXITSTATUS(cmd2) != 0:
                self.error = True
        if self.plugin:
            self._handle_plugin(zip_name)
        elif self.dir == 'gateway':
            self._handle_gateway(zip_name)
        elif self.artifact_name in ['crr-submission-tool']:
            self._install_idman_tool(zip_name)
        else:
            os.system(f'mv {zip_name} cenm-{self.dir}')
            if self.ext == 'zip':
                os.system(f'(cd cenm-{self.dir} && unzip {zip_name} && rm {zip_name})')
        return self.error

    # WIP download jdbc drivers
    def download_drivers(self):
        # TODO: find a way to check if driver is already downloaded
        if not os.path.exists(f'cenm-{self.dir}/drivers'):
            os.system(f'mkdir cenm-{self.dir}/drivers')
        for driver in self.drivers:
            os.system(f'wget {driver} -P cenm-{self.dir}/drivers')

    def clean(self, 
        deep: bool,
        artifacts: bool,
        runtime: bool
    ):
        runtime_files = {
            'dirs': ["logs", "h2", "ssh", "shell-commands", "djvm", "cordapps", "artemis", "brokers", "additional-node-infos"],
            'notary_files': ["process-id", "network-parameters", "nodekeystore.jks", "truststore.jks", "sslkeystore.jks"]
        }
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
            if runtime:
                for file in files:
                    if file.startswith("nodeInfo"):
                        os.system(f'rm {os.path.join(root, file)}')
                    if file in runtime_files["notary_files"] and self.dir == "notary":
                        os.system(f'rm {os.path.join(root, file)}')
                for dir in dirs:
                    if dir in runtime_files["dirs"]:
                        os.system(f'rm -rf {os.path.join(root, dir)}')
                    if self.dir == "idman":
                        if os.path.join(root, dir).split("/")[-2] == "tools":
                            os.system(f'rm -rf {os.path.join(root, dir)}')
                    if self.dir == "pki":
                        if dir in ["crl-files", "trust-stores", "key-stores"]:
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

    def _notary(self):
        # trust stores
        self._copy('trust-stores/network-root-truststore.jks', 'cenm-notary/certificates')

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
    Service('cli', 'cenm-tool', nms_visual_version, 'zip', f'{base_url}/{enm_package}'),
    Service('idman', 'identitymanager', cenm_version, 'zip', f'{base_url}/{enm_package}/services'),
    Service('crr-tool', 'crr-submission-tool', cenm_version, 'zip', f'{base_url}/{enm_package}/tools'),
    Service('nmap', 'networkmap', cenm_version, 'zip', f'{base_url}/{enm_package}/services'),
    Service('notary', 'corda', corda_version, 'jar', f'{base_url}/{corda_package}'),
    Service('pki', 'pki-tool', cenm_version, 'zip', f'{base_url}/{enm_package}/tools'),
    Service('signer', 'signer', cenm_version, 'zip', f'{base_url}/{enm_package}/services'),
    Service('zone', 'zone', cenm_version, 'zip', f'{base_url}/{enm_package}/services')
]

def main(args: argparse.Namespace):

    download_errors = {}
    if args.setup_dir_structure:
        for service in global_services:
            download_errors[service.artifact_name] = service.download()
        
    if args.generate_certs:
        cert_generator = CertificateGenerator(global_services)
        cert_generator.generate()

    if args.clean and args.deep_clean:
        raise ValueError("Cannot use both --clean and --deep-clean flags.")
    if args.clean and args.clean_artifacts:
        raise ValueError("Cannot use both --clean and --clean-artifacts flags.")
    if args.deep_clean and args.clean_artifacts:
        raise ValueError("Cannot use both --deep-clean and --clean-artifacts flags.")

    if args.deep_clean:
        for service in global_services:
            service.clean(deep=True, artifacts=False, runtime=False)
    elif args.clean_artifacts:
        for service in global_services:
            service.clean(deep=False, artifacts=True, runtime=True)
    elif args.clean:
        for service in global_services:
            service.clean(deep=False, artifacts=False, runtime=True)


    # end of script report
    if args.setup_dir_structure:
        print("")
        print("=== End of script report ===")
        if any(download_errors.values()):
            print("The following errors were encountered when downloading artifacts:")
            for artifact_name, error in download_errors.items():
                if error:
                    print(f'Error encountered when downloading {artifact_name}, please check version and try again.')
        else:
            print("All artifacts downloaded successfully.")

if __name__ == '__main__':
    main(parser.parse_args())
