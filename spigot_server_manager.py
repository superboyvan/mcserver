#!/usr/bin/env python3
from flask import Flask, render_template_string, request, jsonify
from flask_cors import CORS
import psutil
import subprocess
import os
import socket
import requests
import shutil
import threading
import zipfile

import logging

app = Flask(__name__)
CORS(app)

# Disable Flask request logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
app.logger.setLevel(logging.ERROR)

# Server JAR cache directory
CACHE_DIR = os.path.expanduser("~/mcserver_cache")
BUILDTOOLS_DIR = os.path.join(CACHE_DIR, "buildtools")
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(BUILDTOOLS_DIR, exist_ok=True)

# Comprehensive version list
MINECRAFT_VERSIONS = [
    "1.21.5", "1.21.4", "1.21.3", "1.21.1", "1.21",
    "1.20.6", "1.20.4", "1.20.2", "1.20.1", "1.20",
    "1.19.4", "1.19.3", "1.19.2", "1.19.1", "1.19",
    "1.18.2", "1.18.1", "1.18",
    "1.17.1", "1.17",
    "1.16.5", "1.16.4", "1.16.3", "1.16.2", "1.16.1",
    "1.15.2", "1.14.4", "1.13.2", "1.12.2", "1.11.2",
    "1.10.2", "1.9.4", "1.8.8", "1.7.10"
]

BUILDTOOLS_URL = "https://hub.spigotmc.org/jenkins/job/BuildTools/lastSuccessfulBuild/artifact/target/BuildTools.jar"

def get_server_dir():
    # Try to find home directory that exists
    if os.path.exists("/home/cam"):
        base = "/home/cam"
    else:
        base = os.path.expanduser("~")
    
    server_dir = os.path.join(base, "mcserver")
    os.makedirs(server_dir, exist_ok=True)
    return server_dir

SERVER_DIR = get_server_dir()
SPIGOT_JAR = "server.jar"
server_process = None
allocated_ram = 2048
servers = {}
build_status = {}
current_server = None  # Track which server is active in console

print(f"[INFO] Using server directory: {SERVER_DIR}")
print(f"[INFO] Cache directory: {CACHE_DIR}")

def find_existing_jar(version):
    """
    Search for existing compiled Spigot JAR files for the given version.
    Checks multiple locations:
    1. Cache directory
    2. Current directory
    3. BuildTools build directories
    4. Common Minecraft server locations
    """
    search_patterns = [
        # Cache directory
        os.path.join(CACHE_DIR, f"spigot-{version}.jar"),
        os.path.join(CACHE_DIR, f"spigot-{version}*.jar"),
        
        # BuildTools directory
        os.path.join(BUILDTOOLS_DIR, f"build-{version}", f"spigot-{version}.jar"),
        os.path.join(BUILDTOOLS_DIR, f"build-{version}", f"spigot-{version}*.jar"),
        os.path.join(BUILDTOOLS_DIR, f"spigot-{version}.jar"),
        os.path.join(BUILDTOOLS_DIR, f"spigot-{version}*.jar"),
        
        # Current working directory
        os.path.join(os.getcwd(), f"spigot-{version}.jar"),
        os.path.join(os.getcwd(), f"spigot-{version}*.jar"),
        
        # Server directory
        os.path.join(SERVER_DIR, f"spigot-{version}.jar"),
        os.path.join(SERVER_DIR, f"spigot-{version}*.jar"),
        
        # Home directory
        os.path.join(os.path.expanduser("~"), f"spigot-{version}.jar"),
        os.path.join(os.path.expanduser("~"), f"spigot-{version}*.jar"),
    ]
    
    for pattern in search_patterns:
        matches = glob.glob(pattern)
        if matches:
            # Return the first match found
            jar_file = matches[0]
            print(f"[INFO] Found existing Spigot {version} JAR: {jar_file}")
            return jar_file
    
    return None

def download_buildtools():
    """Download BuildTools.jar if not present"""
    buildtools_path = os.path.join(BUILDTOOLS_DIR, "BuildTools.jar")
    
    if os.path.exists(buildtools_path):
        print(f"[INFO] BuildTools.jar already exists")
        return buildtools_path
    
    print(f"[INFO] Downloading BuildTools.jar...")
    try:
        response = requests.get(BUILDTOOLS_URL, timeout=60, stream=True)
        if response.status_code == 200:
            with open(buildtools_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            print(f"[INFO] BuildTools.jar downloaded successfully")
            return buildtools_path
        else:
            print(f"[ERROR] Failed to download BuildTools: HTTP {response.status_code}")
            return None
    except Exception as e:
        print(f"[ERROR] BuildTools download failed: {e}")
        return None

def build_spigot(version, server_name):
    """Build or find Spigot for a specific version"""
    build_status[server_name] = {"status": "searching", "progress": 5, "message": "Searching for existing JAR..."}
    
    # First, try to find an existing compiled JAR
    existing_jar = find_existing_jar(version)
    if existing_jar:
        # Copy to cache if not already there
        cache_file = os.path.join(CACHE_DIR, f"spigot-{version}.jar")
        if existing_jar != cache_file:
            print(f"[INFO] Copying existing JAR to cache: {existing_jar} -> {cache_file}")
            try:
                shutil.copy2(existing_jar, cache_file)
                print(f"[INFO] Existing JAR copied to cache")
            except Exception as e:
                print(f"[WARNING] Could not copy to cache: {e}")
        
        build_status[server_name] = {"status": "complete", "progress": 100, "message": "Using existing JAR"}
        return existing_jar
    
    print(f"[INFO] No existing JAR found for version {version}, will build it")
    
    # Check cache directory one more time
    cache_file = os.path.join(CACHE_DIR, f"spigot-{version}.jar")
    if os.path.exists(cache_file):
        print(f"[INFO] Using cached Spigot {version}")
        build_status[server_name] = {"status": "complete", "progress": 100, "message": "Using cached JAR"}
        return cache_file
    
    build_status[server_name] = {"status": "downloading_buildtools", "progress": 10, "message": "Downloading BuildTools..."}
    
    # Download BuildTools
    buildtools_path = download_buildtools()
    if not buildtools_path:
        build_status[server_name] = {"status": "error", "message": "Failed to download BuildTools", "progress": 0}
        return None
    
    # Build directory for this version
    version_build_dir = os.path.join(BUILDTOOLS_DIR, f"build-{version}")
    os.makedirs(version_build_dir, exist_ok=True)
    
    build_status[server_name] = {"status": "building", "progress": 30, "message": f"Building Spigot {version}..."}
    print(f"[INFO] Building Spigot {version}... This may take several minutes")
    
    try:
        # Copy BuildTools to build directory
        bt_copy = os.path.join(version_build_dir, "BuildTools.jar")
        shutil.copy2(buildtools_path, bt_copy)
        
        # Run BuildTools
        cmd = ["java", "-jar", "BuildTools.jar", "--rev", version]
        process = subprocess.Popen(
            cmd,
            cwd=version_build_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for build to complete
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            print(f"[ERROR] BuildTools failed: {stderr}")
            build_status[server_name] = {"status": "error", "message": "Build failed", "progress": 0}
            return None
        
        build_status[server_name] = {"status": "finalizing", "progress": 90, "message": "Finalizing build..."}
        
        # Find the built JAR
        spigot_jar = os.path.join(version_build_dir, f"spigot-{version}.jar")
        if not os.path.exists(spigot_jar):
            # Try alternative naming
            for file in os.listdir(version_build_dir):
                if file.startswith("spigot") and file.endswith(".jar") and version in file:
                    spigot_jar = os.path.join(version_build_dir, file)
                    break
        
        if not os.path.exists(spigot_jar):
            print(f"[ERROR] Built JAR not found")
            build_status[server_name] = {"status": "error", "message": "Built JAR not found", "progress": 0}
            return None
        
        # Copy to cache
        shutil.copy2(spigot_jar, cache_file)
        print(f"[INFO] Spigot {version} built and cached successfully")
        
        build_status[server_name] = {"status": "complete", "progress": 100, "message": "Build complete!"}
        return cache_file
        
    except Exception as e:
        print(f"[ERROR] Build failed: {e}")
        build_status[server_name] = {"status": "error", "message": str(e), "progress": 0}
        return None

def find_existing_server():
    global server_process, allocated_ram
    try:
        result = subprocess.run(['pgrep', '-f', f'java.*{SPIGOT_JAR}'], capture_output=True, text=True)
        if result.stdout.strip():
            pid = int(result.stdout.strip().split('\n')[0])
            print(f"[INFO] Found existing server process with PID {pid}")
            server_process = psutil.Process(pid)
            allocated_ram = 2048
            return True
    except Exception as e:
        print(f"[INFO] No existing server found: {e}")
    return False

find_existing_server()

def get_system_info():
    total_ram = psutil.virtual_memory().total // (1024**3)
    return {"total_ram_gb": total_ram, "total_ram_mb": total_ram * 1024}

def is_server_running():
    global server_process
    if server_process is None:
        return False
    if hasattr(server_process, 'poll'):
        return server_process.poll() is None
    else:
        try:
            return server_process.is_running()
        except:
            return False

def start_server(ram_mb):
    global server_process, allocated_ram, current_server
    
    # If managing a specific server, use that one
    if current_server and current_server in servers:
        return start_named_server(current_server, ram_mb)
    
    # Otherwise try to start default server
    if server_process and is_server_running():
        return {"status": "error", "message": "Server already running"}
    
    # Check if server.jar exists
    jar_path = os.path.join(SERVER_DIR, SPIGOT_JAR)
    if not os.path.exists(jar_path):
        return {"status": "error", "message": f"No server.jar found in {SERVER_DIR}. Create a server first!"}
    
    allocated_ram = ram_mb
    cmd = ["java", f"-Xmx{ram_mb}M", f"-Xms{ram_mb//2}M", "-jar", SPIGOT_JAR, "nogui"]
    try:
        os.chdir(SERVER_DIR)
        server_process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        return {"status": "success", "message": f"Server starting with {ram_mb}MB RAM"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def stop_server():
    global server_process
    if not server_process or not is_server_running():
        return {"status": "error", "message": "Server not running"}
    
    if hasattr(server_process, 'stdin'):
        try:
            server_process.stdin.write("stop\n")
            server_process.stdin.flush()
            server_process.wait(timeout=30)
            return {"status": "success", "message": "Server stopped"}
        except subprocess.TimeoutExpired:
            server_process.kill()
            return {"status": "success", "message": "Server force stopped"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    else:
        try:
            server_process.terminate()
            server_process.wait(timeout=10)
            return {"status": "success", "message": "Server stopped"}
        except:
            try:
                server_process.kill()
            except:
                pass
            return {"status": "success", "message": "Server force stopped"}

def run_command(cmd):
    global server_process, current_server
    
    # If managing a specific server, send command to it
    if current_server and current_server in servers:
        return run_command_on_server(current_server, cmd)
    
    if not is_server_running():
        return {"status": "error", "message": "Server not running"}
    
    if not hasattr(server_process, 'stdin'):
        return {"status": "error", "message": "Cannot send commands to existing process"}
    
    try:
        server_process.stdin.write(cmd + "\n")
        server_process.stdin.flush()
        return {"status": "success", "message": f"Command executed: {cmd}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def run_command_on_server(server_name, cmd):
    if server_name not in servers:
        return {"status": "error", "message": f"Server '{server_name}' not found"}
    
    server_info = servers[server_name]
    if not server_info['running'] or not server_info['process']:
        return {"status": "error", "message": f"Server '{server_name}' not running"}
    
    try:
        server_info['process'].stdin.write(cmd + "\n")
        server_info['process'].stdin.flush()
        return {"status": "success", "message": f"Command executed: {cmd}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def add_to_hosts(server_name):
    try:
        hosts_file = '/etc/hosts'
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        
        with open(hosts_file, 'r') as f:
            content = f.read()
            if server_name in content:
                return
        
        entry = f"{ip}    {server_name}\n"
        with open(hosts_file, 'a') as f:
            f.write(entry)
        print(f"[INFO] Added {server_name} to /etc/hosts")
    except Exception as e:
        print(f"[WARNING] Could not update /etc/hosts: {e}")

def update_server_properties(props_file, server_name, port):
    try:
        if not os.path.exists(props_file):
            with open(props_file, 'w') as f:
                f.write(f"motd={server_name}\n")
                f.write(f"server-port={port}\n")
                f.write("online-mode=true\n")
                f.write("max-players=20\n")
            return
        
        with open(props_file, 'r') as f:
            lines = f.readlines()
        
        updated_motd = False
        updated_port = False
        new_lines = []
        
        for line in lines:
            if line.startswith('motd='):
                new_lines.append(f'motd={server_name}\n')
                updated_motd = True
            elif line.startswith('server-port='):
                new_lines.append(f'server-port={port}\n')
                updated_port = True
            else:
                new_lines.append(line)
        
        if not updated_motd:
            new_lines.append(f'motd={server_name}\n')
        if not updated_port:
            new_lines.append(f'server-port={port}\n')
        
        with open(props_file, 'w') as f:
            f.writelines(new_lines)
    except Exception as e:
        print(f"[ERROR] Could not update server.properties: {e}")

def get_next_available_port():
    used_ports = {s.get('port', 25565) for s in servers.values() if s.get('port')}
    port = 25565
    while port in used_ports:
        port += 1
    return port

def start_named_server(server_name, ram_mb):
    global current_server
    if server_name not in servers:
        return {"status": "error", "message": f"Server '{server_name}' not found"}
    
    server_info = servers[server_name]
    if server_info['running']:
        return {"status": "error", "message": f"Server '{server_name}' already running"}
    
    # Determine base directory
    if os.path.exists("/home/cam"):
        base = "/home/cam"
    else:
        base = os.path.expanduser("~")
    
    server_dir = os.path.join(base, f"mcserver-{server_name.lower()}")
    
    # Check if server directory and JAR exist
    if not os.path.exists(server_dir):
        return {"status": "error", "message": f"Server directory not found: {server_dir}"}
    
    jar_path = os.path.join(server_dir, SPIGOT_JAR)
    if not os.path.exists(jar_path):
        return {"status": "error", "message": f"Server JAR not found. Server may still be building."}
    
    port = server_info.get('port', get_next_available_port())
    
    cmd = ["java", f"-Xmx{ram_mb}M", f"-Xms{ram_mb//2}M", "-jar", SPIGOT_JAR, "nogui"]
    
    try:
        os.chdir(server_dir)
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        server_info['process'] = proc
        server_info['running'] = True
        server_info['port'] = port
        server_info['pid'] = proc.pid
        server_info['ram'] = ram_mb
        current_server = server_name
        
        props_file = os.path.join(server_dir, "server.properties")
        update_server_properties(props_file, server_name, port)
        
        return {"status": "success", "message": f"Server '{server_name}' started on port {port} with {ram_mb}MB RAM"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/api/system-info')
def api_system_info():
    return jsonify(get_system_info())

@app.route('/api/server-status')
def api_server_status():
    global current_server
    
    # If managing a specific server, return its status
    if current_server and current_server in servers:
        server_info = servers[current_server]
        return jsonify({
            "running": server_info['running'],
            "allocated_ram": server_info['ram'],
            "server_name": current_server
        })
    
    # Otherwise return default server status
    return jsonify({
        "running": is_server_running(),
        "allocated_ram": allocated_ram,
        "server_name": None
    })

@app.route('/api/start', methods=['POST'])
def api_start():
    data = request.json
    ram = data.get('ram', 2048)
    return jsonify(start_server(ram))

@app.route('/api/stop', methods=['POST'])
def api_stop():
    return jsonify(stop_server())

@app.route('/api/command', methods=['POST'])
def api_command():
    data = request.json
    cmd = data.get('command', '')
    return jsonify(run_command(cmd))

@app.route('/api/command-named/<server_name>', methods=['POST'])
def api_command_named(server_name):
    data = request.json
    cmd = data.get('command', '')
    return jsonify(run_command_on_server(server_name, cmd))

@app.route('/api/versions', methods=['GET'])
def api_versions():
    versions = [{"version": v, "type": "spigot"} for v in MINECRAFT_VERSIONS]
    return jsonify({"versions": versions})

@app.route('/api/build-status/<server_name>', methods=['GET'])
def api_build_status(server_name):
    status = build_status.get(server_name, {"status": "unknown", "progress": 0})
    return jsonify(status)

@app.route('/api/build-server', methods=['POST'])
def api_build_server():
    # Handle both JSON and form-data requests
    if request.is_json:
        data = request.json
        server_name = data.get('server_name', 'Server')
        ram = data.get('ram', 2048)
        version = data.get('version', '1.21.5')
        world_file = None
    else:
        server_name = request.form.get('server_name', 'Server')
        ram = int(request.form.get('ram', 2048))
        version = request.form.get('version', '1.21.5')
        world_file = request.files.get('world')
    
    if server_name in servers:
        return jsonify({"status": "error", "message": f"Server '{server_name}' already exists"})
    
    servers[server_name] = {
        'process': None,
        'ram': ram,
        'running': False,
        'building': True,
        'name': server_name,
        'version': version
    }
    
    def build_async():
        try:
            # Determine base directory
            if os.path.exists("/home/cam"):
                base = "/home/cam"
            else:
                base = os.path.expanduser("~")
            
            server_dir = os.path.join(base, f"mcserver-{server_name.lower()}")
            os.makedirs(server_dir, exist_ok=True)
            
            # Build/download Spigot (or find existing)
            jar_file = build_spigot(version, server_name)
            
            if not jar_file:
                servers[server_name]['building'] = False
                build_status[server_name] = {"status": "error", "message": "Failed to build server", "progress": 0}
                return
            
            # Copy JAR to server directory
            dst_jar = os.path.join(server_dir, SPIGOT_JAR)
            shutil.copy2(jar_file, dst_jar)
            
            # Create eula.txt
            eula_file = os.path.join(server_dir, "eula.txt")
            with open(eula_file, 'w') as f:
                f.write("eula=true\n")
            
            # Handle world import if provided
            if world_file:
                build_status[server_name] = {"status": "importing_world", "progress": 80, "message": "Importing world..."}
                print(f"[INFO] Importing world for server '{server_name}'")
                
                try:
                    # Save uploaded file temporarily
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
                        world_file.save(tmp_file.name)
                        tmp_path = tmp_file.name
                    
                    # Extract the world
                    with zipfile.ZipFile(tmp_path, 'r') as zip_ref:
                        # Extract all contents
                        zip_ref.extractall(server_dir)
                    
                    # Clean up temp file
                    os.remove(tmp_path)
                    print(f"[INFO] World imported successfully")
                    
                except Exception as e:
                    print(f"[ERROR] Failed to import world: {e}")
                    build_status[server_name] = {"status": "warning", "message": f"Server created but world import failed: {e}", "progress": 90}
            
            # Create server.properties
            props_file = os.path.join(server_dir, "server.properties")
            port = get_next_available_port()
            update_server_properties(props_file, server_name, port)
            
            servers[server_name]['building'] = False
            servers[server_name]['port'] = port
            add_to_hosts(server_name)
            
            print(f"[INFO] Server '{server_name}' built successfully for Spigot {version}")
            build_status[server_name] = {"status": "complete", "message": "Server ready!", "progress": 100}
            
        except Exception as e:
            servers[server_name]['building'] = False
            build_status[server_name] = {"status": "error", "message": str(e), "progress": 0}
            print(f"[ERROR] Failed to build server: {e}")
    
    # Start build in background thread
    thread = threading.Thread(target=build_async)
    thread.daemon = True
    thread.start()
    
    world_msg = " with custom world" if world_file else ""
    return jsonify({"status": "success", "message": f"Building server '{server_name}'{world_msg} for Spigot {version}. Checking for existing JAR first..."})

@app.route('/api/servers', methods=['GET'])
def api_servers():
    return jsonify({"servers": [{
        "name": name,
        "running": s['running'],
        "building": s.get('building', False),
        "ram": s['ram'],
        "port": s.get('port', 25565),
        "version": s.get('version', 'unknown')
    } for name, s in servers.items()]})

@app.route('/api/start-named', methods=['POST'])
def api_start_named():
    data = request.json
    server_name = data.get('server_name')
    ram = data.get('ram', 2048)
    result = start_named_server(server_name, ram)
    return jsonify(result)

@app.route('/api/stop-named/<server_name>', methods=['POST'])
def api_stop_named(server_name):
    global current_server
    if server_name not in servers:
        return jsonify({"status": "error", "message": f"Server '{server_name}' not found"})
    
    server_info = servers[server_name]
    if not server_info['running'] or not server_info['process']:
        return jsonify({"status": "error", "message": f"Server '{server_name}' not running"})
    
    try:
        server_info['process'].stdin.write("stop\n")
        server_info['process'].stdin.flush()
        server_info['process'].wait(timeout=30)
        server_info['running'] = False
        if current_server == server_name:
            current_server = None
        return jsonify({"status": "success", "message": f"Server '{server_name}' stopped"})
    except subprocess.TimeoutExpired:
        server_info['process'].kill()
        server_info['running'] = False
        if current_server == server_name:
            current_server = None
        return jsonify({"status": "success", "message": f"Server '{server_name}' force stopped"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/set-current-server/<server_name>', methods=['POST'])
def api_set_current_server(server_name):
    global current_server
    if server_name not in servers:
        return jsonify({"status": "error", "message": f"Server '{server_name}' not found"})
    current_server = server_name
    return jsonify({"status": "success", "message": f"Now managing: {server_name}"})

@app.route('/api/server-files/<server_name>', methods=['GET'])
def api_server_files(server_name):
    if server_name not in servers:
        return jsonify({"status": "error", "message": "Server not found"}), 404
    
    # Determine base directory
    if os.path.exists("/home/cam"):
        base = "/home/cam"
    else:
        base = os.path.expanduser("~")
    
    server_dir = os.path.join(base, f"mcserver-{server_name.lower()}")
    if not os.path.exists(server_dir):
        return jsonify({"status": "error", "message": "Server directory not found"}), 404
    
    try:
        files = []
        for item in os.listdir(server_dir):
            path = os.path.join(server_dir, item)
            is_dir = os.path.isdir(path)
            size = 0 if is_dir else os.path.getsize(path)
            files.append({
                'name': item,
                'isDir': is_dir,
                'size': size
            })
        return jsonify({"files": sorted(files, key=lambda x: (not x['isDir'], x['name']))})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/upload/<server_name>', methods=['POST'])
def api_upload(server_name):
    if server_name not in servers:
        return jsonify({"status": "error", "message": "Server not found"}), 404
    
    # Determine base directory
    if os.path.exists("/home/cam"):
        base = "/home/cam"
    else:
        base = os.path.expanduser("~")
    
    server_dir = os.path.join(base, f"mcserver-{server_name.lower()}")
    if not os.path.exists(server_dir):
        return jsonify({"status": "error", "message": "Server directory not found"}), 404
    
    try:
        uploaded = []
        for file in request.files.getlist('files'):
            if file.filename:
                filename = os.path.basename(file.filename)
                filename = filename.replace('/', '').replace('\\', '')
                
                if not filename or filename.startswith('.'):
                    continue
                
                filepath = os.path.join(server_dir, filename)
                
                if not os.path.abspath(filepath).startswith(os.path.abspath(server_dir)):
                    continue
                
                file.seek(0, 2)
                size = file.tell()
                file.seek(0)
                
                if size > 100 * 1024 * 1024:
                    return jsonify({"status": "error", "message": f"File {filename} too large (max 100MB)"}), 413
                
                file.save(filepath)
                uploaded.append(filename)
        
        return jsonify({"status": "success", "message": f"Uploaded {len(uploaded)} file(s)", "files": uploaded})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/delete-file/<server_name>/<filename>', methods=['DELETE'])
def api_delete_file(server_name, filename):
    if server_name not in servers:
        return jsonify({"status": "error", "message": "Server not found"}), 404
    
    # Determine base directory
    if os.path.exists("/home/cam"):
        base = "/home/cam"
    else:
        base = os.path.expanduser("~")
    
    server_dir = os.path.join(base, f"mcserver-{server_name.lower()}")
    filepath = os.path.join(server_dir, filename)
    
    if not os.path.abspath(filepath).startswith(os.path.abspath(server_dir)):
        return jsonify({"status": "error", "message": "Invalid path"}), 403
    
    try:
        if os.path.isfile(filepath):
            os.remove(filepath)
            return jsonify({"status": "success", "message": f"Deleted {filename}"})
        else:
            return jsonify({"status": "error", "message": "File not found"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

HTML = """<!DOCTYPE html>
<html>
<head>
    <title>Server Manager</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #1a1a2e; color: #fff; min-height: 100vh; }
        .wrapper { display: grid; grid-template-columns: 250px 1fr; min-height: 100vh; }
        .sidebar { background: #16213e; border-right: 1px solid #0f3460; padding: 20px; overflow-y: auto; }
        .sidebar h3 { color: #0f9dff; font-size: 0.85em; margin-top: 25px; margin-bottom: 15px; text-transform: uppercase; font-weight: 700; letter-spacing: 1px; }
        .sidebar h3:first-child { margin-top: 0; }
        .sidebar a { display: flex; align-items: center; gap: 12px; padding: 12px 15px; color: #aaa; text-decoration: none; border-radius: 6px; transition: all 0.2s; cursor: pointer; }
        .sidebar a:hover { background: #0f3460; color: #0f9dff; }
        .sidebar a.active { background: #0f9dff; color: #000; }
        .main { overflow-y: auto; padding: 30px; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }
        .header h1 { font-size: 2em; }
        .header-icons { display: flex; gap: 15px; }
        .header-icons button { background: none; border: none; color: #aaa; font-size: 1.3em; cursor: pointer; }
        .content-panel { background: #16213e; border: 1px solid #0f3460; border-radius: 8px; padding: 30px; margin-bottom: 20px; }
        .panel-title { font-size: 1.3em; margin-bottom: 20px; }
        .stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .stat-card { background: #0f3460; padding: 15px; border-radius: 8px; border-left: 4px solid #0f9dff; }
        .stat-label { color: #aaa; font-size: 0.9em; margin-bottom: 5px; }
        .stat-value { font-size: 1.8em; font-weight: bold; color: #0f9dff; }
        .control-section { margin-top: 20px; }
        .control-label { color: #aaa; font-size: 0.85em; margin-bottom: 10px; font-weight: 600; }
        input[type="range"] { width: 100%; margin-bottom: 10px; }
        input[type="text"], input[type="number"], input[type="file"] { background: #0f3460; border: 1px solid #0f9dff; color: #fff; padding: 10px 15px; border-radius: 6px; width: 100%; margin-bottom: 10px; font-family: inherit; }
        input[type="text"]:focus, input[type="number"]:focus { outline: none; border-color: #00d4ff; box-shadow: 0 0 10px rgba(15, 157, 255, 0.3); }
        .button-row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 15px; }
        button { padding: 12px 20px; border: none; border-radius: 6px; font-weight: 600; cursor: pointer; transition: all 0.2s; font-size: 0.95em; }
        .btn-primary { background: #0f9dff; color: #000; }
        .btn-primary:hover:not(:disabled) { background: #00d4ff; }
        .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
        .btn-success { background: #00b368; color: #fff; }
        .btn-success:hover:not(:disabled) { background: #00d485; }
        .btn-danger { background: #ff4444; color: #fff; }
        .btn-danger:hover:not(:disabled) { background: #ff6666; }
        .server-list { display: grid; gap: 10px; }
        .server-card { background: #0f3460; padding: 15px; border-radius: 6px; border-left: 4px solid #00b368; }
        .server-card.offline { border-left-color: #666; }
        .server-name { font-weight: 600; margin-bottom: 5px; }
        .server-info { color: #aaa; font-size: 0.9em; margin-bottom: 10px; }
        .server-status { display: flex; align-items: center; gap: 8px; font-size: 0.9em; }
        .status-dot { width: 10px; height: 10px; border-radius: 50%; background: #00b368; }
        .server-card.offline .status-dot { background: #666; }
        .console-input { display: flex; gap: 10px; margin-top: 10px; }
        .console-input input { flex: 1; }
        .console-input button { flex: 0.3; }
        .log { background: #0f3460; padding: 15px; border-radius: 6px; height: 300px; overflow-y: auto; font-family: monospace; font-size: 0.85em; }
        .log-line { margin-bottom: 3px; }
        .log-success { color: #00d485; }
        .log-error { color: #ff6666; }
        .log-info { color: #aaa; }
        .log-cmd { color: #0f9dff; }
        select { background: #0f3460; border: 1px solid #0f9dff; color: #fff; padding: 10px 15px; border-radius: 6px; width: 100%; margin-bottom: 10px; font-family: inherit; }
    </style>
</head>
<body>
    <div class="wrapper">
        <div class="sidebar">
            <h3>Server Management</h3>
            <a class="nav-item active" data-tab="console">→ Console</a>
            <a class="nav-item" data-tab="servers">📦 Servers</a>
            <a class="nav-item" data-tab="create">➕ Create Server</a>
            <a class="nav-item" data-tab="commands">⚡ Quick Commands</a>
            
            <h3>Settings</h3>
            <a class="nav-item" data-tab="system">⚙️ System</a>
            <a class="nav-item" data-tab="files">📁 File Manager</a>
        </div>

        <div class="main">
            <div class="header">
                <h1>Server Manager</h1>
                <div class="header-icons">
                    <button>⚙️</button>
                    <button>🔔</button>
                    <button>→</button>
                </div>
            </div>

            <div id="console-tab" class="tab-content">
                <div class="content-panel">
                    <div class="panel-title">Console</div>
                    
                    <div class="stat-grid">
                        <div class="stat-card">
                            <div class="stat-label">Status</div>
                            <div class="stat-value"><span id="statusDot" class="status-dot"></span><span id="statusText">OFFLINE</span></div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-label">Allocated RAM</div>
                            <div class="stat-value" id="allocRam">0 MB</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-label">System RAM</div>
                            <div class="stat-value" id="sysRam">0 GB</div>
                        </div>
                    </div>

                    <div class="control-section">
                        <div class="control-label">RAM ALLOCATION</div>
                        <input type="range" id="ramSlider" min="512" max="8192" step="256" value="2048" disabled>
                        <div style="color: #aaa; font-size: 0.9em;"><span id="ramValue">2048</span> MB</div>
                    </div>

                    <div class="button-row" style="margin-top: 30px;">
                        <button class="btn-success" id="startBtn" onclick="startServer()">START SERVER</button>
                        <button class="btn-danger" id="stopBtn" onclick="stopServer()" disabled>STOP SERVER</button>
                    </div>

                    <div style="margin-top: 30px;">
                        <div class="control-label">COMMAND INPUT</div>
                        <div class="console-input">
                            <input type="text" id="cmdInput" placeholder="Enter command...">
                            <button class="btn-primary" onclick="sendCmd()">SEND</button>
                        </div>
                    </div>

                    <div style="margin-top: 30px;">
                        <div class="control-label">ACTIVITY LOG</div>
                        <div class="log" id="logBox"></div>
                    </div>
                </div>
            </div>

            <div id="servers-tab" class="tab-content" style="display: none;">
                <div class="content-panel">
                    <div class="panel-title">Active Servers</div>
                    <div class="server-list" id="serverList">
                        <div style="color: #aaa;">No servers running</div>
                    </div>
                </div>
            </div>

            <div id="create-tab" class="tab-content" style="display: none;">
                <div class="content-panel">
                    <div class="panel-title">Create New Server</div>
                    
                    <div class="control-section">
                        <div class="control-label">SERVER NAME</div>
                        <input type="text" id="serverName" placeholder="e.g., Cammc">
                    </div>

                    <div class="control-section">
                        <div class="control-label">SERVER VERSION (Spigot)</div>
                        <select id="serverVersion">
                            <option value="">Loading versions...</option>
                        </select>
                    </div>

                    <div class="control-section">
                        <div class="control-label">RAM ALLOCATION</div>
                        <input type="range" id="newRamSlider" min="512" max="8192" step="256" value="2048">
                        <div style="color: #aaa; font-size: 0.9em;"><span id="newRamValue">2048</span> MB</div>
                    </div>

                    <div class="control-section">
                        <div class="control-label">🌍 IMPORT EXISTING WORLD (Optional)</div>
                        <div style="background: #0f3460; border: 1px solid #0f9dff; border-radius: 6px; padding: 15px; margin-bottom: 10px;">
                            <div style="color: #aaa; font-size: 0.85em; margin-bottom: 10px;">
                                Upload a world folder as a ZIP file. The ZIP should contain folders like: world, world_nether, world_the_end
                            </div>
                            <input type="file" id="worldInput" accept=".zip" style="margin-bottom: 0;">
                            <div id="worldStatus" style="color: #0f9dff; font-size: 0.85em; margin-top: 5px;"></div>
                        </div>
                    </div>

                    <button class="btn-primary" onclick="createServer()" style="width: 100%; margin-top: 20px; padding: 15px;">CREATE SERVER</button>
                </div>
            </div>

            <div id="commands-tab" class="tab-content" style="display: none;">
                <div class="content-panel">
                    <div class="panel-title">Quick Commands</div>
                    <div id="cmdGrid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px;"></div>
                </div>
            </div>

            <div id="files-tab" class="tab-content" style="display: none;">
                <div class="content-panel">
                    <div class="panel-title">File Manager</div>
                    
                    <div class="control-section">
                        <div class="control-label">SELECT SERVER</div>
                        <select id="fileServerSelect" onchange="loadServerFiles()">
                            <option value="">Choose a server...</option>
                        </select>
                    </div>

                    <div id="fileManager" style="display: none;">
                        <div class="control-section">
                            <div class="control-label">UPLOAD FILES</div>
                            <input type="file" id="fileInput" multiple>
                            <button class="btn-primary" onclick="uploadFiles()" style="width: 100%;">UPLOAD</button>
                        </div>

                        <div class="control-section" style="margin-top: 20px;">
                            <div class="control-label">SERVER FILES</div>
                            <div style="background: #0f3460; border: 1px solid #0f9dff; border-radius: 6px; padding: 15px; max-height: 400px; overflow-y: auto;">
                                <div id="fileList" style="color: #aaa;">Loading files...</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div id="system-tab" class="tab-content" style="display: none;">
                <div class="content-panel">
                    <div class="panel-title">System Information</div>
                    <div class="stat-grid">
                        <div class="stat-card">
                            <div class="stat-label">Total RAM</div>
                            <div class="stat-value" id="sysTotalRam">0 GB</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-label">Active Servers</div>
                            <div class="stat-value" id="sysActiveServers">0</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const COMMANDS = {
            "Player": [
                {name: "List", cmd: "list"},
                {name: "OP @p", cmd: "op @p"},
                {name: "Gamemode Creative", cmd: "gamemode creative @p"},
                {name: "Gamemode Survival", cmd: "gamemode survival @p"},
                {name: "Teleport Spawn", cmd: "tp @p 0 100 0"},
                {name: "Heal", cmd: "effect give @p instant_health"},
            ],
            "World": [
                {name: "Day", cmd: "time set day"},
                {name: "Night", cmd: "time set night"},
                {name: "Clear Weather", cmd: "weather clear"},
                {name: "Rain", cmd: "weather rain"},
                {name: "Save All", cmd: "save-all"},
            ],
            "Server": [
                {name: "Announce", cmd: "say Server Message"},
                {name: "Difficulty Hard", cmd: "difficulty 3"},
                {name: "Difficulty Easy", cmd: "difficulty 1"},
            ]
        };

        let logs = [];
        let activeServer = null;

        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', () => {
                document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(t => t.style.display = 'none');
                item.classList.add('active');
                const tab = item.dataset.tab + '-tab';
                document.getElementById(tab).style.display = 'block';
            });
        });

        function addLog(msg, type = 'info') {
            logs.push({msg, type});
            if (logs.length > 100) logs.shift();
            document.getElementById('logBox').innerHTML = logs.map(l => `<div class="log-line log-${l.type}">${l.msg}</div>`).join('');
            document.getElementById('logBox').scrollTop = 999999;
        }

        function updateStatus() {
            fetch('/api/server-status').then(r => r.json()).then(d => {
                const online = d.running;
                document.getElementById('statusDot').style.background = online ? '#00b368' : '#666';
                let statusText = online ? 'ONLINE' : 'OFFLINE';
                if (d.server_name) {
                    statusText += ` (${d.server_name})`;
                }
                document.getElementById('statusText').textContent = statusText;
                document.getElementById('allocRam').textContent = d.allocated_ram + ' MB';
                document.getElementById('startBtn').disabled = online;
                document.getElementById('stopBtn').disabled = !online;
                document.getElementById('ramSlider').disabled = online;
            }).catch(e => console.log('Status check failed:', e));
        }

        function getSystemInfo() {
            fetch('/api/system-info').then(r => r.json()).then(d => {
                document.getElementById('sysRam').textContent = d.total_ram_gb + ' GB';
                document.getElementById('sysTotalRam').textContent = d.total_ram_gb + ' GB';
                document.getElementById('ramSlider').max = Math.floor(d.total_ram_mb * 0.75);
                document.getElementById('newRamSlider').max = Math.floor(d.total_ram_mb * 0.75);
            }).catch(e => console.log('System info failed:', e));
        }

        function loadVersions() {
            fetch('/api/versions').then(r => r.json()).then(d => {
                const select = document.getElementById('serverVersion');
                select.innerHTML = '';
                d.versions.forEach(v => {
                    const opt = document.createElement('option');
                    opt.value = v.version;
                    opt.textContent = `${v.version} (${v.type})`;
                    select.appendChild(opt);
                });
                select.value = '1.21.5';
            }).catch(e => {
                console.log('Load versions failed:', e);
                document.getElementById('serverVersion').innerHTML = '<option value="1.21.5">1.21.5 (fallback)</option>';
            });
        }

        function startServer() {
            const ram = document.getElementById('ramSlider').value;
            addLog(`Starting server with ${ram}MB...`, 'info');
            fetch('/api/start', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ram: parseInt(ram)})})
                .then(r => r.json()).then(d => {
                    if (d.status === 'error') {
                        addLog('⚠️ ' + d.message, 'error');
                        if (d.message.includes('No server.jar')) {
                            addLog('💡 Create a server first using "Create Server" tab!', 'info');
                        }
                    } else {
                        addLog(d.message, 'success');
                    }
                    setTimeout(updateStatus, 1000);
                }).catch(e => addLog('Start failed: ' + e, 'error'));
        }

        function stopServer() {
            addLog('Stopping...', 'info');
            fetch('/api/stop', {method: 'POST'}).then(r => r.json()).then(d => {
                addLog(d.message, d.status === 'success' ? 'success' : 'error');
                setTimeout(updateStatus, 1000);
            }).catch(e => addLog('Stop failed: ' + e, 'error'));
        }

        function sendCmd() {
            const cmd = document.getElementById('cmdInput').value.trim();
            if (!cmd) return;
            addLog(`> ${cmd}`, 'cmd');
            
            let url = '/api/command';
            if (activeServer) {
                url = `/api/command-named/${activeServer}`;
            }
            
            fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({command: cmd})})
                .then(r => r.json()).then(d => {
                    addLog(d.message, d.status === 'success' ? 'success' : 'error');
                }).catch(e => addLog('Command failed: ' + e, 'error'));
            document.getElementById('cmdInput').value = '';
        }

        function createServer() {
            const name = document.getElementById('serverName').value.trim();
            const ram = document.getElementById('newRamSlider').value;
            const version = document.getElementById('serverVersion').value;
            const worldFile = document.getElementById('worldInput').files[0];
            
            if (!name) {
                addLog('⚠️ Server name required', 'error');
                return;
            }
            
            const formData = new FormData();
            formData.append('server_name', name);
            formData.append('ram', ram);
            formData.append('version', version);
            if (worldFile) {
                formData.append('world', worldFile);
                addLog(`🌍 Uploading world file: ${worldFile.name}...`, 'info');
            }
            
            addLog(`🔨 Creating '${name}' (Spigot ${version})...`, 'info');
            addLog('🔍 Checking for existing compiled JARs first...', 'info');
            if (!worldFile) {
                addLog('⏳ If JAR not found, building will take 5-10 minutes!', 'info');
            }
            
            fetch('/api/build-server', {method: 'POST', body: formData})
                .then(r => r.json()).then(d => {
                    if (d.status === 'success') {
                        addLog('✅ ' + d.message, 'success');
                        document.getElementById('serverName').value = '';
                        document.getElementById('worldInput').value = '';
                        document.getElementById('worldStatus').textContent = '';
                        setTimeout(() => {
                            document.querySelector('[data-tab="servers"]').click();
                        }, 2000);
                    } else {
                        addLog('❌ ' + d.message, 'error');
                    }
                    loadServers();
                }).catch(e => addLog('Create failed: ' + e, 'error'));
        }

        function loadServers() {
            fetch('/api/servers').then(r => r.json()).then(d => {
                const html = d.servers.map(s => {
                    let statusColor = '#666';
                    let statusText = 'OFFLINE';
                    let buildProgress = '';
                    
                    if (s.building) {
                        statusColor = '#ff9800';
                        statusText = 'SEARCHING/BUILDING';
                        buildProgress = '<div style="margin-top: 8px; color: #ff9800; font-size: 0.85em;">⏳ Checking for existing JAR or building (5-10 min)...</div>';
                    } else if (s.running) {
                        statusColor = '#00b368';
                        statusText = 'ONLINE';
                    }
                    
                    return `
                    <div class="server-card ${!s.running ? 'offline' : ''}">
                        <div class="server-name">${s.name}</div>
                        <div class="server-info">Version: ${s.version} | RAM: ${s.ram}MB | Port: ${s.port}</div>
                        <div class="server-status">
                            <span class="status-dot" style="background: ${statusColor};"></span>
                            <span>${statusText}</span>
                        </div>
                        ${buildProgress}
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 5px; margin-top: 10px;">
                            <button class="btn-success" onclick="startNamed('${s.name}', ${s.ram})" style="padding: 8px 12px; font-size: 0.85em;" ${s.running || s.building ? 'disabled' : ''}>START</button>
                            <button class="btn-danger" onclick="stopNamed('${s.name}')" style="padding: 8px 12px; font-size: 0.85em;" ${!s.running ? 'disabled' : ''}>STOP</button>
                        </div>
                        <button class="btn-primary" onclick="manageServer('${s.name}')" style="width: 100%; margin-top: 5px; padding: 8px 12px; font-size: 0.85em;">MANAGE</button>
                    </div>
                `;
                }).join('');
                document.getElementById('serverList').innerHTML = html || '<div style="color: #aaa;">No servers</div>';
                document.getElementById('sysActiveServers').textContent = d.servers.filter(s => s.running).length;
            }).catch(e => console.log('Load servers failed:', e));
        }

        function startNamed(name, ram) {
            addLog(`Starting '${name}'...`, 'info');
            activeServer = name;
            fetch('/api/start-named', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({server_name: name, ram: parseInt(ram)})})
                .then(r => r.json()).then(d => {
                    addLog(d.message, d.status === 'success' ? 'success' : 'error');
                    setTimeout(loadServers, 1000);
                }).catch(e => addLog('Start failed: ' + e, 'error'));
        }

        function stopNamed(name) {
            addLog(`Stopping '${name}'...`, 'info');
            fetch(`/api/stop-named/${name}`, {method: 'POST'})
                .then(r => r.json()).then(d => {
                    addLog(d.message, d.status === 'success' ? 'success' : 'error');
                    if (activeServer === name) activeServer = null;
                    setTimeout(loadServers, 1000);
                }).catch(e => addLog('Stop failed: ' + e, 'error'));
        }

        function manageServer(name) {
            activeServer = name;
            fetch(`/api/set-current-server/${name}`, {method: 'POST'})
                .then(r => r.json()).then(d => {
                    addLog(d.message, d.status === 'success' ? 'success' : 'error');
                    document.querySelector('[data-tab="console"]').click();
                    updateStatus();
                }).catch(e => addLog('Failed to set server: ' + e, 'error'));
        }

        function loadServerOptions() {
            fetch('/api/servers').then(r => r.json()).then(d => {
                const select = document.getElementById('fileServerSelect');
                select.innerHTML = '<option value="">Choose a server...</option>';
                d.servers.forEach(s => {
                    const opt = document.createElement('option');
                    opt.value = s.name;
                    opt.textContent = s.name;
                    select.appendChild(opt);
                });
            }).catch(e => console.log('Load server options failed:', e));
        }

        function loadServerFiles() {
            const server = document.getElementById('fileServerSelect').value;
            if (!server) {
                document.getElementById('fileManager').style.display = 'none';
                return;
            }
            document.getElementById('fileManager').style.display = 'block';
            
            fetch(`/api/server-files/${server}`)
                .then(r => r.json()).then(d => {
                    if (d.files) {
                        const html = d.files.map(f => `
                            <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px; background: rgba(15, 157, 255, 0.1); margin-bottom: 8px; border-radius: 4px;">
                                <div>
                                    <div style="color: #60a5fa; font-weight: 600;">${f.isDir ? '📁' : '📄'} ${f.name}</div>
                                    <div style="color: #aaa; font-size: 0.8em;">${f.isDir ? 'Folder' : (f.size / 1024).toFixed(2) + ' KB'}</div>
                                </div>
                                ${!f.isDir ? `<button class="btn-danger" onclick="deleteFile('${server}', '${f.name}')" style="padding: 8px 12px; font-size: 0.85em;">DELETE</button>` : ''}
                            </div>
                        `).join('');
                        document.getElementById('fileList').innerHTML = html || '<div style="color: #aaa;">Empty</div>';
                    }
                }).catch(e => console.log('Load files failed:', e));
        }

        function uploadFiles() {
            const server = document.getElementById('fileServerSelect').value;
            const files = document.getElementById('fileInput').files;
            
            if (!server) {
                addLog('Select a server first', 'error');
                return;
            }
            if (files.length === 0) {
                addLog('Select files to upload', 'error');
                return;
            }
            
            const formData = new FormData();
            for (let file of files) {
                formData.append('files', file);
            }
            
            addLog(`Uploading ${files.length} file(s) to ${server}...`, 'info');
            fetch(`/api/upload/${server}`, {method: 'POST', body: formData})
                .then(r => r.json()).then(d => {
                    addLog(d.message, d.status === 'success' ? 'success' : 'error');
                    document.getElementById('fileInput').value = '';
                    loadServerFiles();
                }).catch(e => addLog('Upload failed: ' + e, 'error'));
        }

        function deleteFile(server, filename) {
            if (!confirm(`Delete ${filename}?`)) return;
            addLog(`Deleting ${filename}...`, 'info');
            fetch(`/api/delete-file/${server}/${filename}`, {method: 'DELETE'})
                .then(r => r.json()).then(
