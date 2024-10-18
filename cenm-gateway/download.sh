#!/bin/bash

download () {
	curl --progress-bar -u $1:$2 -O https://software.r3.com/artifactory/corda-gateway-plugins/com/r3/corda/node/management/plugin/node-management-plugin/$3/node-management-plugin-$3.jar || echo "Node management gateway plugin version ${3} not found."
	curl --progress-bar -u $1:$2 -O https://software.r3.com/artifactory/corda-gateway-plugins/com/r3/corda/flow/management/plugin/flow-management-plugin/$3/flow-management-plugin-$3.jar || echo "Flow management gateway plugin version ${3} not found."
	cp ./*-management-plugin-$3.jar public/plugins
	mv ./*-management-plugin-$3.jar private/plugins
}

print_usage () {
cat << EOL
Dowload your node/flow management gateway plugin jars with: (use -o to overwrite existing plugin versions)
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
	rm -rf public/plugins/*-management-plugin-*.jar > /dev/null 2>&1
	rm -rf private/plugins/*-management-plugin-*.jar > /dev/null 2>&1
fi

echo "Downloading Node/Flow management gateway plugins v${VERSION}"

download "$USERNAME" "$PASSWORD" "$VERSION"
