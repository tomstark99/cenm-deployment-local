#!/bin/bash

download () {
	curl --progress-bar -u $1:$2 -O https://software.r3.com/artifactory/corda-gateway-plugins/com/r3/corda/node/management/plugin/auth-baseline-node-management-plugin/$3/auth-baseline-node-management-plugin-$3.jar || echo "Node management baseline plugin version ${3} not found."
	curl --progress-bar -u $1:$2 -O https://software.r3.com/artifactory/corda-gateway-plugins/com/r3/corda/flow/management/plugin/auth-baseline-flow-management-plugin/$3/auth-baseline-flow-management-plugin-$3.jar || echo "Flow management baseline plugin version ${3} not found."
	mv ./auth-baseline-*-management-plugin-$3.jar plugins
}

print_usage () {
cat << EOL
Dowload your node/flow management baseline plugin jars with: (use -o to overwrite existing plugin versions)
  ./dowload.sh -u <first>.<last>@r3.com -p <api_key> -v <version>
EOL
}

USERNAME=
PASSWORD=
VERSION=
OVERWRITE=

while getopts 'u:p:v:o' flag
do
	case "${flag}" in
		u)
            USERNAME=${OPTARG};;
		p) 
			PASSWORD=${OPTARG};;
		v)
			VERSION=${OPTARG};;
		o)
			OVERWRITE=true;;
		*)
			print_usage
			exit;;
	esac
done

if [ -z "$USERNAME" ] || [ -z "$PASSWORD" ] || [ -z "$VERSION" ]; then
	print_usage
	exit
fi

if [ "$OVERWRITE" = true ] ; then
	rm -rf plugins/auth-baseline-*-management-plugin-*.jar > /dev/null 2>&1
fi

echo "Downloading Node/Flow management baseline plugins v${VERSION}"

download "$USERNAME" "$PASSWORD" "$VERSION"
