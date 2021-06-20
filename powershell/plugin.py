
def is_supported(server, language):
    return language == 'powershell'

def start_shell(server, language):
    return "powershell -Command {{ profile.content }}"

def get_bootstrap(server, language):
    
    _bootstrap_shell = \
    """
$env:TRACE_STATE = '{{ STATE }}';
$env:TUNNEL = '{{ tunnel }}';
function EscArgv { $args -Replace '\\(?=\\*")','\\' -Replace '"','\"' }
function Get-Profile {
    Invoke-WebRequest -Uri "{{ profile_url }}" -Body '{{ STATE }}' -Method POST -ContentType 'application/json' | Select-Object -Expand Content;
}
    """

    url = server.get_profile_url(domain='$Env:UserName@$Env:ComputerName')
    return _bootstrap_shell.replace("{{ profile_url }}", url)

def refer_argument_script(server, language):
    return "(Get-Profile)"

def create_temp_file(server, language):
    return "$tempfile = New-TemporaryFile; Get-Profile | Out-File $tempfile;"

def refer_temp_file(server, language):
    return "$tempfile"

def delete_temp_file(server, language):
    return "Remove-Item $tempfile;"

def get_profile(server, language):
    return server.get_file("powershell/profile.ps1")

