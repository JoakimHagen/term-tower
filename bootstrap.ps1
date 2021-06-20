if ($null -Eq $env:TUNNEL) {
    $env:TUNNEL = '127.0.0.1:44022'
}
#TODO: check if server is running and is reachable
$script = Invoke-WebRequest -Uri "http://$env:TUNNEL/profile?shell=powershell&domain=$Env:UserName@$Env:ComputerName&tunnel=$env:TUNNEL" -Body '{}' -Method POST -ContentType 'application/json' | Select-Object -Expand Content;
Invoke-Command -NoNewScope ([ScriptBlock]::Create($script));
