#!/usr/bin/env python3
"""
Enhanced Minecraft Server Manager with World Import
Run with: python3 server_manager.py
Access at: http://localhost:5000
"""

from flask import Flask, render_template_string, request, jsonify
from flask_cors import CORS
import psutil, subprocess, os, socket, requests, shutil, threading, zipfile, tempfile, glob, logging

app = Flask(__name__)
CORS(app)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# Configuration
CACHE_DIR = os.path.expanduser("~/mcserver_cache")
BUILDTOOLS_DIR = os.path.join(CACHE_DIR, "buildtools")
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(BUILDTOOLS_DIR, exist_ok=True)

MINECRAFT_VERSIONS = ["1.21.5", "1.21.4", "1.21.3", "1.21.1", "1.21", "1.20.6", "1.20.4", 
    "1.20.2", "1.20.1", "1.20", "1.19.4", "1.19.3", "1.19.2", "1.19.1", "1.19", "1.18.2", 
    "1.18.1", "1.18", "1.17.1", "1.17", "1.16.5", "1.16.4", "1.16.3", "1.16.2", "1.16.1",
    "1.15.2", "1.14.4", "1.13.2", "1.12.2", "1.11.2", "1.10.2", "1.9.4", "1.8.8", "1.7.10"]

BUILDTOOLS_URL = "https://hub.spigotmc.org/jenkins/job/BuildTools/lastSuccessfulBuild/artifact/target/BuildTools.jar"
SPIGOT_JAR = "server.jar"

# Global state
base_dir = "/home/cam" if os.path.exists("/home/cam") else os.path.expanduser("~")
SERVER_DIR = os.path.join(base_dir, "mcserver")
os.makedirs(SERVER_DIR, exist_ok=True)

server_process = None
allocated_ram = 2048
servers = {}
build_status = {}
current_server = None

print(f"[INFO] Server directory: {SERVER_DIR}")
print(f"[INFO] Cache directory: {CACHE_DIR}")

# Helper functions
def find_existing_jar(version):
    patterns = [
        os.path.join(CACHE_DIR, f"spigot-{version}.jar"),
        os.path.join(BUILDTOOLS_DIR, f"build-{version}", f"spigot-{version}.jar"),
        os.path.join(os.getcwd(), f"spigot-{version}.jar"),
    ]
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            print(f"[INFO] Found existing JAR: {matches[0]}")
            return matches[0]
    return None

def download_buildtools():
    path = os.path.join(BUILDTOOLS_DIR, "BuildTools.jar")
    if os.path.exists(path):
        return path
    print("[INFO] Downloading BuildTools...")
    try:
        r = requests.get(BUILDTOOLS_URL, timeout=60, stream=True)
        if r.status_code == 200:
            with open(path, 'wb') as f:
                for chunk in r.iter_content(8192):
                    if chunk: f.write(chunk)
            return path
    except Exception as e:
        print(f"[ERROR] Download failed: {e}")
    return None

def build_spigot(version, server_name):
    build_status[server_name] = {"status": "searching", "progress": 5, "message": "Searching..."}
    
    jar = find_existing_jar(version)
    if jar:
        cache = os.path.join(CACHE_DIR, f"spigot-{version}.jar")
        if jar != cache:
            shutil.copy2(jar, cache)
        build_status[server_name] = {"status": "complete", "progress": 100, "message": "Using existing JAR"}
        return jar
    
    build_status[server_name] = {"status": "building", "progress": 30, "message": f"Building {version}..."}
    bt = download_buildtools()
    if not bt:
        build_status[server_name] = {"status": "error", "message": "BuildTools download failed", "progress": 0}
        return None
    
    build_dir = os.path.join(BUILDTOOLS_DIR, f"build-{version}")
    os.makedirs(build_dir, exist_ok=True)
    shutil.copy2(bt, os.path.join(build_dir, "BuildTools.jar"))
    
    proc = subprocess.Popen(["java", "-jar", "BuildTools.jar", "--rev", version], 
        cwd=build_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = proc.communicate()
    
    if proc.returncode != 0:
        build_status[server_name] = {"status": "error", "message": "Build failed", "progress": 0}
        return None
    
    jar_path = os.path.join(build_dir, f"spigot-{version}.jar")
    cache_path = os.path.join(CACHE_DIR, f"spigot-{version}.jar")
    if os.path.exists(jar_path):
        shutil.copy2(jar_path, cache_path)
        build_status[server_name] = {"status": "complete", "progress": 100, "message": "Build complete!"}
        return cache_path
    
    build_status[server_name] = {"status": "error", "message": "JAR not found", "progress": 0}
    return None

def get_next_port():
    used = {s.get('port', 25565) for s in servers.values()}
    port = 25565
    while port in used:
        port += 1
    return port

def is_running():
    global server_process
    if not server_process:
        return False
    return server_process.poll() is None if hasattr(server_process, 'poll') else server_process.is_running()

# API Routes
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/system-info')
def api_system_info():
    ram = psutil.virtual_memory().total // (1024**3)
    return jsonify({"total_ram_gb": ram, "total_ram_mb": ram * 1024})

@app.route('/api/server-status')
def api_server_status():
    if current_server and current_server in servers:
        s = servers[current_server]
        return jsonify({"running": s['running'], "allocated_ram": s['ram'], "server_name": current_server})
    return jsonify({"running": is_running(), "allocated_ram": allocated_ram, "server_name": None})

@app.route('/api/versions')
def api_versions():
    return jsonify({"versions": [{"version": v, "type": "spigot"} for v in MINECRAFT_VERSIONS]})

@app.route('/api/servers')
def api_servers():
    return jsonify({"servers": [{
        "name": n, "running": s['running'], "building": s.get('building', False),
        "ram": s['ram'], "port": s.get('port', 25565), "version": s.get('version', 'unknown')
    } for n, s in servers.items()]})

@app.route('/api/build-status/<server_name>')
def api_build_status(server_name):
    return jsonify(build_status.get(server_name, {"status": "unknown", "progress": 0}))

@app.route('/api/build-server', methods=['POST'])
def api_build_server():
    if request.is_json:
        name = request.json.get('server_name', 'Server')
        ram = request.json.get('ram', 2048)
        version = request.json.get('version', '1.21.5')
        world = None
    else:
        name = request.form.get('server_name', 'Server')
        ram = int(request.form.get('ram', 2048))
        version = request.form.get('version', '1.21.5')
        world = request.files.get('world')
    
    if name in servers:
        return jsonify({"status": "error", "message": f"Server '{name}' exists"})
    
    servers[name] = {'process': None, 'ram': ram, 'running': False, 'building': True, 
                     'name': name, 'version': version}
    
    def build():
        try:
            sdir = os.path.join(base_dir, f"mcserver-{name.lower()}")
            os.makedirs(sdir, exist_ok=True)
            
            jar = build_spigot(version, name)
            if not jar:
                servers[name]['building'] = False
                return
            
            shutil.copy2(jar, os.path.join(sdir, SPIGOT_JAR))
            
            with open(os.path.join(sdir, "eula.txt"), 'w') as f:
                f.write("eula=true\n")
            
            if world:
                build_status[name] = {"status": "importing_world", "progress": 85, "message": "Importing world..."}
                with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp:
                    world.save(tmp.name)
                    with zipfile.ZipFile(tmp.name, 'r') as z:
                        z.extractall(sdir)
                    os.remove(tmp.name)
                print(f"[INFO] World imported for '{name}'")
            
            port = get_next_port()
            props = os.path.join(sdir, "server.properties")
            with open(props, 'w') as f:
                f.write(f"motd={name}\nserver-port={port}\nonline-mode=true\nmax-players=20\n")
            
            servers[name]['building'] = False
            servers[name]['port'] = port
            build_status[name] = {"status": "complete", "message": "Ready!", "progress": 100}
            print(f"[INFO] Server '{name}' ready ({version})")
        except Exception as e:
            servers[name]['building'] = False
            build_status[name] = {"status": "error", "message": str(e), "progress": 0}
    
    threading.Thread(target=build, daemon=True).start()
    msg = " with world" if world else ""
    return jsonify({"status": "success", "message": f"Building '{name}'{msg}..."})

@app.route('/api/start-named', methods=['POST'])
def api_start_named():
    global current_server
    name = request.json.get('server_name')
    ram = request.json.get('ram', 2048)
    
    if name not in servers or servers[name]['running']:
        return jsonify({"status": "error", "message": "Cannot start"})
    
    sdir = os.path.join(base_dir, f"mcserver-{name.lower()}")
    jar = os.path.join(sdir, SPIGOT_JAR)
    if not os.path.exists(jar):
        return jsonify({"status": "error", "message": "JAR not found"})
    
    try:
        os.chdir(sdir)
        proc = subprocess.Popen(["java", f"-Xmx{ram}M", f"-Xms{ram//2}M", "-jar", SPIGOT_JAR, "nogui"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        servers[name].update({'process': proc, 'running': True, 'ram': ram, 'pid': proc.pid})
        current_server = name
        return jsonify({"status": "success", "message": f"Started on port {servers[name].get('port', 25565)}"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/stop-named/<server_name>', methods=['POST'])
def api_stop_named(server_name):
    global current_server
    if server_name not in servers or not servers[server_name]['running']:
        return jsonify({"status": "error", "message": "Not running"})
    
    try:
        servers[server_name]['process'].stdin.write("stop\n")
        servers[server_name]['process'].stdin.flush()
        servers[server_name]['process'].wait(timeout=30)
        servers[server_name]['running'] = False
        if current_server == server_name:
            current_server = None
        return jsonify({"status": "success", "message": "Stopped"})
    except:
        servers[server_name]['process'].kill()
        servers[server_name]['running'] = False
        return jsonify({"status": "success", "message": "Force stopped"})

@app.route('/api/command-named/<server_name>', methods=['POST'])
def api_cmd_named(server_name):
    if server_name not in servers or not servers[server_name]['running']:
        return jsonify({"status": "error", "message": "Not running"})
    try:
        cmd = request.json.get('command', '')
        servers[server_name]['process'].stdin.write(cmd + "\n")
        servers[server_name]['process'].stdin.flush()
        return jsonify({"status": "success", "message": f"Executed: {cmd}"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/set-current-server/<server_name>', methods=['POST'])
def api_set_current(server_name):
    global current_server
    if server_name not in servers:
        return jsonify({"status": "error", "message": "Not found"})
    current_server = server_name
    return jsonify({"status": "success", "message": f"Managing: {server_name}"})

@app.route('/api/server-files/<server_name>')
def api_files(server_name):
    if server_name not in servers:
        return jsonify({"status": "error"}), 404
    sdir = os.path.join(base_dir, f"mcserver-{server_name.lower()}")
    if not os.path.exists(sdir):
        return jsonify({"status": "error"}), 404
    files = [{"name": i, "isDir": os.path.isdir(os.path.join(sdir, i)), 
              "size": 0 if os.path.isdir(os.path.join(sdir, i)) else os.path.getsize(os.path.join(sdir, i))}
             for i in os.listdir(sdir)]
    return jsonify({"files": sorted(files, key=lambda x: (not x['isDir'], x['name']))})

@app.route('/api/upload/<server_name>', methods=['POST'])
def api_upload(server_name):
    if server_name not in servers:
        return jsonify({"status": "error"}), 404
    sdir = os.path.join(base_dir, f"mcserver-{server_name.lower()}")
    uploaded = []
    for f in request.files.getlist('files'):
        if f.filename:
            fn = os.path.basename(f.filename).replace('/', '').replace('\\', '')
            if fn and not fn.startswith('.'):
                f.save(os.path.join(sdir, fn))
                uploaded.append(fn)
    return jsonify({"status": "success", "files": uploaded})

@app.route('/api/delete-file/<server_name>/<filename>', methods=['DELETE'])
def api_delete(server_name, filename):
    if server_name not in servers:
        return jsonify({"status": "error"}), 404
    sdir = os.path.join(base_dir, f"mcserver-{server_name.lower()}")
    fpath = os.path.join(sdir, filename)
    if os.path.isfile(fpath):
        os.remove(fpath)
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 404

# HTML Template (see next artifact for full HTML)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html><head><title>MC Server Manager</title>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<!-- Full HTML in next artifact -->
</head></html>
"""

if __name__ == '__main__':
    print("[INFO] Starting Server Manager on http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
