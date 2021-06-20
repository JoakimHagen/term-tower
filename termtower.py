from os import walk, path
import json
from subprocess import run
from flask import Flask, Response, request
from gevent.pywsgi import WSGIServer
import nesttempl

plugins = []
for dirpath, dirnames, filenames in walk("."):
    if not "plugin.py" in filenames:
        continue
    directory = path.basename(dirpath)
    module = __import__(directory + ".plugin")
    plugins.append(module.plugin)
    print("plugin imported: " + module.__name__)

if not plugins:
    print("no plugins were found in working-directory")

init_filename  = 'bootstrap'
setup_filename = 'setup'
tunnel_port = 44022
root_dir = path.abspath(path.dirname(__file__))

def get_file(filename):
    filename = path.relpath(filename)
    try:
        src = path.join(root_dir, filename)
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


def update_state(state, template, pid, proc, domain):
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
        if not last or last['domain'] != domain or last['proc'] != proc or last['pid'] != pid:
            trace.append({ 'pid': pid, 'proc': proc, 'domain': domain })

    if template:
        state['template'] = template
    if not template:
        state['template'] = '{green:{cwd}} {grey:{trace}}{blue:{cmd}}>'
    state['prompt'] = create_prompt(state['template'], state)

    return state

class Server:

    def __init__(self) -> None:
        pass

    def get_profile_url(self, domain):
        profile_url = "http://{{ tunnel }}/profile?shell={{ shell }}&domain={{ domain }}&tunnel={{ tunnel }}"
        return profile_url.replace('{{ domain }}', domain)

    def get_file(self, filename):
        return get_file(filename)

server = Server()

def include_plugin(plugin):
    if '__name__' in dir(plugin):
        name = plugin.__name__
    else:
        name = plugin.__class__.__name__
    print("plugin imported: " + name)
    plugins.append(plugin)

import inspect

def get_plugin(language):
    if not language:
        raise ValueError(f"language can not None or empty")
    for p in plugins:
        if p.is_supported(server, language):
            return p

def get_bootstrap_script(language, target_shell=None, tunnel=f"127.0.0.1:{tunnel_port}", state={}):

    plugin = get_plugin(language)
    if plugin is None:
        raise ValueError(f"language '{language}' is not supported!")

    if not target_shell:
        target_shell = language
        target_shell_plugin = plugin
    elif target_shell != language:
        target_shell_plugin = get_plugin(target_shell)
        if target_shell_plugin is None:
            raise ValueError(f"language '{target_shell}' is not supported!")
    else:
        target_shell_plugin = plugin
    
    command = target_shell_plugin.start_shell(server, target_shell)

    if '{{ profile.file }}' in command:
        create_cmd = plugin.create_temp_file(server, language)
        delete_cmd = plugin.delete_temp_file(server, language)
        command = '\n'.join([create_cmd, command, delete_cmd]).replace('{{ profile.file }}', plugin.refer_temp_file(server, language))
    
    if '{{ profile.content }}' in command:
        command = command.replace('{{ profile.content }}', plugin.refer_argument_script(server, language))

    bootstrap = plugin.get_bootstrap(server, language)
    bootstrap = bootstrap \
        .replace('{{ tunnel }}', tunnel) \
        .replace('{{ shell }}', target_shell) \
        .replace('{{ STATE }}', json.dumps(state))

    return bootstrap + '\n' + command

def get_profile_script(language, tunnel=f"127.0.0.1:{tunnel_port}", state={}):
    plugin = get_plugin(language)
    if plugin is None:
        raise ValueError(f"language '{language}' is not supported!")
    return plugin.get_profile(server, language) \
        .replace('{{ tunnel }}', tunnel) \
        .replace('{{ shell }}', language) \
        .replace('{{ STATE }}', json.dumps(state)) \
        .replace('{{ PROMPT }}', state['prompt'])

app = Flask(__name__)

@app.route('/health', methods=['GET', 'POST'])
def health_check():
    return "ok"

@app.route('/bootstrap', methods=['GET', 'POST'])
def route_bootstrap():
    shell   = request.args.get('shell')
    t_shell = request.args.get('target')
    tunnel  = request.args.get('tunnel')
    #command = request.args.get('command')
    state = request.json
    if not state:
        state = dict()
    print(json.dumps(state))

    return get_bootstrap_script(shell, t_shell, tunnel, state)

@app.route('/profile', methods=['GET','POST'])
def r_profile():
    shell = request.args.get('shell')
    
    if (shell.startswith('-')):
        shell = shell[1:]

    state = request.json
    print(json.dumps(state))
    template = request.args.get('template')
    tunnel = request.args.get('tunnel')
    pid = request.args.get('pid')
    if not pid:
        pid = -1
    proc = request.args.get('proc')
    if not proc:
        proc = shell
    domain = request.args.get('domain')
    state = update_state(state, template, pid, proc, domain)
    state_json = json.dumps(state)
    print(state_json)
    
    return get_profile_script(shell, tunnel, state)

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
    wsgi_port=tunnel_port
    http_server = WSGIServer((wsgi_ip, wsgi_port), app)
    print(f"Serving on {wsgi_ip}:{wsgi_port}")
    http_server.serve_forever()

