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
NOTARY_VERSION=<corda_version>
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

## Deployment Order

CENM services should be deployed in a particular order, this being:

1. Run the pki-tool (this can be run with the python scripts by specifying `--generate-certs`
    
    ```shell
    java -jar pkitool.jar -f pki.conf
    ```
    
2. Start the identity manager

    ```shell
    java -jar identitymanager.jar -f identitymanager.conf
    ````
    
3. Start the signer service

    ```shell
    java -jar signer.jar -f signer.conf
    ````
    
4. Register the notary

    ```shell
    java -jar corda.jar \
        --initial-registration \
        --network-root-truststore ./certificates/network-root-truststore.jks \
        --network-root-truststore-password trustpass
    ````
    
5. Set network parameters

    ```shell
    java -jar networkmap.jar \
        -f networkmap.conf \
        --set-network-parameters networkparameters.conf \
        --network-truststore ./certificates/network-root-truststore.jks \
        --truststore-password trustpass \
        --root-alias cordarootca
    ````
    
6. Start the network map

    ```shell
    java -jar networkmap.jar -f networkmap.conf
    ````
    
7. Start the notary

    ```shell
    java -jar corda.jar -f notary.conf
    ````

8. Start the auth service

    ```shell
    java -jar accounts-application.jar \
        -f ./auth.conf \
        --initial-user-name admin \
        --initial-user-password p4ssWord \
        --keep-running \
        --verbose
    ````
    
9. Start the private and public gateway services

    ```shell
    java -jar gateway-service.jar -f private.conf
    java -jar gateway-service.jar -f public.conf
    ````
    
10. Start the zone service

    ```shell
    java -jar zone.jar \
        --driver-class-name=org.h2.Driver\
        --jdbc-driver= \
        --user=zoneuser \
        --password=password \
        --url='jdbc:h2:file:./h2/zone-persistence;DB_CLOSE_ON_EXIT=FALSE;LOCK_TIMEOUT=10000;WRITE_DELAY=0;AUTO_SERVER_PORT=0' \
        --run-migration=true \
        --enm-listener-port=5061 \
        --admin-listener-port=5063 \
        --auth-host=127.0.0.1 \
        --auth-port=8081 \
        --auth-trust-store-location certificates/corda-ssl-trust-store.jks \
        --auth-trust-store-password trustpass \
        --auth-issuer test \
        --auth-leeway 5 \
        --tls=true \
        --tls-keystore=certificates/corda-ssl-identity-manager-keys.jks \
        --tls-keystore-password=password \
        --tls-truststore=certificates/corda-ssl-trust-store.jks \
        --tls-truststore-password=trustpass
    ````
    
11. Run the `setupAuth.sh` script to add users to the auth service
    
    ```shell
    setupAuth.sh
    ```
    
12. Verify your gateway is up by navigating to http://localhost:8089
