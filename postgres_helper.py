import os
import sys
if f'{os.getcwd()}/.src' not in sys.path:
    sys.path.append(f'{os.getcwd()}/.src')
try:
    from pyhocon import ConfigFactory
except ImportError:
    raise ImportError("""

Your python installation is missing the:
    pyhocon

package which is required for this script to run. Please install it using:
    pip install pyhocon""")
import argparse
import glob
import multiprocessing
from pathlib import Path
from typing import Dict
from time import sleep
from abc import ABC, abstractmethod
from utils import SystemInteract, Logger


parser = argparse.ArgumentParser(description='A helper script to run a minikube postgres deployment')
parser.add_argument(
    'database_name',
    type=str,
    help='database name'
)
parser.add_argument(
    'node_directory',
    type=Path,
    help='Path to node which will use the database'
)
parser.add_argument(
    'sql_script',
    type=Path,
    help='Path to sql script'
)

logger = Logger().get_logger(__name__)

class PostgresService(ABC):

    def __init__(self, database_name: str):
        self.database_name = database_name
        self.sysi = SystemInteract()

    @abstractmethod
    def deploy(self):
        pass

class PostgresInstance(PostgresService):

    def __init__(self, database_name: str, sql_script: Path):
        super().__init__(database_name)
        self.sql_script = sql_script

    def _wait_for_pod(self):
        status = "init"
        while "running" not in status:
            sleep(15)
            status = self.sysi.run_get_stdout(f'kubectl get pods -l app.kubernetes.io/instance={self.database_name}'+' -o jsonpath="{.items[*].status.containerStatuses[-1:].state}"')
            logger.info(f"Waiting for pod, current status is: {'init' if not status else status}")
        logger.info("Sleeping for 10 seconds to allow the pod start fully")
        sleep(10)

    def _deploy_helm_chart(self):
        logger.info("Deploying postgres helm chart: 'helm install notary-database bitnami/postgresql'")
        self.sysi.run("helm install notary-database bitnami/postgresql", silent=True)
        self._wait_for_pod()

    def deploy(self):
        logger.info("Thread started to deploy postgres instance")
        try:
            self._deploy_helm_chart()
        except Exception as e:
            logger.info(f"Instance deployment interrupted")
            raise RuntimeError(f"Instance deployment interrupted: {e}")

    def setup_postgres_environment(self):
        logger.info("Setting up postgres environment")
        try:
            self.sysi.run('export POSTGRES_PASSWORD=$(kubectl get secret --namespace default notary-database-postgresql -o jsonpath="{.data.postgres-password}" | base64 -d)')
            self.password = self.sysi.run_get_stdout(f'kubectl get secret --namespace default {self.database_name}-postgresql'+' -o jsonpath="{.data.postgres-password}" | base64 -d')
            self.sysi.run(f'PGPASSWORD="{self.password}" psql --host 127.0.0.1 -U postgres -d postgres -p 5432 < {self.sql_script}', silent=True)
        except Exception as e:
            logger.info(f"Postgres environment setup interrupted")
            raise RuntimeError(f'Postgres environment setup interrupted: {e}')


class PostgresPortForward(PostgresService):

    # not in use
    def get_multiprocessing_process(self):
        return multiprocessing.Process(target=self.deploy, name="postgres_port_forward", daemon=True)

    def deploy(self):
        logger.info("Thread started to deploy postgres port forward")
        while True:
            try:
                logger.info(f"Running: kubectl port-forward --namespace default svc/{self.database_name}-postgresql 5432:5432")
                self.sysi.run(f'kubectl port-forward --namespace default svc/{self.database_name}-postgresql 5432:5432', silent=True)
            except Exception as e:
                logger.info(f"Port forward interrupted: {e}. Restarting...")

class PostgresManager:

    def __init__(self, database_name: str, node_directory: Path, sql_script: Path):
        self.database_name = database_name
        self.node_directory = node_directory
        self.sql_script = sql_script
        self.sysi = SystemInteract()
        self.postgres_instance = PostgresInstance(database_name, sql_script)
        self.postgres_port_forward = PostgresPortForward(database_name)
        self.processes = []

    def _is_running(self) -> bool:
        return self.sysi.run_get_exit_code('minikube status | grep -i "host: Running"', silent=True) == 0

    def _wait_for_service_termination(self):
        pass

    def _set_node_branch(self):
        try:
            logger.info("Setting node branch to release/postgres")
            self.sysi.run(f'(cd {self.node_directory} && git checkout release/postgres)', silent=True)
        except Exception as e:
            raise RuntimeError(f"Node branch could not be set: {e}")

    def _validate_node_config(self):
        try:
            logger.info("Validating node config")
            if len(glob.glob(f"{self.node_directory}/*.conf")) != 1:
                raise RuntimeError("Node config could not be found or is not unique")
            config_file = glob.glob(f"{self.node_directory}/*.conf")[0]
            config = ConfigFactory.parse_file(config_file)
            if config.dataSourceProperties.dataSource.url != 'jdbc:postgresql://127.0.0.1:5432/postgres':
                raise RuntimeError("Node config does not match the database name")
            if config.dataSourceProperties.dataSourceClassName != 'org.postgresql.ds.PGSimpleDataSource':
                raise RuntimeError("Node config does not match correct database driver")
            if not glob.glob(f'{self.node_directory}/drivers/postgresql*.jar'):
                raise RuntimeError("Node directory does not have the database drivers required")
        except Exception as e:
            raise RuntimeError(f"Node config could not be parsed: {e}")

    def start_minikube_cluster(self):
        if self._is_running():
            raise RuntimeError("Minikube cluster is already running, this script will not use an existing cluster")
        try:
            logger.info("Running: minikube start --nodes 1 --memory 2048 --cpus 2")
            self.sysi.run('minikube start --nodes 1 --memory 2048 --cpus 2')
        except Exception as e:
            logger.error(f"Minikube cluster could not be started: {e}")
            self.stop_cluster_and_cleanup()
            raise RuntimeError("Minikube cluster could not be started")

    def deploy_postgres(self, health_check_frequency: int):
        self._set_node_branch()
        self._validate_node_config()
        self.start_minikube_cluster()
        if not self._is_running():
            raise RuntimeError("Minikube cluster is not running, please start it and try again")
        try:
            logger.info("Starting the postgres deployment")
            postgres_process = multiprocessing.Process(target=self.postgres_instance.deploy, name="postgres_instance", daemon=True)
            postgres_process.start()
            postgres_process.join()
            postgres_portforward_process = multiprocessing.Process(target=self.postgres_port_forward.deploy, name="postgres_port_forward", daemon=True)
            self.processes.append(postgres_portforward_process)
            postgres_portforward_process.start()

            logger.info("Sleeping for 10 seconds to allow ports to forward")
            sleep(10)
            self.postgres_instance.setup_postgres_environment()
            logger.info("Postgres database running, starting health check")

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
                        new_process = multiprocessing.Process(target=self.postgres_port_forward.deploy, name="postgres_port_forward", daemon=True)
                        new_process.start()
                        self.processes.append(new_process)
                sleep(health_check_frequency)

        # In theory nothing should go wrong during deployment but if it does we want to clean up
        # Generally catching BaseException is not great.
        except BaseException:
            logger.info("Postgres deployment interrupted, cleaning up")
            for process in self.processes:
                logger.info(f'Terminating {process}')
                process.terminate()
                logger.info(f'Waiting for {process} to exit gracefully')
                process.join()
            self._wait_for_service_termination()
            self.stop_cluster_and_cleanup()
            logger.info("Done cleaned up")
            exit(1)

    def stop_cluster_and_cleanup(self):
        logger.info("Running: minikube stop")
        self.sysi.run('minikube stop')
        logger.info("Running: minikube delete")
        self.sysi.run('minikube delete')

            
def validate_arguments(args: argparse.Namespace):
    if SystemInteract().run_get_exit_code("minikube --help", silent=True) != 0:
        raise RuntimeError("minikube is not installed in your shell, please install it and try again")

def main(args: argparse.Namespace):

    validate_arguments(args)
    postgres_manager = PostgresManager(
        args.database_name, 
        args.node_directory, 
        args.sql_script
    )

    postgres_manager.deploy_postgres(health_check_frequency=30)


if __name__ == '__main__':
    main(parser.parse_args())