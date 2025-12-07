function manageServer(name) {
            activeServer = name;
            document.querySelector('[data-tab="console"]').click();
            addLog(`Now managing: ${name}`, 'info');
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
            });
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
                });
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
                });
        }

        function deleteFile(server, filename) {
            if (!confirm(`Delete ${filename}?`)) return;
            addLog(`Deleting ${filename}...`, 'info');
            fetch(`/api/delete-file/${server}/${filename}`, {method: 'DELETE'})
                .then(r => r.json()).then(d => {
                    addLog(d.message, d.status === 'success' ? 'success' : 'error');
                    loadServerFiles();
                });
        }

        function initCmds() {@app.route('/api/stop-named/<server_name>', methods=['POST'])
def api_stop_named(server_name):
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
        return jsonify({"status": "success", "message": f"Server '{server_name}' stopped"})
    except subprocess.TimeoutExpired:
        server_info['process'].kill()
        server_info['running'] = False
        return jsonify({"status": "success", "message": f"Server '{server_name}' force stopped"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/server-files/<server_name>', methods=['GET'])
def api_server_files(server_name):
    """List files in server directory"""
    if server_name not in servers:
        return jsonify({"status": "error", "message": "Server not found"}), 404
    
    server_dir = os.path.join("/home/cam", f"mcserver-{server_name.lower()}")
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
    """Upload files to server"""
    if server_name not in servers:
        return jsonify({"status": "error", "message": "Server not found"}), 404
    
    server_dir = os.path.join("/home/cam", f"mcserver-{server_name.lower()}")
    if not os.path.exists(server_dir):
        return jsonify({"status": "error", "message": "Server directory not found"}), 404
    
    try:
        uploaded = []
        for file in request.files.getlist('files'):
            if file.filename:
                filename = os.path.basename(file.filename)
                filepath = os.path.join(server_dir, filename)
                file.save(filepath)
                uploaded.append(filename)
        
        return jsonify({"status": "success", "message": f"Uploaded {len(uploaded)} file(s)", "files": uploaded})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/delete-file/<server_name>/<filename>', methods=['DELETE'])
def api_delete_file(server_name, filename):
    """Delete a file from server"""
    if server_name not in servers:
        return jsonify({"status": "error", "message": "Server not found"}), 404
    
    server_dir = os.path.join("/home/cam", f"mcserver-{server_name.lower()}")
    filepath = os.path.join(server_dir, filename)
    
    # Security check - make sure path is within server dir
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=False)@app.route('/api/start-named', methods=['POST'])
def api_start_named():
    data = request.json
    server_name = data.get('server_name')
    ram = data.get('ram', 2048)
    result = start_named_server(server_name, ram)
    return jsonify(result)

@app.route('/api/stop-named/<server_name>', methods=['POST'])
def api_stop_named(server_name):
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
        return jsonify({"status": "success", "message": f"Server '{server_name}' stopped"})
    except subprocess.TimeoutExpired:
        server_info['process'].kill()
        server_info['running'] = False
        return jsonify({"status": "success", "message": f"Server '{server_name}' force stopped"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})@app.route('/api/command', methods=['POST'])
def api_command():
    data = request.json
    cmd = data.get('command', '')
    return jsonify(run_command(cmd))

@app.route('/api/command-named/<server_name>', methods=['POST'])
def api_command_named(server_name):
    data = request.json
    cmd = data.get('command', '')
    return jsonify(run_command_on_server(server_name, cmd))

@app.route('/api/build-server', methods=['POST'])#!/usr/bin/env python3
from flask import Flask, render_template_string, request, jsonify
from flask_cors import CORS
import psutil
import subprocess
import os
import socket

app = Flask(__name__)
CORS(app)

def get_server_dir():
    if os.path.exists("/home/cam/mcserver/server.jar"):
        return "/home/cam/mcserver"
    elif os.path.exists(os.path.expanduser("~/mcserver/server.jar")):
        return os.path.expanduser("~/mcserver")
    else:
        return os.path.expanduser("~/mcserver")

SERVER_DIR = get_server_dir()
SPIGOT_JAR = "server.jar"
server_process = None
allocated_ram = 2048
servers = {}

print(f"[INFO] Using server directory: {SERVER_DIR}")

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
    global server_process, allocated_ram
    if server_process and is_server_running():
        return {"status": "error", "message": "Server already running"}
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
    global server_process
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
    """Run command on a specific named server"""
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
    """Add server name to /etc/hosts"""
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
    """Update server.properties with custom name and port"""
    try:
        with open(props_file, 'r') as f:
            lines = f.readlines()
        
        updated = False
        new_lines = []
        
        for line in lines:
            if line.startswith('motd='):
                new_lines.append(f'motd={server_name}\n')
                updated = True
            elif line.startswith('server-port='):
                new_lines.append(f'server-port={port}\n')
                updated = True
            else:
                new_lines.append(line)
        
        if not updated or 'motd=' not in ''.join(new_lines):
            new_lines.append(f'motd={server_name}\n')
            new_lines.append(f'server-port={port}\n')
        
        with open(props_file, 'w') as f:
            f.writelines(new_lines)
    except Exception as e:
        print(f"[ERROR] Could not update server.properties: {e}")

def start_named_server(server_name, ram_mb):
    """Start a named server instance"""
    if server_name not in servers:
        return {"status": "error", "message": f"Server '{server_name}' not found"}
    
    server_info = servers[server_name]
    if server_info['running']:
        return {"status": "error", "message": f"Server '{server_name}' already running"}
    
    server_dir = os.path.join("/home/cam", f"mcserver-{server_name.lower()}")
    port = 25565 + len([s for s in servers.values() if s['running']])
    
    cmd = ["java", f"-Xmx{ram_mb}M", f"-Xms{ram_mb//2}M", "-jar", SPIGOT_JAR, "nogui"]
    
    try:
        os.chdir(server_dir)
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        server_info['process'] = proc
        server_info['running'] = True
        server_info['port'] = port
        server_info['pid'] = proc.pid
        
        props_file = os.path.join(server_dir, "server.properties")
        if os.path.exists(props_file):
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
    return jsonify({"running": is_server_running(), "allocated_ram": allocated_ram})

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
def api_build_server():
    data = request.json
    server_name = data.get('server_name', 'Server')
    ram = data.get('ram', 2048)
    version = data.get('version', 'latest')
    
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
    
    # Create server directory and copy files
    try:
        import shutil
        server_dir = os.path.join("/home/cam", f"mcserver-{server_name.lower()}")
        
        # Create directory if it doesn't exist
        os.makedirs(server_dir, exist_ok=True)
        
        # Copy server.jar based on version
        # For now, just copy from main server - user can replace jar manually if needed
        src_jar = os.path.join(SERVER_DIR, SPIGOT_JAR)
        dst_jar = os.path.join(server_dir, SPIGOT_JAR)
        if os.path.exists(src_jar) and not os.path.exists(dst_jar):
            shutil.copy2(src_jar, dst_jar)
            # Note: Server jar version would need to be managed separately
            # For now we copy the existing jar - user should replace if different version needed
        
        # Copy server.properties
        src_props = os.path.join(SERVER_DIR, "server.properties")
        dst_props = os.path.join(server_dir, "server.properties")
        if os.path.exists(src_props) and not os.path.exists(dst_props):
            shutil.copy2(src_props, dst_props)
        
        # Copy eula.txt
        src_eula = os.path.join(SERVER_DIR, "eula.txt")
        dst_eula = os.path.join(server_dir, "eula.txt")
        if os.path.exists(src_eula) and not os.path.exists(dst_eula):
            shutil.copy2(src_eula, dst_eula)
        
        servers[server_name]['building'] = False
        add_to_hosts(server_name)
        
        msg = f"Server '{server_name}' built for version {version}. Ready to start."
        return jsonify({"status": "success", "message": msg})
    except Exception as e:
        servers[server_name]['building'] = False
        return jsonify({"status": "error", "message": f"Failed to build server: {str(e)}"})

@app.route('/api/servers', methods=['GET'])
def api_servers():
    return jsonify({"servers": [{
        "name": name,
        "running": s['running'],
        "building": s.get('building', False),
        "ram": s['ram'],
        "port": s.get('port', 25565)
    } for name, s in servers.items()]})

@app.route('/api/start-named', methods=['POST'])
def api_start_named():
    data = request.json
    server_name = data.get('server_name')
    ram = data.get('ram', 2048)
    result = start_named_server(server_name, ram)
    return jsonify(result)

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
        input[type="text"], input[type="number"] { background: #0f3460; border: 1px solid #0f9dff; color: #fff; padding: 10px 15px; border-radius: 6px; width: 100%; margin-bottom: 10px; font-family: inherit; }
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
            <a class="nav-item" data-tab="logs">📊 Logs</a>
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

            <!-- Console Tab -->
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

            <!-- Servers Tab -->
            <div id="servers-tab" class="tab-content" style="display: none;">
                <div class="content-panel">
                    <div class="panel-title">Active Servers</div>
                    <div class="server-list" id="serverList">
                        <div style="color: #aaa;">No servers running</div>
                    </div>
                </div>
            </div>

            <!-- Create Server Tab -->
            <div id="create-tab" class="tab-content" style="display: none;">
                <div class="content-panel">
                    <div class="panel-title">Create New Server</div>
                    
                    <div class="control-section">
                        <div class="control-label">SERVER NAME</div>
                        <input type="text" id="serverName" placeholder="e.g., Cammc">
                    </div>

                    <div class="control-section">
                        <div class="control-label">SERVER VERSION</div>
                        <select id="serverVersion" style="background: #0f3460; border: 1px solid #0f9dff; color: #fff; padding: 10px 15px; border-radius: 6px; width: 100%; margin-bottom: 10px; font-family: inherit;">
                            <optgroup label="1.21+">
                                <option value="1.21.8">1.21.8</option>
                                <option value="1.21.7">1.21.7</option>
                                <option value="1.21.6">1.21.6</option>
                                <option value="1.21.5">1.21.5</option>
                                <option value="1.21.4">1.21.4</option>
                                <option value="1.21.3">1.21.3</option>
                                <option value="1.21.2">1.21.2</option>
                                <option value="1.21.1">1.21.1</option>
                                <option value="1.21">1.21</option>
                            </optgroup>
                            <optgroup label="1.20+">
                                <option value="1.20.1">1.20.1</option>
                                <option value="1.20">1.20</option>
                            </optgroup>
                            <optgroup label="1.19+">
                                <option value="1.19.3">1.19.3</option>
                                <option value="1.19.2">1.19.2</option>
                                <option value="1.19.1">1.19.1</option>
                                <option value="1.19">1.19</option>
                            </optgroup>
                            <optgroup label="1.18+">
                                <option value="1.18.2">1.18.2</option>
                                <option value="1.18.1">1.18.1</option>
                                <option value="1.18">1.18</option>
                            </optgroup>
                            <optgroup label="1.17+">
                                <option value="1.17.1">1.17.1</option>
                                <option value="1.17">1.17</option>
                            </optgroup>
                            <optgroup label="1.16+">
                                <option value="1.16.5">1.16.5</option>
                                <option value="1.16.4">1.16.4</option>
                                <option value="1.16.3">1.16.3</option>
                                <option value="1.16.2">1.16.2</option>
                                <option value="1.16.1">1.16.1</option>
                                <option value="1.16">1.16</option>
                            </optgroup>
                            <optgroup label="1.15+">
                                <option value="1.15.2">1.15.2</option>
                                <option value="1.15.1">1.15.1</option>
                                <option value="1.15">1.15</option>
                            </optgroup>
                            <optgroup label="1.14+">
                                <option value="1.14.4">1.14.4</option>
                                <option value="1.14.3">1.14.3</option>
                                <option value="1.14.2">1.14.2</option>
                                <option value="1.14.1">1.14.1</option>
                                <option value="1.14">1.14</option>
                            </optgroup>
                            <optgroup label="1.13+">
                                <option value="1.13.2">1.13.2</option>
                                <option value="1.13.1">1.13.1</option>
                                <option value="1.13">1.13</option>
                            </optgroup>
                            <optgroup label="1.12+">
                                <option value="1.12.2">1.12.2</option>
                                <option value="1.12.1">1.12.1</option>
                                <option value="1.12">1.12</option>
                            </optgroup>
                            <optgroup label="1.11+">
                                <option value="1.11.2">1.11.2</option>
                                <option value="1.11.1">1.11.1</option>
                                <option value="1.11">1.11</option>
                            </optgroup>
                            <optgroup label="1.10+">
                                <option value="1.10.2">1.10.2</option>
                                <option value="1.10.1">1.10.1</option>
                                <option value="1.10">1.10</option>
                            </optgroup>
                            <optgroup label="1.9+">
                                <option value="1.9.4">1.9.4</option>
                                <option value="1.9.3">1.9.3</option>
                                <option value="1.9.2">1.9.2</option>
                                <option value="1.9.1">1.9.1</option>
                                <option value="1.9">1.9</option>
                            </optgroup>
                            <optgroup label="1.8+">
                                <option value="1.8.8">1.8.8</option>
                                <option value="1.8.7">1.8.7</option>
                                <option value="1.8.6">1.8.6</option>
                                <option value="1.8.5">1.8.5</option>
                                <option value="1.8.4">1.8.4</option>
                                <option value="1.8.3">1.8.3</option>
                            </optgroup>
                        </select>
                    </div>

                    <div class="control-section">
                        <div class="control-label">RAM ALLOCATION</div>
                        <input type="range" id="newRamSlider" min="512" max="8192" step="256" value="2048">
                        <div style="color: #aaa; font-size: 0.9em;"><span id="newRamValue">2048</span> MB</div>
                    </div>

                    <button class="btn-primary" onclick="createServer()" style="width: 100%; margin-top: 20px; padding: 15px;">CREATE SERVER</button>
                </div>
            </div>

            <!-- Quick Commands Tab -->
            <div id="commands-tab" class="tab-content" style="display: none;">
                <div class="content-panel">
                    <div class="panel-title">Quick Commands</div>
                    <div id="cmdGrid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px;"></div>
                </div>
            </div>

            <!-- File Manager Tab -->
            <div id="files-tab" class="tab-content" style="display: none;">
                <div class="content-panel">
                    <div class="panel-title">File Manager</div>
                    
                    <div class="control-section">
                        <div class="control-label">SELECT SERVER</div>
                        <select id="fileServerSelect" style="background: #0f3460; border: 1px solid #0f9dff; color: #fff; padding: 10px 15px; border-radius: 6px; width: 100%; margin-bottom: 10px; font-family: inherit;" onchange="loadServerFiles()">
                            <option value="">Choose a server...</option>
                        </select>
                    </div>

                    <div id="fileManager" style="display: none;">
                        <div class="control-section">
                            <div class="control-label">UPLOAD FILES</div>
                            <input type="file" id="fileInput" multiple style="margin-bottom: 10px; color: #aaa;">
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
        let activeServer = null;  // Track which named server is running

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
                document.getElementById('statusText').textContent = online ? 'ONLINE' : 'OFFLINE';
                document.getElementById('allocRam').textContent = d.allocated_ram + ' MB';
                document.getElementById('startBtn').disabled = online;
                document.getElementById('stopBtn').disabled = !online;
                document.getElementById('ramSlider').disabled = online;
            });
        }

        function getSystemInfo() {
            fetch('/api/system-info').then(r => r.json()).then(d => {
                document.getElementById('sysRam').textContent = d.total_ram_gb + ' GB';
                document.getElementById('ramSlider').max = Math.floor(d.total_ram_mb * 0.75);
                document.getElementById('newRamSlider').max = Math.floor(d.total_ram_mb * 0.75);
            });
        }

        function startServer() {
            const ram = document.getElementById('ramSlider').value;
            addLog(`Starting with ${ram}MB...`, 'info');
            fetch('/api/start', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ram: parseInt(ram)})})
                .then(r => r.json()).then(d => {
                    addLog(d.message, d.status === 'success' ? 'success' : 'error');
                    setTimeout(updateStatus, 1000);
                });
        }

        function stopServer() {
            addLog('Stopping...', 'info');
            fetch('/api/stop', {method: 'POST'}).then(r => r.json()).then(d => {
                addLog(d.message, d.status === 'success' ? 'success' : 'error');
                setTimeout(updateStatus, 1000);
            });
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
                });
            document.getElementById('cmdInput').value = '';
        }

        function createServer() {
            const name = document.getElementById('serverName').value.trim();
            const ram = document.getElementById('newRamSlider').value;
            const version = document.getElementById('serverVersion').value;
            if (!name) {
                addLog('Server name required', 'error');
                return;
            }
            addLog(`Creating '${name}' (${version})...`, 'info');
            fetch('/api/build-server', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({server_name: name, ram: parseInt(ram), version: version})})
                .then(r => r.json()).then(d => {
                    addLog(d.message, d.status === 'success' ? 'success' : 'error');
                    document.getElementById('serverName').value = '';
                    loadServers();
                });
        }

        function loadServers() {
            fetch('/api/servers').then(r => r.json()).then(d => {
                const html = d.servers.map(s => `
                    <div class="server-card ${!s.running ? 'offline' : ''}">
                        <div class="server-name">${s.name}</div>
                        <div class="server-info">Version: ${s.version} | RAM: ${s.ram}MB | Port: ${s.port}</div>
                        <div class="server-status">
                            <span class="status-dot" style="background: ${s.building ? '#ff9800' : s.running ? '#00b368' : '#666'};"></span>
                            <span>${s.building ? 'BUILDING' : s.running ? 'ONLINE' : 'OFFLINE'}</span>
                        </div>
                        <button class="btn-primary" onclick="startNamed('${s.name}', ${s.ram})" style="width: 100%; margin-top: 10px;" ${s.running || s.building ? 'disabled' : ''}>START</button>
                        <button class="btn-danger" onclick="stopNamed('${s.name}')" style="width: 100%; margin-top: 5px;" ${!s.running ? 'disabled' : ''}>STOP</button>
                        <button class="btn-primary" onclick="manageServer('${s.name}')" style="width: 100%; margin-top: 5px;">MANAGE</button>
                    </div>
                `).join('');
                document.getElementById('serverList').innerHTML = html || '<div style="color: #aaa;">No servers</div>';
            });
        }

        function startNamed(name, ram) {
            addLog(`Starting '${name}'...`, 'info');
            activeServer = name;
            fetch('/api/start-named', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({server_name: name, ram: parseInt(ram)})})
                .then(r => r.json()).then(d => {
                    addLog(d.message, d.status === 'success' ? 'success' : 'error');
                    setTimeout(loadServers, 1000);
                });
        }

        function stopNamed(name) {
            addLog(`Stopping '${name}'...`, 'info');
            fetch(`/api/stop-named/${name}`, {method: 'POST'})
                .then(r => r.json()).then(d => {
                    addLog(d.message, d.status === 'success' ? 'success' : 'error');
                    if (activeServer === name) activeServer = null;
                    setTimeout(loadServers, 1000);
                });
        }

        function manageServer(name) {
            activeServer = name;
            document.querySelector('[data-tab="console"]').click();
            addLog(`Now managing: ${name}`, 'info');
        }
            const grid = document.getElementById('cmdGrid');
            let html = '';
            for (const [cat, cmds] of Object.entries(COMMANDS)) {
                html += `<div style="grid-column: 1/-1; color: #0f9dff; font-weight: 600; margin-top: 10px;">${cat}</div>`;
                cmds.forEach(c => {
                    html += `<button class="btn-primary" onclick="sendCommand('${c.cmd}')" style="padding: 10px 15px; font-size: 0.85em;">${c.name}</button>`;
                });
            }
            grid.innerHTML = html;
        }

        function sendCommand(cmd) {
            document.getElementById('cmdInput').value = cmd;
            sendCmd();
        }

        document.getElementById('ramSlider').addEventListener('input', e => {
            document.getElementById('ramValue').textContent = e.target.value;
        });
        document.getElementById('newRamSlider').addEventListener('input', e => {
            document.getElementById('newRamValue').textContent = e.target.value;
        });

        getSystemInfo();
        updateStatus();
        loadServers();
        loadServerOptions();
        initCmds();
        setInterval(updateStatus, 2000);
        setInterval(loadServers, 5000);
        setInterval(loadServerOptions, 10000);
        addLog('Ready', 'success');
    </script>
</body>
</html>"""

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=False)
