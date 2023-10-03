# cenm-deployment-local

The host repo to tie in config repos, download artifacts and generate certs for CENM services.

## One line install

if you want to skip having to clone the repo manually and running the script yourself here is a one-line-installation script, you will be prompted to setup a `.env` file with your credentials and CENM versions. Then it will download all your artifacts and config files and run the certificate generation for your CENM services

```shell
/bin/bash -c "$(curl -fsSl https://raw.githubusercontent.com/tomstark99/cenm-deployment-local/HEAD/install.sh)"
```

You then skip to the [Deployment Order](#deployment-order) section

## One line auto-deployment

If you just need a default deployment of CENM then you can also skip having to run the manual commands in the [Deployment Order](#deployment-order) section. You can also run this command after making any config adjustments and adding plugins that need testing for example.

```shell
python3 setup_script.py --clean --run-default-deployment
```

This runs all the commands from the [Deployment Order](#deployment-order) section in python subprocesses, the python program won't exit until you shut down the CENM deployment with a `Ctrl+C`.

A health check runs on the subprocesses every 30 seconds and will restart services if they become unhealthy.

If you already have a CENM deployment you can omit the `--clean` flag and the deployment will run without running the initial registration steps.

## Getting started

Clone this repo locally:

```shell
git clone --branch=dev/tom https://github.com/tomstark99/cenm-deployment-local.git
```

next, rename the `.env.template` file to `.env`, here you will fill in your credentials

```shell
cd cenm-deployment-local && mv .env.template .env
```

Now open the `.env` file and fill in the config options (there are default versions already configured)

```shell
ARTIFACTORY_USERNAME=<some>.<one>@r3.com
ARTIFACTORY_API_KEY=<api_key>
AUTH_VERSION=<auth_version>
GATEWAY_VERSION=<gateway_version>
CENM_VERSION=<cenm_version>
NMS_VISUAL_VERSION=<nms_visual_version>
NOTARY_VERSION=<corda_version>
```

The `pyhocon` package is required for this script to work, install using

```shell
pip3 install pyhocon
```

Once you have saved this file, you can run the Python script with the following options.

```
$ python3 setup_script.py -h
usage: setup_script.py [-h]
                       [--setup-dir-structure]
                       [--download-individual DOWNLOAD_INDIVIDUAL]
                       [--generate-certs]
                       [--run-default-deployment]
                       [--clean-runtime]
                       [--clean-certs]
                       [--clean-artifacts]
                       [--deep-clean]
                       [--clean-individual-artifacts CLEAN_INDIVIDUAL_ARTIFACTS]
                       [--health-check-frequency HEALTH_CHECK_FREQUENCY]
                       [--validate]
                       [--version]

Download CENM artifacts from Artifactory

options:
  -h, --help            show this help message and exit
  --setup-dir-structure
                        Create directory structure for CENM deployment and download all current artifacts
  --download-individual DOWNLOAD_INDIVIDUAL
                        Download individual artifacts, use a comma separated string of artifacts to download e.g.
                        "pki-tool,identitymanager" to download the pki-tool and identitymanager artifacts
  --generate-certs      Generate certificates and distribute them to services
  --run-default-deployment
                        Runs a default deployment, following the steps from README
  --clean-runtime       Remove all generated runtime files
  --clean-certs         Remove all generated certificates
  --clean-artifacts     Remove all downloaded artifacts
  --deep-clean          Remove all generated service folders
  --clean-individual-artifacts CLEAN_INDIVIDUAL_ARTIFACTS
                        Clean individual artifacts, use a comma separated string of artifacts to download e.g.
                        "pki-tool,identitymanager" to clean the pki-tool and identitymanager artifacts
  --health-check-frequency HEALTH_CHECK_FREQUENCY
                        Time to wait between each health check, default is 30 seconds
  --validate            Check which artifacts are present
  --version             Show current cenm version
```

The following command will download all the config files in the correct directories as well as download all the artifacts with the versions specified in `.env`:

```shell
python3 setup_script.py --setup-dir-structure --generate-certs
```

## Deployment Order

CENM services should be deployed in a particular order, this being:

1. If you have not previously run the python scirpt with the `--generate-certs` flag then do this now
    
    ```shell
    python3 setup_script.py --generate-certs
    ```
    
    This will run the pki tool and copy the generated certificates into the correct locations for each service
    
2. Start the identity manager

    ```shell
    java -jar identitymanager.jar -f identitymanager.conf
    ```
    
3. Start the signer service

    ```shell
    java -jar signer.jar -f signer.conf
    ```
    
4. Register the notary

    ```shell
    java -jar corda.jar \
        -f notary.conf
        --initial-registration \
        --network-root-truststore ./certificates/network-root-truststore.jks \
        --network-root-truststore-password trustpass
    ```
    
    _Note: There is currently a known issue (https://github.com/tomstark99/cenm-deployment-local/issues/5) where corda versions outside of `4.10` might cause exceptions during registration._
    
5. Update the `networkparameters.conf` file with the correct nodeInfo

    When the notary is registered with the network it generates a `nodeInfo-XXXXX...` file. The name of this file needs to replace the `INSERT_NODE_INFO_FILE_NAME_HERE` placeholder in the `cenm-nmap/networkparameters.conf` file e.g.
    
    ```properties
    notaries : [
        {
            notaryNodeInfoFile: "nodeInfo-DFD4D403F65EA6C9B33B653A8B855CB3C4F04D599B373E662EBD2146241219F2"
            validating = false
        }
    ]

    minimumPlatformVersion = 4
    maxMessageSize = 10485760
    maxTransactionSize = 10485760
    eventHorizonDays = 10 # Duration in days
    ```
    
    The `nodeInfo-XXXXX...` file should also be copied to the `cenm-nmap/` folder
    
    ```shell
    cp cenm-notary/nodeInfo-* cenm-nmap/
    ```
    
6. Set network parameters

    ```shell
    java -jar networkmap.jar \
        -f networkmap.conf \
        --set-network-parameters networkparameters.conf \
        --network-truststore ./certificates/network-root-truststore.jks \
        --truststore-password trustpass \
        --root-alias cordarootca
    ```
    
7. Start the network map

    ```shell
    java -jar networkmap.jar -f networkmap.conf
    ```
    
8. Start the notary

    ```shell
    java -jar corda.jar -f notary.conf
    ```
    
    _Note: you may have to wait while the network parameters that were set in step 5 are signed, this can take a few minutes._

9. Start the auth service

    ```shell
    java -jar accounts-application.jar \
        -f ./auth.conf \
        --initial-user-name admin \
        --initial-user-password p4ssWord \
        --keep-running \
        --verbose
    ```
    
10. Start the private and public gateway services

    ```shell
    java -jar gateway-service.jar -f private.conf
    java -jar gateway-service.jar -f public.conf
    ```
    
11. Start the zone service

    ```shell
    java -jar zone.jar \
        --driver-class-name=org.h2.Driver \
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
        --auth-issuer "http://test" \
        --auth-leeway 5 \
        --tls=true \
        --tls-keystore=certificates/corda-ssl-identity-manager-keys.jks \
        --tls-keystore-password=password \
        --tls-truststore=certificates/corda-ssl-trust-store.jks \
        --tls-truststore-password=trustpass
    ```

12. Verify your gateway is up by navigating to http://localhost:8089

13. Run setupAuth initially to create users in the global zone:

    ```shell
    cd cenm-auth/setup-auth
    bash setupAuth.sh
    ```

    _Note: this script requires [jq](https://stedolan.github.io/jq/download/), a command line JSON processor that can be installed easily in various ways._

14. Create a 'Main' subzone

    Navigate to the cenm-tool directory

    ```shell
    cd cenm-gateway/cenm-tool
    ```

    First set your global zone config for identity manager and network map:

    ```shell
    ./cenm context login -s http://127.0.0.1:8089 -u config-maintainer -p <password>
    ./cenm identity-manager config set-admin-address -a=127.0.0.1:5053
    ./cenm identity-manager config set -f=identitymanager.conf --zone-token
    ./cenm netmap config set-admin-address -a=127.0.0.1:5053
    ./cenm context logout http://127.0.0.1:8089
    ```

    To create a subzone, you need the `network-maintainer` login:

    ```shell
    ./cenm context login -s http://127.0.0.1:8089 -u network-maintainer -p <password>
    ./cenm zone create-subzone \
        --config-file=../../cenm-nmap/networkmap.conf \
        --network-map-address=127.0.0.1:20000 \
        --network-parameters=../../cenm-nmap/networkparameters.conf \
        --label=Main \
        --label-color='#941213' \
        --zone-token
    ./cenm context logout http://127.0.0.1:8089
    ```

    Make a note of the zone tokens that are returned in case you need it later (for example if you are using the angel service).

    Next set your signer config globally:

    ```shell
    ./cenm context login -s http://127.0.0.1:8089 -u config-maintainer -p <password>
    ./cenm signer config set-admin-address -a=127.0.0.1:5054
    ./cenm signer config set -f=signer.conf
    ```

    Get your subzone id:

    ```shell
    ./cenm zone get-subzones
    ```

    Set your network map config for the subzone and replace the `<SUBZONE_ID>` with the id returned from:

    ```shell
    ./cenm netmap config set -s <SUBZONE_ID> -f=networkmap.conf
    ./cenm context logout http://127.0.0.1:8089
    ```

<!-- 15. Set your zone config

    Set the 'Main' zone config to be the same as the global zone, for this you will need the `config-maintainer` login

    ```shell
    ./cenm context login -s http://127.0.0.1:8089 -u config-maintainer -p <password>
    ./cenm identity-manager config set \
        --config-file=../../cenm-idman/identitymanager.conf \
        --zone-token
    ./cenm signer config set \
        --config-file=../../cenm-signer/signer.conf \
        --zone-token
    ```

    Again, make a note of the zone token that is returned in case you need it later (for example if you are using the angel service) -->
    
15. To grant your users access to the new subzone, replace the `<SUBZONE_ID>` with the id returned from

    ```shell
    ./cenm context login -s http://127.0.0.1:8089 -u config-maintainer -p <password>
    ./cenm zone get-subzones
    ```

    The user roles are located in the cenm-auth directory, in the example below the zone id is `1` which should be substituted `"s//<here>/g"` in the `perl` command

    ```shell
    cd cenm-auth/setup-auth/roles
    for file in *.json; do perl -i -pe "s/<SUBZONE_ID>/1/g" $file; done
    ```

    After this run setupAuth again:

    ```shell
    setupAuth.sh
    ```

    _Note: this script requires [jq](https://stedolan.github.io/jq/download/), a command line JSON processor that can be installed easily in various ways._
    

