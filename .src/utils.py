import logging
import os
from enum import Enum
from typing import List, Dict
import warnings
import functools
import uuid

def deprecated(func):
    """This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emitted
    when the function is used.
    
    """
    @functools.wraps(func)
    def new_func(*args, **kwargs):
        warnings.simplefilter('always', DeprecationWarning)  # turn off filter
        warnings.warn("Call to deprecated function {}.".format(func.__name__),
                      category=DeprecationWarning,
                      stacklevel=2)
        warnings.simplefilter('default', DeprecationWarning)  # reset filter
        return func(*args, **kwargs)
    return new_func

class Constants(Enum):
    BASE_URL = 'https://software.r3.com/artifactory'
    GITHUB_URL = 'https://github.com/tomstark99'
    EXT_PACKAGE = 'extensions-lib-release-local/com/r3/appeng'
    ENM_PACKAGE = 'r3-enterprise-network-manager/com/r3/enm'
    CORDA_PACKAGE = 'r3-corda-releases/com/r3/corda'
    CORDAPP_PACKAGE = 'corda-releases/net/corda'

    MSSQL_DRIVER = 'https://repo1.maven.org/maven2/com/microsoft/sqlserver/mssql-jdbc/8.2.2.jre8/mssql-jdbc-8.2.2.jre8.jar'
    POSTGRES_DRIVER = 'https://repo1.maven.org/maven2/org/postgresql/postgresql/42.5.2/postgresql-42.5.2.jar'
    ORACLE_DRIVER = 'https://repo1.maven.org/maven2/com/oracle/ojdbc/ojdbc8/19.3.0.0/ojdbc8-19.3.0.0.jar'

    REPOS = ['auth', 'gateway', 'idman', 'nmap', 'notary', 'node', 'pki', 'signer', 'zone']
    DB_SERVICES = ['auth', 'idman', 'nmap', 'notary', 'node', 'zone']

    RUNTIME_FILES = {
        'dirs': ["logs", "h2", "ssh", "shell-commands", "djvm", "artemis", "brokers", "additional-node-infos"],
        'notary_files': ["process-id", "network-parameters", "nodekeystore.jks", "truststore.jks", "sslkeystore.jks", "certificate-request-id.txt"]
    }

    IDMAN_DEPLOY_TIME = 10
    SIGNER_DEPLOY_TIME = 10
    NMAP_DEPLOY_TIME = 20
    AUTH_DEPLOY_TIME = 15
    GATEWAY_DEPLOY_TIME = 5
    ZONE_DEPLOY_TIME = 10

    NODE_DEPLOY_TIME = 70
    

class Logger:
    """Logger management

    Args:
        name:
            The name of the class that called the logger.

    """
    def __init__(self):
        # self.name = name
        self.formatter = logging.Formatter('[%(asctime)s, %(levelname)s] %(name)s %(message)s')

    def _set_logging_config(self, logger_name, log_file, level=logging.DEBUG):
        logger = logging.getLogger(logger_name)

        fileHandler = logging.FileHandler(log_file, mode='w')
        fileHandler.setFormatter(self.formatter)

        streamHandler = logging.StreamHandler()
        streamHandler.setFormatter(self.formatter)

        logger.setLevel(level)
        logger.addHandler(fileHandler)
        logger.addHandler(streamHandler)

    def get_logger(self, name):
        """Create a logger

        Returns:
            Returns a logger object with the name of the class that called it.

        """
        # handler = logging.FileHandler(f".logs/default-deployment-{self.name}.log")
        # handler.setFormatter(self.formatter)
        # # logging.basicConfig(
        # #     filename=f".logs/default-deployment-{self.name}.log",
        # #     filemode='a',
        # #     format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
        # #     datefmt='%H:%M:%S',
        # #     level=logging.DEBUG
        # # )
        # logger = logging.getLogger(self.name)
        # logger.setLevel(logging.DEBUG)
        # logger.addHandler(handler)
        # print(os.getcwd())
        self._set_logging_config(name, f".logs/default-deployment-{name}.log")
        return logging.getLogger(name)
        # return logging.getLogger(self.name)
        # return logger
        # print(f'creating logger with name: {self.name}')
        # return logging.getLogger(self.name)

class Printer:
    """Printer for standard printing

    Deprecated class: use ExceptionGroup in favour.
    other print statements can be done inline in class

    """
    def __init__(self,
        cenm_version: str,
        auth_version: str,
        gateway_version: str,
        nms_visual_version: str,
        corda_version: str
    ):
        self.cenm_version = cenm_version
        self.auth_version = auth_version
        self.gateway_version = gateway_version
        self.nms_visual_version = nms_visual_version
        self.corda_version = corda_version

    @deprecated
    def print_cenm_version(self):
        print("""
Cenm local deployment manager
=====================================

Current CENM version:    {}
Current Auth version:    {}
Current Gateway version: {}
Current NMS version:     {}

Current Corda version:   {}

        """.format(
            self.cenm_version,
            self.auth_version,
            self.gateway_version,
            self.nms_visual_version,
            self.corda_version
        ))

    @deprecated
    def print_deployment_complete(self):
        print("""
Deployment complete
=====================================

Deployment logs can be found under: .logs/default-deployment.log

        """)

    @deprecated
    def print_end_of_script_report(self, download_errors, download_errors_db):
        print("""
End of script report
=====================================
        """)
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

    @deprecated
    def print_end_of_check_report(self, check_errors):
        print("""
End of validation report
=====================================
        """)
        if any(check_errors.values()):
            print("The following errors were encountered when validating artifacts:")
            for artifact_name, error in check_errors.items():
                if error:
                    print(f'Failed to validate {artifact_name}, artifact not found.')
        else:
            print("All artifacts validated successfully.")

class SystemInteract:
    """Class for using system commands

    """
    def path_exists(self, path) -> bool:
        return os.path.exists(path)

    def sleep(self, seconds):
        os.system(f'sleep {seconds}')

    def perl(self, file, predicate, replace, multi_line: bool = False):
        if multi_line:
            os.system(f'perl -0777 -i -pe "s/{predicate}/{replace}/" {file}')
        else:
            os.system(f'perl -i -pe "s/{predicate}/{replace}/" {file}')

    def remove(self, path, silent: bool = False):
        if silent:
            os.system(f'rm -rf {path} > /dev/null 2>&1')
        else:
            os.system(f'rm -rf {path}')

    def run(self, cmd):
        os.system(cmd)

    def run_get_exit_code(self, cmd, silent: bool = False) -> int:
        if silent:
            return os.system(f'{cmd} > /dev/null 2>&1')
        else:
            return os.system(cmd)

    def run_get_stdout(self, cmd) -> str:
        unique_file = f'.tmp-{uuid.uuid4().hex}'
        os.system(f'{cmd} > {unique_file}')
        try:
            with open(unique_file, 'r') as f:
                out = f.read()
            self.remove(unique_file, silent=True)
        except:
            out = 'E: Could not read stdout'
        return out

class CenmTool:
    """Class for using cenm cli tool

    Args:
        version:
            The version of the cenm cli tool to use.

    """
    def __init__(self, nms_visual_version: str):
        self.host = 'http://127.0.0.1:8089'
        self.path = 'cenm-gateway/cenm-tool'
        self.jar = f'cenm-tool-{nms_visual_version}.jar'
        self.sysi = SystemInteract()

    def _run(self, cmd: str):
        print(f'Running: {cmd}')
        return self.sysi.run_get_stdout(f'(cd {self.path} && java -jar {self.jar} {cmd})')

    def _login(self, username: str, password: str):
        self._run(f'context login -s {self.host} -u {username} -p {password}')
    
    def _logout(self):
        self._run(f'context logout {self.host}')

    def create_zone(self,
        config_file: str, 
        network_map_address: str,
        network_parameters: str, 
        label: str,
        label_color: str
    ) -> str:
        self._login('network-maintainer', 'p4ssWord')
        token = self._run(f'zone create-subzone --config-file={config_file} --network-map-address={network_map_address} --network-parameters={network_parameters} --label={label} --label-color="{label_color}" --zone-token')
        self._logout()
        return token

    def set_config(self, service: str, config_file: str, subzone: str = None) -> str:
        self._login('config-maintainer', 'p4ssWord')
        if subzone:
            token = self._run(f'{service} config set -s {subzone} -f={config_file} --zone-token')
        else:
            token = self._run(f'{service} config set -f={config_file} --zone-token')
        self._logout()
        return token

    def set_admin_address(self, service: str, address: str, subzone: str = None):
        self._login('config-maintainer', 'p4ssWord')
        # You can only specify sub_zone for netmap
        if subzone and service == "netmap":
            self._run(f'{service} config set-admin-address -s {subzone} -a={address}')
        else:
            self._run(f'{service} config set-admin-address -a={address}')
        self._logout()

    def get_subzones(self) -> List[str]:
        self._login('config-maintainer', 'p4ssWord')
        subzones = self._run('zone get-subzones')
        self._logout()
        zones = self.sysi.run_get_stdout(f"echo \"{subzones}\" | grep id | rev | cut -d ' ' -f 1 | rev | xargs").replace(',','').replace('\n','').split(' ')
        return zones

    def cenm_subzone_deployment_init(self) -> Dict[str, str]:
        tokens = {}

        self.set_admin_address('identity-manager', 'localhost:5053')
        # print(self.sysi.run_get_stdout(f'(cd {self.path} && cat ../../cenm-idman/identitymanager.conf)'))
        tokens['idman'] = self.set_config('identity-manager', '../../cenm-idman/identitymanager.conf')
        
        self.set_admin_address('netmap', 'localhost:5055')
        # print(self.sysi.run_get_stdout(f'(cd {self.path} && cat ../../cenm-nmap/networkparameters.conf)'))
        tokens['nmap'] = self.create_zone(
            config_file='../../cenm-nmap/networkmap.conf',
            network_map_address='localhost:20000',
            network_parameters='../../cenm-nmap/networkparameters.conf',
            label='Main',
            label_color='#941213'
        )
        self.set_admin_address('signer', 'localhost:5054')
        # print(self.sysi.run_get_stdout(f'(cd {self.path} && cat ../../cenm-signer/signer.conf)'))
        tokens['signer'] = self.set_config('signer', '../../cenm-signer/signer.conf')
        return tokens

    def cenm_set_subzone_config(self, subzone: str) -> str:
        # necessary step?
        self.set_admin_address('identity-manager', 'localhost:5053', subzone=subzone)
        self.set_admin_address('netmap', 'localhost:5055', subzone=subzone)

        return self.set_config('netmap', '../../cenm-nmap/networkmap.conf', subzone=subzone)