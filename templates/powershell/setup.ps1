
# These environment-variables are substituted by the server
$TRACE_STATE = '{{ STATE }}'
$env:TUNNEL = '{{ tunnel }}'
$prompt_template = '{{ PROMPT }}'

echo "state: $TRACE_STATE"
echo "tunnel: $env:TUNNEL"
echo "template: $prompt_template"

function prompt { $prompt_template -Replace '\{cwd\}',(Get-Location) }

function Template ([string]$str) {
    foreach ($block in [regex]::Matches($str,'\{\{(.?[^\}])*\}\}') | Select-Object -ExpandProperty Value)
    {
        $out = Invoke-Expression ($block -Replace '^\{\{ *' -Replace ' *\}\}$')
        $str = $str.Replace($block, [string]$out)
    }
    return $str
}

function setprompt($template) {
    if ($null -Ne $template) {
        $template = [System.Web.HTTPUtility]::UrlEncode($template)
    }
    $prompt_template = Invoke-WebRequest -Uri "http://$env:TUNNEL/prompt?template=$template" -Body $TRACE_STATE -Method POST -ContentType 'application/json' | Select-Object -Expand Content;
}

# Escape Arguments Vector, used to preserve strings passed as command arguments
function EscArgv { $args -Replace '\\(?=\\*")','\\' -Replace '"','\"' }

function Split-Target([string]$Target) {
    $domain, $port = $Target.Split(':')
    if ($null -Eq $port) { $port = '22' }
    return $domain, $port
}

function DiscoverShell ([string]$Target) {
    $domain, $port = Split-Target $Target
    
    # all the following shells support 'echo'
    # unix shells will replace the $0 with their command-name
    # windows powershell will replace $PSVersionTable.PSEdition with its edition name
    # windows cmd will replace %OS% with the OS version
    # we can determine the shell type by looking at the response
    $probe = 'echo $0 $PSVersionTable.PSEdition %OS%'
    $response = (ssh -o VisualHostKey=no -p $port -R"0:$env:TUNNEL" $domain $probe) 2>stderr.txt

    $allocated_port = (Get-Content stderr.txt -Raw) | Select-String -Pattern 'Allocated port (\d+)'
    if ($null -Eq $allocated_port.Matches) {
        Write-Error -Message (Get-Content stderr.txt -Raw) -ErrorAction Stop
    }

    $remote_tunnel = $allocated_port.Matches[0].Groups[1].Value

    if ($response.Indexof('.PSEdition') -Ne -1) {
        if ($response.Indexof('%OS%') -Ne -1) {
            # most likely unix shell
            # improvement: If unix shell has $PSVersionTable defined, containing spaces, this fails
            $shell = $response -Replace ' [^ ]*\.PSEdition.*'
        }
        else {
            # most likely cmd
            #$os = $response -Replace '.*PSEdition '
            $shell = 'cmd'
        }
    }
    elseif ($response.Indexof('%OS%') -Ne -1) {
        # most likely powershell
        $shell = 'powershell'
    }
    else {
        $shell = 'unknown'
    }
    return $shell, $remote_tunnel
}

function Get-BootstrapScript ($Shell, $Tunnel, $Command) {

    Add-Type -AssemblyName System.Web
    $urlsafe_shell = [System.Web.HTTPUtility]::UrlEncode($Shell)

    $uri = "http://$env:TUNNEL/bootstrap?shell=$urlsafe_shell&tunnel=$Tunnel"

    if ($null -Ne $Command) {
        $Command = [System.Web.HTTPUtility]::UrlEncode($Command)
        $uri += "&command=$Command"
    }

    if ($null -Eq $TRACE_STATE) {
        $TRACE_STATE = "{}"
    }

    $bootscript = Invoke-WebRequest -Uri $uri -Body $TRACE_STATE -Method POST -ContentType 'application/json' | Select-Object -Expand Content
    return $bootscript
}

function ChangeHost ($Target, $Command) {
    $domain, $port = Split-Target $Target

    $shell, $remote_tunnel_port = DiscoverShell $Target
    $bootstrap = Get-BootstrapScript -Shell $shell -Tunnel "127.0.0.1:$remote_tunnel_port" -Command $Command

    ssh -t -p"$port" -o VisualHostKey=no -L"44044:127.0.0.1:$port" -R"$remote_tunnel_port`:$env:TUNNEL" $domain (EscArgv (EscArgv $bootstrap))
}

Set-Alias -Name ch -Value ChangeHost

function Reset-Trace () {
    if ($null -Eq $env:TUNNEL) {
        $env:TUNNEL = '127.0.0.1:44022'
    }
    $script = Invoke-WebRequest -Uri "http://$env:TUNNEL/p2?shell=powershell&domain=$Env:UserName@$Env:ComputerName&tunnel=$env:TUNNEL" -Body '{}' -Method POST -ContentType 'application/json' | Select-Object -Expand Content;
    Invoke-Command -NoNewScope ([ScriptBlock]::Create($script));
}

if (Test-Path C:\Windows\system32\bash.exe) {
    function bash {
        # Get the IP address allocated to this host from within WSL
        # $wslAdr = (wsl -- ip address show eth0 | Select-String -Pattern "inet ([\d.]+)").Matches.Groups[1].Value;
        $hostAdr = bash.exe -c "tail -1 /etc/resolv.conf | cut -d' ' -f2";
        if ($hostAdr -Match '::1$') {
            # WSL v1 shares the same IP as host so tunnel socket will be the same
            $hostAdr = $env:TUNNEL;
        } else {
            $hostAdr += ($env:TUNNEL -Replace '127.0.0.1');
        }

        $bootscript = Get-BootstrapScript -Shell 'bash' -Tunnel $hostAdr;
        C:\Windows\system32\bash.exe -c (EscArgv $bootscript);
    }
}

function vscode() {
    Invoke-WebRequest -Uri "http://$env:TUNNEL/vscode?user=$Env:UserName&path=$PWD" | Out-Null;
}
