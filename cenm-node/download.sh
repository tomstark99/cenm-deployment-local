#!/bin/bash

download () {
	curl --progress-bar -u $1:$2 -O https://software.r3.com/artifactory/r3-corda-releases/com/r3/corda/corda/$3/corda-$3.jar || echo "Corda version ${3} not found."
	curl --progress-bar -u $1:$2 -O https://software.r3.com/artifactory/r3-corda-releases/com/r3/corda/corda-shell/$3/corda-shell-$3.jar || echo "Corda shell version ${3} not found."
	mv ./corda-shell-$3.jar ./drivers/
	curl --progress-bar -u $1:$2 -O https://software.r3.com/artifactory/corda-releases/net/corda/corda-finance-contracts/$3/corda-finance-contracts-$3.jar || echo "Corda finance contracts version ${3} not found."
	curl --progress-bar -u $1:$2 -O https://software.r3.com/artifactory/corda-releases/net/corda/corda-finance-workflows/$3/corda-finance-workflows-$3.jar || echo "Corda finance workflows version ${3} not found."
	mv ./corda-finance-*-$3.jar ./cordapps/
}

print_usage () {
cat << EOL
Dowload your Corda jar with: (use -o to overwrite existing plugin versions)
  ./dowload.sh -u <first>.<last>@r3.com -p <api_key> -v <corda_version>
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

if [ "$OVERWRITE" = true ]; then
	rm -rf corda-*.jar > /dev/null 2>&1
	rm -rf drivers/corda-shell-*.jar > /dev/null 2>&1
	rm -rf cordapps/corda-finance-*-*.jar > /dev/null 2>&1
fi

echo "Downloading Corda v${VERSION}"

download "$USERNAME" "$PASSWORD" "$VERSION"
