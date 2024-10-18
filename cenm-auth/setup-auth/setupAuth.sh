# log in and cache access token
TOKEN_RESPONSE="$(curl -X POST --data "grant_type=password" --data "username=admin" \
    --data "password=p4ssWord" http://127.0.0.1:8089/api/v1/authentication/authenticate --raw | sed -n 2p)"
ACCESS_TOKEN="$(echo ${TOKEN_RESPONSE} | jq -r '.access_token')"
echo "access-token=${ACCESS_TOKEN}"

echo
echo "========================= Creating users ========================="
for filename in ./users/*.json; do
 echo "Creating user $filename."
 curl -X POST -H "Authorization: Bearer $ACCESS_TOKEN" -H "Content-Type: application/json" \
    --data-binary "@$filename" http://127.0.0.1:8089/api/v1/admin/users
 echo ""
done

echo
echo "========================= Creating groups ========================="
for filename in ./groups/*.json; do
 echo "Creating group ${filename}."
 curl -X POST -H "Authorization: Bearer $ACCESS_TOKEN" -H "Content-Type: application/json" \
    --data-binary "@$filename" http://127.0.0.1:8089/api/v1/admin/groups
 echo ""
done

echo
echo "========================= Assigning roles to groups ========================="
for role in "CASigner" "ConfigurationMaintainer" "ConfigurationReader" "NetworkMaintainer" "NetworkOperator" "NetworkOperationsReader" "NonCASigner"; do
 echo "Assigning role ${role} to groups."
 srcFile='./roles/'$role'.json'
 tempFile=$srcFile'-tmp'
 sed "s/<SUBZONE_ID>/$1/g" $srcFile > $tempFile
 curl -X PATCH -H "Authorization: Bearer $ACCESS_TOKEN" -H "Content-Type: application/merge-patch+json" \
      --data-binary "@$tempFile" http://127.0.0.1:8089/api/v1/admin/roles/$role
 echo ""
 rm "$tempFile"
done

# for srcFile in ./roles/*.json; do
#  echo "Creating role from file ${srcFile} and assigning it to groups."
#  tempFile=$srcFile'-tmp'
#  sed -i '' "s/<SUBZONE_ID>/$1/g" $srcFile > $tempFile
#  curl -X POST -H "Authorization: Bearer $ACCESS_TOKEN" -H "Content-Type: application/json" \
#       --data-binary "@$tempFile" http://127.0.0.1:8089/api/v1/admin/roles
#  echo ""
#  rm "$tempFile"
# done


# log in and cache access token
# ACCESS_TOKEN=""
# while [ -z "${ACCESS_TOKEN}" ]
# do
#     TOKEN_RESPONSE="$(curl -X POST --data "grant_type=password" --data "username=admin" --data "password=p4ssWord" http://127.0.0.1:8089/api/v1/authentication/authenticate)"
#     ACCESS_TOKEN="$(echo ${TOKEN_RESPONSE} | jq -r '.access_token')"
#     sleep 5
# done

# pwd
# ls -alR

# echo
# echo "========================= Creating users ========================="
# for i in users/*.json
# do
#     echo
#     echo ">>>>>>>> User: ${i}"
#     cat ${i}; echo
#     curl -X POST -H "Authorization: Bearer $ACCESS_TOKEN" -H "Content-Type: application/json" --data-binary "@${i}" http://127.0.0.1:8089/api/v1/admin/users
#     echo
# done

# echo
# echo "========================= Creating groups ========================="
# for i in groups/*.json
# do
#     echo
#     echo ">>>>>>>> Group: ${i}"
#     cat ${i}; echo
#     curl -X POST -H "Authorization: Bearer $ACCESS_TOKEN" -H "Content-Type: application/json" --data-binary "@${i}" http://127.0.0.1:8089/api/v1/admin/groups
#     echo
# done

# echo
# echo "========================= Assigning roles to groups ========================="
# for role in "CASigner" "ConfigurationMaintainer" "ConfigurationReader" "NetworkMaintainer" "NetworkOperator" "NetworkOperationsReader" "NonCASigner"; do
#  file='./roles/'$role'.json'
#  echo
#  echo ">>>>>>>> Role: ${file}"
#  cat ${file}; echo
#  curl -X PATCH -H "Authorization: Bearer $ACCESS_TOKEN" -H "Content-Type: application/merge-patch+json" --data-binary "@${file}" http://127.0.0.1:8089/api/v1/admin/roles/${role}
#  echo
# done
