import os

# Check if .env file exists
if not os.path.exists(".env"):
    raise FileNotFoundError("No .env file found. Please create one and try again.")

with open(".env", 'r') as f:
    # dictionary comprehension to read the build.args file, split each value on '=' and create a map of key:value
    args = {key:value for (key,value) in [x.strip().split("=") for x in f.readlines()]}

# Get variables from .env file
username = args["ARTIFACTORY_USERNAME"]
password = args["ARTIFACTORY_API_KEY"]
auth_version = args["AUTH_VERSION"]
gateway_version = args["GATEWAY_VERSION"]
cenm_version = args["CENM_VERSION"]

# Useful variables
base_url = 'https://software.r3.com/artifactory'
ext_package = 'extensions-lib-release-local/com/r3/appeng'
enm_package = 'r3-enterprise-network-manager/com/r3/enm'
repos = ['auth', 'gateway', 'idman', 'nmap', 'pki', 'signer', 'zone']

# Define service class to handle downloading and unzipping
class Service:
    def __init__(self, abb, artifact_name, version, ext, url):
        self.dir = 'auth' if abb in ['auth', 'client', 'plugin'] else abb
        self.plugin = abb == 'plugin'
        self.repo = abb in repos
        self.artifact_name = artifact_name
        self.ext = ext
        self.version = version
        self.url = self._build_url(url)
        self.drivers = ['https://jdbc.postgresql.org/download/postgresql-42.2.9.jar']

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
        
# Define list of services to download
global_services = [
    Service('auth', 'accounts-application', auth_version, 'jar', f'{base_url}/{ext_package}/accounts'),
    Service('client', 'accounts-client', auth_version, 'jar', f'{base_url}/{ext_package}/accounts'),
    Service('gateway', 'gateway-service', gateway_version, 'jar', f'{base_url}/{ext_package}/gateway'),
    Service('plugin', 'accounts-baseline-cenm', cenm_version, 'jar', f'{base_url}/{enm_package}'),
    Service('idman', 'identitymanager', cenm_version, 'zip', f'{base_url}/{enm_package}/services'),
    Service('nmap', 'networkmap', cenm_version, 'zip', f'{base_url}/{enm_package}/services'),
    Service('pki', 'pki-tool', cenm_version, 'zip', f'{base_url}/{enm_package}/tools'),
    Service('signer', 'signer', cenm_version, 'zip', f'{base_url}/{enm_package}/services'),
    Service('zone', 'zone', cenm_version, 'zip', f'{base_url}/{enm_package}/services')
]

def main():
    for service in global_services:
        service.download()

if __name__ == '__main__':
    main()