if [ -z "$TUNNEL" ]; then
    TUNNEL='127.0.0.1:44022'
fi
#TODO: check if server is running and is reachable
script=$(curl -sm3 --data "{}" --request POST -H "Content-Type: application/json" "http://$TUNNEL/profile?pid=$$&shell=$0&domain=$USER@$HOSTNAME&tunnel=$TUNNEL")
eval "$script"
