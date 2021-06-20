#!/bin/sh

TRACE_STATE='{{ STATE }}'
TUNNEL='{{ tunnel }}'
PS1TEMPLATE=$(echo '{{ PROMPT }}' | sed 's|{cwd}|\\w|g')
PS1="$PS1TEMPLATE"
PS2='| '

TRACE_STATE=$(echo "$TRACE_STATE" | sed s/-1/$$/)

if [ "$0" = "sh" ] || [ "$0" = "dash" ] || [ "$0" = "/bin/sh" ] || [ "$0" = "/bin/dash" ]; then

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
    curl -sm3 --data "$TRACE_STATE" --request POST -H "Content-Type: application/json" "http://$TUNNEL/bootstrap?shell=$1&tunnel=$2"
}

escArgv() {
    echo $1 | sed -re 's/(\\+)"/\1\1"/g' -e 's/"/\\"/g'
}

changehost() {
    sredg=$(discovershell "$1")
    remote_shell="${sredg%,*}"
    remote_port="${sredg#*,}"
    initcmd=$(getinitscript "$remote_shell" "127.0.0.1:$remote_port")
    echo "$(escArgv "$(escArgv "$initcmd")")"
    port="${1#*:}"
    ssh -t -p"$port" -o VisualHostKey=no -L"44044:127.0.0.1:$port" -R"$remote_port:$TUNNEL" "${1%:*}" "$(escArgv "$initcmd")"
}

alias ch=changehost

changeshell() {
    initcmd=$(getinitscript "$1" "$TUNNEL")
    eval "$initcmd"
}

# if command exist, override with alias
command -v bash 1>/dev/null && alias bash="changeshell bash";
command -v sh 1>/dev/null   && alias sh="changeshell sh";
command -v dash 1>/dev/null && alias dash="changeshell dash";
command -v zsh 1>/dev/null  && alias zsh="changeshell zsh";
command -v ksh 1>/dev/null  && alias ksh="changeshell ksh";

vscode() {
    curl -s "http://$TUNNEL/vscode?user=$USER&path=$PWD" >/dev/null;
}
