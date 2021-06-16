#!/bin/sh

TRACE_STATE='{{ STATE }}'
TUNNEL='{{ tunnel }}'
PS1TEMPLATE=$(echo '{{ PROMPT }}' | sed 's|{cwd}|\\w|g')
PS1="$PS1TEMPLATE"
PS2='| '

if [ "$0" = "sh" ] || [ "$0" = "dash" ]; then

    sh_update_prompt() {
        PS1=$(echo "$PS1TEMPLATE" | sed -e "s|\\\\w|$(pwd)|g" -e "s|$HOME|~|g")
    }

    wrapped_cd() {
        unalias cd
        cd $@ && sh_update_prompt
        alias cd=wrapped_cd
    }

    alias cd=wrapped_cd

    sh_update_prompt
fi

discovershell() {
    probe='echo $0 $PSVersionTable.PSEdition %OS%'
    response=$(ssh -M -o VisualHostKey=no -p "${1#*:}" -R"0:$TUNNEL" "${1%:*}" "$probe" 2>stderr.txt | tr -d '\n\r')
    tunnel_port=$(cat stderr.txt | grep Allocated | sed -r 's/.*Allocated port ([0-9]+).*/\1/')

    [ -z tunnel_port ] && cat stderr.txt && return 1

    test "${response#*.PSEdition}" != "$response" \
    && { test "${response#*\%OS\%}" != "$response" \
        && shell=${response% .PSEdition*} \
        || shell='cmd'; } \
    || { test "${response#*\%OS\%}" != "$response" \
        && shell='powershell' \
        || shell='unknown'; }

    echo "$shell,$tunnel_port"
}

getinitscript() {
    curl -m3 --data "$TRACE_STATE" --request POST -H "Content-Type: application/json" "http://$TUNNEL/bootstrap?shell=$1&tunnel=$2"
}

escArgv() {
    echo $1 | sed -re 's/(\\+)"/\1\1"/g' -e 's/"/\\"/g'
}

change-host() {
    sredg=$(discovershell "$1")
    remote_shell="${sredg%,*}"
    remote_port="${sredg#*,}"
    initcmd=$(getinitscript "$remote_shell" "127.0.0.1:$remote_port")
    echo "$(escArgv "$(escArgv "$initcmd")")"
    port="${1#*:}"
    ssh -t -p"$port" -o VisualHostKey=no -L"44044:127.0.0.1:$port" -R"$remote_port:$TUNNEL" "${1%:*}" "$(escArgv "$initcmd")"
}

alias ch=change-host

bash2() {
    initcmd=$(getinitscript bash "$TUNNEL")
    eval "$initcmd"
}

vscode() {
    curl -s "http://$TUNNEL/vscode?user=$USER&path=$PWD" >/dev/null;
}

dash() {
    initcmd=$(getinitscript sh "$TUNNEL")
    eval "$initcmd"
}

resettrace() {
    if [ -z "$TUNNEL" ]; then
        TUNNEL='127.0.0.1:44022'
    fi
    script=$(curl -sm3 --data "{}" --request POST -H "Content-Type: application/json" "http://$TUNNEL/p2?shell=bash&domain=$USER@$HOSTNAME&tunnel=$TUNNEL")
    eval "$script"
}
