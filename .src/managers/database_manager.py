import os
from typing import List
from managers.download_manager import DownloadManager
from services.base_services import BaseService
from utils import SystemInteract, Constants

class DatabaseManager:
    """Database manager for handling database drivers.

    Args:
        services:
            A list of services that need db drivers.
        dlm:
            A download manager.

    """
    
    def __init__(self, 
        services: List[BaseService],
        dlm: DownloadManager
    ):
        self.db_drivers = [
            Constants.MSSQL_DRIVER.value,
            Constants.POSTGRES_DRIVER.value,
            Constants.ORACLE_DRIVER.value
        ]
        self.services_with_db = services
        self.dlm = dlm
        self.sysi = SystemInteract()

    def _get_jar_name(self, url):
        return url.split('/')[-1]

    def _copy(self, source, destination):
        self.sysi.run(f'cp {source} {destination}')

    def _exists(self, driver):
        jar_file = self._get_jar_name(driver)
        exists_in_service = {}
        for service in self.services_with_db:
            for _, _, files in os.walk(f'{service.dir}'):
                if jar_file in files:
                    exists_in_service[service.abb] = True
            if service.abb not in exists_in_service:
                exists_in_service[service.abb] = False
        return exists_in_service

    def _cleanup(self, driver):
        self.sysi.remove(self._get_jar_name(driver))

    def _distribute_drivers(self, exists_dict):
        for service in self.services_with_db:
            if not self.sysi.path_exists(f'{service.dir}/drivers'):
                self.sysi.run(f'{service.dir}/drivers')
        for driver, exists in exists_dict.items():
            if not all(exists.values()):
                for service in self.services_with_db:
                    if not exists[service.abb]:
                        self._copy(self._get_jar_name(driver), f'{service.dir}/drivers')
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