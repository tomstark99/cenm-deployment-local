#!/bin/bash

download () {
	curl --progress-bar -u $1:$2 -O https://software.r3.com/artifactory/r3-corda-releases/com/r3/archive/archive-service/$3/archive-service-$3.jar || echo "Archive Service version ${3} not found."
	curl --progress-bar -u $1:$2 -O https://software.r3.com/artifactory/r3-corda-releases/com/r3/ledger-graph/$4/ledger-graph-$4.jar || echo "Ledger Graph version ${4} not found."
	mv ./archive-service-$3.jar ./cordapps/
	mv ./ledger-graph-$4.jar ./cordapps/
}

print_usage () {
cat << EOL
Dowload your Archiving and LedgerGraph jar(s) with: (use -o to overwrite existing plugin versions)
  ./dowload.sh -u <first>.<last>@r3.com -p <api_key> -a <archive_service_version> -l <ledger_graph_version>
EOL
}

USERNAME=
PASSWORD=
ARCHIVE_VERSION=
LG_VERSION=
OVERWRITE=

while getopts 'u:p:a:l:o' flag
do
	case "${flag}" in
		u)
            USERNAME=${OPTARG};;
		p) 
			PASSWORD=${OPTARG};;
		a)
			ARCHIVE_VERSION=${OPTARG};;
		l)
			LG_VERSION=${OPTARG};;
		o)
			OVERWRITE=true;;
		*)
			print_usage
			exit;;
	esac
done

if [ -z "$USERNAME" ] || [ -z "$PASSWORD" ] || [ -z "$ARCHIVE_VERSION" ] || [ -z "$LG_VERSION" ]; then
	print_usage
	exit
fi

if [ "$OVERWRITE" = true ]; then
	rm -rf cordapps/archive-service-*.jar > /dev/null 2>&1
	rm -rf cordapps/ledger-graph-*.jar > /dev/null 2>&1
fi

echo "Downloading Archive Service v${ARCHIVE_VERSION} and Ledger Graph v${LG_VERSION}..."

download "$USERNAME" "$PASSWORD" "$ARCHIVE_VERSION" "$LG_VERSION"
