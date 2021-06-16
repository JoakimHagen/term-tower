export TRACE_STATE='{{ STATE }}';
export TUNNEL='{{ tunnel }}';

getprofile() {
    curl -s --data "$TRACE_STATE" --request POST -H "Content-Type: application/json" "http://{{ tunnel }}/p2?shell={{ shell }}&domain=$USER@$HOSTNAME&tunnel={{ tunnel }}";
}

#od -bc $tmpfile | head
#cat $tmpfile

{{ command }}

#curl --data '{}' --request POST -H "Content-Type: application/json" "http://172.19.160.1:44022/p2?shell=bash\&domain=$USER@$HOSTNAME\&tunnel=172.19.160.1:44022";

#curl -m 2 "http://172.19.160.1:44022/"