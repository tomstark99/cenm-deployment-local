import os
from .src.managers.download_manager import DownloadManager

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
        os.system(f'rm {self._get_jar_name(driver)}')

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