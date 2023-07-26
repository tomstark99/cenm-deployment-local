import os
import sys
if f'{os.getcwd()}/.src' not in sys.path:
    sys.path.append(f'{os.getcwd()}/.src')
import argparse
import warnings
from typing import Dict
from managers.service_manager import ServiceManager

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
parser.add_argument(
    '--health-check-frequency',
    type=int,
    default=30,
    help='Time to wait between each health check, default is 30 seconds'
)
parser.add_argument(
    '--download-individual',
    type=str,
    help='Download individual artifacts, use a comma separated string of artifacts to download e.g. "pki-tool,identitymanager" to download the pki-tool and identitymanager artifacts'
)
parser.add_argument(
    '--clean-individual-artifacts',
    type=str,
    help='Clean individual artifacts, use a comma separated string of artifacts to download e.g. "pki-tool,identitymanager" to clean the pki-tool and identitymanager artifacts'
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

def validate_arguments(args: argparse.Namespace):
    # Check if only one of the clean flags are used
    clean_args = [args.clean, args.deep_clean, args.clean_artifacts, args.clean_certs]
    if sum(clean_args) > 1:
        raise ValueError("Cannot use more than one of the following flags: --clean, --deep-clean, --clean-artifacts, --clean-certs")
    # Check if no other arguments are used with --download-individual
    all_args = [args.setup_dir_structure, args.generate_certs, args.clean, args.clean_certs, args.clean_artifacts, args.deep_clean, args.run_default_deployment, args.version, (args.health_check_frequency != 30), (not args.download_individual), (not args.clean_individual_artifacts)]
    if args.download_individual and sum(all_args) > 1:
        raise ValueError("Cannot use --download-individual with any other flag")
    if args.download_individual == "":
        raise ValueError("Cannot use --download-individual without specifying artifacts to download")
    if args.clean_individual_artifacts and sum(all_args) > 1:
        raise ValueError("Cannot use --clean-individual-artifacts with any other flag")
    if args.clean_individual_artifacts == "":
        raise ValueError("Cannot use --clean-individual-artifacts without specifying artifacts to clean")
    if args.health_check_frequency != 30 and not args.run_default_deployment:
        warnings.warn("--health-check-frequency is not needed without --run-default-deployment")
    if args.health_check_frequency < 10:
        raise ValueError("Smallest value for --health-check-frequency is 10 seconds")

def main(args: argparse.Namespace):

    validate_arguments(args)

    service_manager = ServiceManager(
        username,
        password,
        auth_version,
        gateway_version,
        cenm_version,
        nms_visual_version,
        corda_version
    )

    if args.download_individual:
        services = [arg.strip() for arg in args.download_individual.split(',')]
        service_manager.download_specific(services)

    if args.clean_individual_artifacts:
        services = [arg.strip() for arg in args.clean_individual_artifacts.split(',')]
        service_manager.clean_specific_artifacts(services)

    service_manager.clean_all(
        args.deep_clean,
        args.clean_artifacts,
        args.clean_certs,
        args.clean
    )

    if args.setup_dir_structure:
        service_manager.download_all()

    if args.generate_certs:
        service_manager.generate_certificates()

    if args.run_default_deployment:
        service_manager.deploy_all(args.health_check_frequency)

if __name__ == '__main__':
    main(parser.parse_args())