
def is_supported(server, language):
    return language in ['sh', 'dash', 'bash', 'zsh', 'ksh']

def start_shell(server, language):
    return language + " --rcfile {{ profile.file }} -i"

def get_bootstrap(server, language):
    
    _bootstrap_shell = \
    """
export TRACE_STATE='{{ STATE }}';
export TUNNEL='{{ tunnel }}';

getprofile() {
    curl -s --data "$TRACE_STATE" --request POST -H "Content-Type: application/json" "{{ profile_url }}";
}
    """

    url = server.get_profile_url(domain='$USER@$HOSTNAME')
    return _bootstrap_shell.replace("{{ profile_url }}", url)

def refer_argument_script(server, language):
    return "$(getprofile)"

def create_temp_file(server, language):
    return f"tempfile=$(mktemp /tmp/{language}rc-XXXXXX); getprofile > $tempfile;"

def refer_temp_file(server, language):
    return "$tempfile"

def delete_temp_file(server, language):
    return "rm $tempfile;"

def get_profile(server, language):
    return server.get_file("posix/profile.sh")
