import os
import json
from subprocess import run
from flask import Flask, Response, request
from gevent.pywsgi import WSGIServer
import nesttempl

init_filename  = 'bootstrap'
setup_filename = 'setup'

posix_bash_command = '''
    tempfile=$(mktemp /tmp/bashrc-XXXXXX);
    getprofile > $tempfile;
    bash --rcfile $tempfile -i;
    rm $tempfile;
    '''

bash_bash_command = '''
    bash --rcfile <(getprofile) -i;
    '''

bash_powershell_command = '''
    powershell -Command $(getprofile);
    '''

powershell_powershell_command = '''
    powershell -Command (Get-Profile);
    '''

powershell_bash_command = '''
    $TempFile = New-TemporaryFile;
    Get-Profile | Out-File $TempFile;
    bash --rcfile $TempFile -i;
    Delete-File $TempFile;
    '''

bash_tempfile = ["""
tempfile=$(mktemp /tmp/bashrc-XXXXXX);
getprofile > $tempfile;
""","""
rm $tempfile;
"""
]
powershell_tempfile = ["""
$tempfile = New-TemporaryFile;
Get-Profile | Out-File $tempfile;
""","""
Remove-Item $tempfile;
"""
]

def get_bootstrap(bootstrap_script, lang='bash', command='bash --rcfile {{ profile.file }} -i', target_lang='bash'):
    if lang == 'bash' or lang == 'dash' or lang == 'sh':
        context = dict(profile = dict(
            content = "$(getprofile)",
            file    = "$tempfile"
        ))
        if 'profile.file' in command:
            context['before'] = bash_tempfile[0]
            context['after']  = bash_tempfile[1]
        else:
            context['before'] = ''
            context['after']  = ''
    elif lang == 'powershell':
        context = dict(profile = dict(
            content = "(EscArgv (Get-Profile))",
            file    = "$tempfile"
        ))
        if 'profile.file' in command:
            context['before'] = powershell_tempfile[0]
            context['after']  = powershell_tempfile[1]
        else:
            context['before'] = ''
            context['after']  = ''
    
    command = command.replace('{{ profile.file }}', context['profile']['file'])
    command = command.replace('{{ profile.content }}', context['profile']['content'])

    bootstrap_script = bootstrap_script.replace('{{ shell }}', target_lang)

    # context['command'] = fill_template(command, context)

    return bootstrap_script.replace('{{ command }}', context['before'] + command + context['after'])

    # return fill_template(bootstrap_script, context)

def root_dir():
    return os.path.abspath(os.path.dirname(__file__))

def get_file(filename):
    try:
        src = os.path.join(root_dir(), filename)
        return open(src).read()
    except IOError as exc:
        return str(exc)

def segm(branch, previous_domain):
    segment = []
    if 'domain' in branch and (branch["domain"] != previous_domain or previous_domain == ''):
        segment.append(str(branch["domain"]))
        previous_domain = branch["domain"]
    
    if 'proc' in branch:
        segment.append(str(branch['proc']))
    return segment

def get_trace(state):
    segments = []
    previous_domain = ''
    for branch in state['trace'][:-1]:
        segment = segm(branch, previous_domain)
        
        segments.append('-'.join(segment))

    segment = segm(state['trace'][-1], previous_domain)
    segments.append('-'.join(segment[:-1]) + '-')
    segments.append(segment[-1])

    return segments


def create_prompt(template, state):
    trace = get_trace(state)

    subst_lookup = nesttempl.subst_lookup
    subst_lookup['cwd'] = lambda: ["{cwd}"]
    subst_lookup['trace'] = lambda: ['>'.join(trace[:-1])]
    subst_lookup['cmd'] = lambda: [trace[-1]]

    return nesttempl.process(template, subst_lookup)


def update_state(state, template, proc, domain):
    if not state:
        state = dict()

    if template:
        state['template'] = template

    if proc:
        if 'trace' not in state:
            state['trace'] = []
        trace = state['trace']
        # idempotence check
        last = len(trace) > 0 and trace[-1]
        if not last or last['domain'] != domain or last['proc'] != proc:
            trace.append({ 'proc': proc, 'domain': domain })

    if template:
        state['template'] = template
    if not template:
        state['template'] = '{green:{cwd}} {grey:{trace}}{blue:{cmd}}>'
    state['prompt'] = create_prompt(state['template'], state)

    return state

def get_target_shell_cmd(target):
    if target == 'bash':
        return 'bash --rcfile {{ profile.file }} -i'
    elif target == 'powershell':
        return 'powershell -NoProfile -NoExit -Command {{ profile.content }}'
    elif target == 'cmd':
        return 'powershell -NoProfile -NoExit -Command {{ profile.content }}'
    else:
        raise ValueError(f"unrecognized target shell '{target}'")


app = Flask(__name__)

@app.route('/health', methods=['GET', 'POST'])
def health_check():
    return "ok"

@app.route('/bootstrap', methods=['GET', 'POST'])
def route_bootstrap():
    shell = request.args.get('shell')
    t_shell = request.args.get('target')
    if not t_shell:
        t_shell = shell
    tunnel = request.args.get('tunnel')
    command = request.args.get('command')
    state = request.json
    if not state:
        state = dict()
    print(json.dumps(state))
    if not command:
        command = get_target_shell_cmd(t_shell)

    if shell == 'bash' or shell == 'dash' or shell == 'sh':
        content = get_file('templates/posix/' + init_filename + '.sh')
        content = get_bootstrap(content, lang='sh', command=command, target_lang=t_shell)
    elif shell == 'powershell':
        content = get_file('templates/powershell/' + init_filename + '.ps1')
        content = get_bootstrap(content, lang='powershell', command=command, target_lang=t_shell)
    elif shell == 'cmd':
        content = get_file('templates/wincmd/' + init_filename + '.bat')
    else:
        content = '#UNRECOGNIZED SHELL ' + shell

    content = content.replace('{{ STATE }}', json.dumps(state))
    content = content.replace('{{ tunnel }}', tunnel)

    return Response(content, mimetype="text/x-shellscript")

@app.route('/init', methods=['GET', 'POST'])
def init():
    path = ''
    shell = request.args.get('shell')
    tunnel = request.args.get('tunnel')
    token = request.args.get('token')
    
    state = request.json
    if not state:
        state = dict()

    if shell == 'bash':
        content = get_file('templates/posix/' + init_filename + '.sh')
        content = content.replace('{{ $PTRACE_PATH }}', path.replace('\\', '\\\\'))
        content = content.replace('{{ tunnel }}', tunnel)
        content = content.replace('{{ STATE }}', json.dumps(state))
    elif shell == 'powershell':
        content = get_file('templates/powershell/' + init_filename + '.ps1')
        content = content.replace('{{ $TUNNEL_PORT }}', tunnel)
        content = content.replace('{{ STATE }}', json.dumps(state))
    elif shell == 'cmd':
        content = get_file('templates/wincmd/' + init_filename + '.bat')
        content = content.replace('{{ $TUNNEL_PORT }}', tunnel)
        content = content.replace('{{ STATE }}', json.dumps(state))
    else:
        content = '#UNRECOGNIZED SHELL ' + shell

    return Response(content, mimetype="text/x-shellscript")

@app.route('/p2', methods=['GET','POST'])
def part2():
    shell = request.args.get('shell')
    
    state = request.json
    print(json.dumps(state))
    template = request.args.get('template')
    tunnel = request.args.get('tunnel')
    proc = request.args.get('proc')
    if not proc:
        proc = shell
    domain = request.args.get('domain')
    state = update_state(state, template, proc, domain)
    state_json = json.dumps(state)
    print(state_json)

    if shell == 'bash':
        content = get_file('templates/posix/' + setup_filename + '.sh')
    elif shell == 'powershell':
        content = get_file('templates/powershell/' + setup_filename + '.ps1')
    elif shell == 'cmd':
        content = get_file('templates/powershell/' + setup_filename + '.ps1')
    else:
        raise ValueError(f"unrecognized shell {shell}")
    
    content = content.replace('{{ tunnel }}', tunnel or '127.0.0.1:44022')
    content = content.replace('{{ STATE }}', state_json)
    content = content.replace('{{ PROMPT }}', state['prompt'])

    return Response(content, mimetype="text/x-shellscript")

@app.route('/createjson', methods=['GET','POST'])
def createjson():
    state = request.json
    template = request.args.get('template')
    proc = request.args.get('proc')
    domain = request.args.get('domain')
    return update_state(state, template, proc, domain)

@app.route('/prompt', methods=['POST'])
def prompt():
    template = request.args.get('template')
    if not template:
        template = '{green:{cwd}} {grey:{trace}}{blue:{cmd}}>'
    return Response(create_prompt(template, request.json), mimetype="text/plain")

@app.route('/vscode', methods=['GET'])
def vscode():
    user = request.args.get('user')
    path = request.args.get('path')
    if path.startswith("C:"):
        path = path[2:] # cut off 'C:' cause code doesn't like it
    path = path.replace('\\','/')
    remote_uri = f"vscode-remote://ssh-remote+{user}@127.0.0.1:44044{path}"
    print('code', '--folder-uri', remote_uri)
    run(['code.cmd', '--folder-uri', remote_uri])
    return ""

if __name__ == '__main__':
    wsgi_ip='0.0.0.0'
    wsgi_port=44022
    http_server = WSGIServer((wsgi_ip, wsgi_port), app)
    print(f"Serving on {wsgi_ip}:{wsgi_port}")
    http_server.serve_forever()
