#!/bin/bash -e
printf "Cloning deployment repo...\n"
git clone git@github.com:tomstark99/cenm-deployment-local.git --quiet
cat << EOL
To continue with the setup, edit your env file in cenm-deployment-local/.env

    $ mv .env.template .env
    $ vim .env
    
    1. ARTIFACTORY_USERNAME=<some>.<one>@r3.com
    2. ARTIFACTORY_API_KEY=<api_key>
    3. AUTH_VERSION=<auth_version>
    4. GATEWAY_VERSION=<gateway_version>
    5. CENM_VERSION=<cenm_version>
    6. NMS_VISUAL_VERSION=<nms_visual_version>

Once you are done with this, come back to this script and
EOL
read -p "press enter to continue"
(cd cenm-deployment-local && python3 setup_script.py --setup-dir-structure --generate-certs)

printf "Done\n"
exec rm ./install.sh >/dev/null 2>&1
