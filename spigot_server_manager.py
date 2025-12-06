#!/usr/bin/env python3
"""
Spigot Server Manager with Modern Web UI
Run: sudo python3 server_manager.py
"""

from flask import Flask, render_template_string, request, jsonify
from flask_cors import CORS
import psutil
import subprocess
import os

app = Flask(__name__)
CORS(app)

# Configuration
SERVER_DIR = os.path.expanduser("~/mcserver")
SPIGOT_JAR = "server.jar"
server_process = None
allocated_ram = 2048

def get_system_info():
    """Get available system RAM"""
    total_ram = psutil.virtual_memory().total // (1024**3)
    return {"total_ram_gb": total_ram, "total_ram_mb": total_ram * 1024}

def start_server(ram_mb):
    """Start Spigot server with specified RAM"""
    global server_process, allocated_ram
    
    if server_process and server_process.poll() is None:
        return {"status": "error", "message": "Server already running"}
    
    allocated_ram = ram_mb
    cmd = [
        "java",
        f"-Xmx{ram_mb}M",
        f"-Xms{ram_mb//2}M",
        "-jar",
        SPIGOT_JAR,
        "nogui"
    ]
    
    try:
        os.chdir(SERVER_DIR)
        server_process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        return {"status": "success", "message": f"Server starting with {ram_mb}MB RAM"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def stop_server():
    """Stop the server gracefully"""
    global server_process
    
    if not server_process or server_process.poll() is not None:
        return {"status": "error", "message": "Server not running"}
    
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

def run_command(cmd):
    """Run a Minecraft command on the server"""
    global server_process
    
    if not server_process or server_process.poll() is not None:
        return {"status": "error", "message": "Server not running"}
    
    try:
        server_process.stdin.write(cmd + "\n")
        server_process.stdin.flush()
        return {"status": "success", "message": f"Command executed: {cmd}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def is_server_running():
    """Check if server is running"""
    global server_process
    return server_process is not None and server_process.poll() is None

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/system-info')
def api_system_info():
    return jsonify(get_system_info())

@app.route('/api/server-status')
def api_server_status():
    return jsonify({
        "running": is_server_running(),
        "allocated_ram": allocated_ram
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

HTML_TEMPLATE = '''<!DOCTYPE html>
<html>
<head>
    <title>Server Manager</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: #fff;
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { margin-bottom: 30px; }
        .header h1 { font-size: 2.5em; margin-bottom: 5px; }
        .header p { color: #94a3b8; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-box {
            background: rgba(30, 41, 59, 0.8);
            border: 1px solid rgba(148, 163, 184, 0.2);
            border-radius: 12px;
            padding: 24px;
            backdrop-filter: blur(10px);
        }
        .stat-label { font-size: 0.875em; color: #94a3b8; margin-bottom: 8px; font-weight: 600; }
        .stat-value { font-size: 2.5em; font-weight: bold; margin-bottom: 5px; }
        .stat-sub { font-size: 0.875em; color: #64748b; }
        .main-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 20px; }
        .panel {
            background: rgba(30, 41, 59, 0.8);
            border: 1px solid rgba(148, 163, 184, 0.2);
            border-radius: 12px;
            padding: 24px;
            backdrop-filter: blur(10px);
        }
        .panel h2 { font-size: 1.25em; margin-bottom: 20px; }
        .slider-group { margin-bottom: 20px; }
        .slider-label { font-size: 0.875em; color: #94a3b8; margin-bottom: 10px; display: block; }
        input[type="range"] {
            width: 100%;
            height: 6px;
            border-radius: 3px;
            background: rgba(100, 116, 139, 0.3);
            outline: none;
            -webkit-appearance: none;
        }
        input[type="range"]::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 18px;
            height: 18px;
            border-radius: 50%;
            background: #3b82f6;
            cursor: pointer;
        }
        input[type="range"]::-moz-range-thumb {
            width: 18px;
            height: 18px;
            border-radius: 50%;
            background: #3b82f6;
            cursor: pointer;
            border: none;
        }
        .button-group { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 20px; }
        button {
            padding: 12px 20px;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            font-size: 1em;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn-start {
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            color: white;
        }
        .btn-start:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 8px 16px rgba(16, 185, 129, 0.3); }
        .btn-start:disabled { opacity: 0.5; cursor: not-allowed; }
        .btn-stop {
            background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
            color: white;
        }
        .btn-stop:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 8px 16px rgba(239, 68, 68, 0.3); }
        .btn-stop:disabled { opacity: 0.5; cursor: not-allowed; }
        .command-group { display: flex; gap: 12px; margin-bottom: 20px; }
        input[type="text"] {
            flex: 1;
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid rgba(148, 163, 184, 0.2);
            border-radius: 8px;
            padding: 10px 14px;
            color: white;
            font-family: 'Monaco', monospace;
        }
        input[type="text"]:focus { outline: none; border-color: #3b82f6; box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1); }
        .btn-send {
            background: #3b82f6;
            color: white;
            padding: 10px 20px;
        }
        .btn-send:hover:not(:disabled) { background: #2563eb; }
        .btn-send:disabled { opacity: 0.5; cursor: not-allowed; }
        .log-box {
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid rgba(148, 163, 184, 0.2);
            border-radius: 8px;
            padding: 14px;
            height: 300px;
            overflow-y: auto;
            font-family: 'Monaco', monospace;
            font-size: 0.875em;
        }
        .log-entry { margin: 4px 0; line-height: 1.4; }
        .log-error { color: #f87171; }
        .log-success { color: #86efac; }
        .log-command { color: #60a5fa; }
        .log-info { color: #cbd5e1; }
        .status-badge {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .status-online { background: #10b981; box-shadow: 0 0 8px #10b981; }
        .status-offline { background: #6b7280; }
        @media (max-width: 768px) { .main-grid { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Server Manager</h1>
            <p>Spigot Server Control Panel</p>
        </div>

        <div class="grid">
            <div class="stat-box">
                <div class="stat-label">STATUS</div>
                <div class="stat-value"><span class="status-badge" id="statusBadge"></span><span id="statusText">OFFLINE</span></div>
            </div>
            <div class="stat-box">
                <div class="stat-label">ALLOCATED RAM</div>
                <div class="stat-value" id="allocatedRam">0 MB</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">SYSTEM RAM</div>
                <div class="stat-value" id="systemRam">-</div>
                <div class="stat-sub">Available</div>
            </div>
        </div>

        <div class="main-grid">
            <div>
                <div class="panel">
                    <h2>RAM Allocation</h2>
                    <div class="slider-group">
                        <label class="slider-label">Select RAM Amount</label>
                        <input type="range" id="ramSlider" min="512" max="8192" step="256" value="2048" disabled>
                        <div style="margin-top: 12px; color: #94a3b8; font-size: 0.875em;">
                            <span id="ramValue">2048</span> MB / <span id="ramMax">8192</span> MB
                        </div>
                    </div>
                </div>

                <div class="panel" style="margin-top: 20px;">
                    <h2>Server Control</h2>
                    <div class="button-group">
                        <button class="btn-start" id="startBtn" onclick="startServer()">START</button>
                        <button class="btn-stop" id="stopBtn" onclick="stopServer()">STOP</button>
                    </div>
                </div>

                <div class="panel" style="margin-top: 20px;">
                    <h2>Console</h2>
                    <div class="command-group">
                        <input type="text" id="commandInput" placeholder="say Hello" onkeypress="if(event.key==='Enter') sendCommand()">
                        <button class="btn-send" onclick="sendCommand()">SEND</button>
                    </div>
                </div>
            </div>

            <div class="panel">
                <h2>Activity Log</h2>
                <div class="log-box" id="logBox"></div>
            </div>
        </div>
    </div>

    <script>
        let logs = [];
        
        function updateStatus() {
            fetch('/api/server-status')
                .then(r => r.json())
                .then(data => {
                    const badge = document.getElementById('statusBadge');
                    const statusText = document.getElementById('statusText');
                    const startBtn = document.getElementById('startBtn');
                    const stopBtn = document.getElementById('stopBtn');
                    const ramSlider = document.getElementById('ramSlider');
                    
                    if (data.running) {
                        badge.className = 'status-badge status-online';
                        statusText.textContent = 'ONLINE';
                        startBtn.disabled = true;
                        stopBtn.disabled = false;
                        ramSlider.disabled = true;
                    } else {
                        badge.className = 'status-badge status-offline';
                        statusText.textContent = 'OFFLINE';
                        startBtn.disabled = false;
                        stopBtn.disabled = true;
                        ramSlider.disabled = false;
                    }
                    document.getElementById('allocatedRam').textContent = data.allocated_ram + ' MB';
                });
        }

        function getSystemInfo() {
            fetch('/api/system-info')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('systemRam').textContent = data.total_ram_gb + ' GB';
                    document.getElementById('ramMax').textContent = data.total_ram_mb;
                    document.getElementById('ramSlider').max = Math.floor(data.total_ram_mb * 0.75);
                });
        }

        function startServer() {
            const ram = document.getElementById('ramSlider').value;
            addLog('Starting server with ' + ram + ' MB...', 'info');
            fetch('/api/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ram: parseInt(ram)})
            })
            .then(r => r.json())
            .then(data => {
                addLog(data.message, data.status === 'success' ? 'success' : 'error');
                setTimeout(updateStatus, 1000);
            });
        }

        function stopServer() {
            addLog('Stopping server...', 'info');
            fetch('/api/stop', {method: 'POST'})
                .then(r => r.json())
                .then(data => {
                    addLog(data.message, data.status === 'success' ? 'success' : 'error');
                    setTimeout(updateStatus, 1000);
                });
        }

        function sendCommand() {
            const input = document.getElementById('commandInput');
            const cmd = input.value.trim();
            if (!cmd) return;
            addLog('> ' + cmd, 'command');
            fetch('/api/command', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({command: cmd})
            })
            .then(r => r.json())
            .then(data => {
                addLog(data.message, data.status === 'success' ? 'success' : 'error');
            });
            input.value = '';
        }

        function addLog(msg, type = 'log') {
            logs.push({msg, type});
            if (logs.length > 100) logs.shift();
            const logBox = document.getElementById('logBox');
            logBox.innerHTML = logs.map(l => `<div class="log-entry log-${l.type}">${l.msg}</div>`).join('');
            logBox.scrollTop = logBox.scrollHeight;
        }

        document.getElementById('ramSlider').addEventListener('input', (e) => {
            document.getElementById('ramValue').textContent = e.target.value;
        });

        getSystemInfo();
        updateStatus();
        setInterval(updateStatus, 2000);
        addLog('Server manager ready', 'success');
    </script>
</body>
</html>'''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=False)
