for service in auth gateway idman nmap pki signer zone; do
    printf "Downloading ${service} setup files\n"
    git clone https://github.com/tomstark99/cenm-${service}.git --quiet
done
