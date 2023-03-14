# cenm-deployment-local

The host repo to tie in config repos, download artifacts and generate certs for CENM services.

## One line install

if you want to skip having to clone the repo manually and running the script yourself here is a one-line-installation script, you will be prompted to setup a `.env` file with your credentials and CENM versions. Then it will download all your artifacts and config files and run the certificate generation for your CENM services

```shell
/bin/bash -c "$(curl -fsSl https://raw.githubusercontent.com/tomstark99/cenm-deployment-local/HEAD/install.sh)"
```

## Getting started

Clone this repo locally:

```shell
git clone https://github.com/tomstark99/cenm-deployment-local.git
```

next, rename the `.env.template` file to `.env`, here you will fill in your credentials

```shell
cd cenm-deployment-local && mv .env.template .env
```

Now open the `.env` file and fill in the config options

```shell
ARTIFACTORY_USERNAME=<some>.<one>@r3.com
ARTIFACTORY_API_KEY=<api_key>
AUTH_VERSION=<auth_version>
GATEWAY_VERSION=<gateway_version>
CENM_VERSION=<cenm_version>
NMS_VISUAL_VERSION=<nms_visual_version>
CORDA_VERSION=<corda_version>
```

Once you have saved this file, you can run the python script with the following options

```
$ python3 setup_script.py -h
usage: setup_script.py [-h] [--setup-dir-structure] [--generate-certs]

Download CENM artifacts from Artifactory

options:
  -h, --help            show this help message and exit
  --setup-dir-structure
                        Create directory structure for CENM deployment and download all current artifacts
  --generate-certs      Generate certificates and distribute them to services
```

This command will download all the config files in the correct directories as well as download all the artifacts with the versions specified in `.env`:

```shell
python3 setup_script.py --setup-dir-structure --generate-certs
```
