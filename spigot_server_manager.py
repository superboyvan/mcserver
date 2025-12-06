#!/usr/bin/env python3
"""
Spigot Server Manager with Minecraft-style UI
Run: python3 server_manager.py
"""

from flask import Flask, render_template_string, request, jsonify
from flask_cors import CORS
import psutil
import subprocess
import os
import json

app = Flask(__name__)
CORS(app)

# Configuration
SERVER_DIR = "/mcserver"  # Your Spigot server directory
SPIGOT_JAR = "server.jar"
server_process = None
allocated_ram = 2048  # Default 2GB

def get_system_info():
    """Get available system RAM"""
    total_ram = psutil.virtual_memory().total // (1024**3)  # Convert to GB
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

# Routes
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

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Spigot Server Manager</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Minecraft', 'Arial', sans-serif;
            background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
            color: #fff;
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: #121212;
            border: 3px solid #00aa00;
            border-radius: 4px;
            box-shadow: 0 0 20px rgba(0, 170, 0, 0.3);
            padding: 20px;
        }
        
        .header {
            text-align: center;
            margin-bottom: 30px;
            border-bottom: 2px solid #00aa00;
            padding-bottom: 15px;
        }
        
        .header h1 {
            font-size: 2.5em;
            color: #00ff00;
            text-shadow: 2px 2px 4px #000;
            letter-spacing: 2px;
        }
        
        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .panel {
            background: #1a1a1a;
            border: 2px solid #00aa00;
            padding: 15px;
            border-radius: 3px;
        }
        
        .panel h2 {
            color: #00ff00;
            margin-bottom: 15px;
            font-size: 1.3em;
        }
        
        .info-item {
            margin: 10px 0;
            padding: 8px;
            background: #0d0d0d;
            border-left: 3px solid #00aa00;
            border-radius: 2px;
        }
        
        .info-label {
            color: #00aa00;
            font-weight: bold;
        }
        
        .info-value {
            color: #fff;
            margin-left: 10px;
        }
        
        .slider-container {
            margin: 15px 0;
        }
        
        input[type="range"] {
            width: 100%;
            height: 8px;
            border-radius: 3px;
            background: #0d0d0d;
            outline: none;
            -webkit-appearance: none;
        }
        
        input[type="range"]::-webkit-slider-thumb {
            -webkit-appearance: none;
            appearance: none;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            background: #00ff00;
            cursor: pointer;
            box-shadow: 0 0 5px #00aa00;
        }
        
        input[type="range"]::-moz-range-thumb {
            width: 20px;
            height: 20px;
            border-radius: 50%;
            background: #00ff00;
            cursor: pointer;
            border: none;
            box-shadow: 0 0 5px #00aa00;
        }
        
        .button-group {
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }
        
        button {
            flex: 1;
            padding: 12px;
            font-size: 1em;
            border: 2px solid #00aa00;
            background: #0d0d0d;
            color: #00ff00;
            cursor: pointer;
            border-radius: 3px;
            font-weight: bold;
            transition: all 0.2s;
        }
        
        button:hover {
            background: #00aa00;
            color: #000;
            box-shadow: 0 0 10px #00ff00;
        }
        
        button:active {
            transform: scale(0.98);
        }
        
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }
        
        .status-online {
            background: #00ff00;
            box-shadow: 0 0 8px #00ff00;
        }
        
        .status-offline {
            background: #ff0000;
            box-shadow: 0 0 8px #ff0000;
        }
        
        .command-section {
            grid-column: 1 / -1;
        }
        
        .command-input-group {
            display: flex;
            gap: 10px;
            margin-bottom: 10px;
        }
        
        input[type="text"] {
            flex: 1;
            padding: 10px;
            background: #0d0d0d;
            border: 2px solid #00aa00;
            color: #fff;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }
        
        input[type="text"]:focus {
            outline: none;
            box-shadow: 0 0 8px #00aa00;
        }
        
        .command-send {
            padding: 10px 20px;
        }
        
        .log-box {
            background: #0d0d0d;
            border: 2px solid #00aa00;
            padding: 10px;
            border-radius: 3px;
            height: 150px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }
        
        .log-entry {
            color: #00ff00;
            margin: 2px 0;
        }
        
        .log-error {
            color: #ff5555;
        }
        
        .log-success {
            color: #55ff55;
        }
        
        @media (max-width: 768px) {
            .grid {
                grid-template-columns: 1fr;
            }
            .command-section {
                grid-column: 1;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⛏ Spigot Server Manager</h1>
        </div>
        
        <div class="grid">
            <div class="panel">
                <h2>Server Status</h2>
                <div class="info-item">
                    <span class="info-label">Status:</span>
                    <span class="status-indicator" id="statusIndicator"></span>
                    <span id="statusText">Checking...</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Allocated RAM:</span>
                    <span class="info-value" id="allocatedRam">0 MB</span>
                </div>
                <div class="slider-container">
                    <label class="info-label">RAM Allocation:</label>
                    <input type="range" id="ramSlider" min="512" max="8192" step="256" value="2048">
                    <div style="margin-top: 8px; color: #00aa00;">
                        <span id="ramValue">2048</span> MB
                    </div>
                </div>
            </div>
            
            <div class="panel">
                <h2>System Info</h2>
                <div class="info-item">
                    <span class="info-label">Available RAM:</span>
                    <span class="info-value" id="systemRam">Loading...</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Recommended:</span>
                    <span class="info-value">50-75% of total</span>
                </div>
                <div class="button-group" style="margin-top: 20px;">
                    <button id="startBtn" onclick="startServer()">START</button>
                    <button id="stopBtn" onclick="stopServer()">STOP</button>
                </div>
            </div>
            
            <div class="panel command-section">
                <h2>Console Commands</h2>
                <div class="command-input-group">
                    <input type="text" id="commandInput" placeholder="Enter command (e.g., say Hello)" onkeypress="handleKeyPress(event)">
                    <button class="command-send" onclick="sendCommand()">SEND</button>
                </div>
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
                    const indicator = document.getElementById('statusIndicator');
                    const statusText = document.getElementById('statusText');
                    const startBtn = document.getElementById('startBtn');
                    const stopBtn = document.getElementById('stopBtn');
                    const ramSlider = document.getElementById('ramSlider');
                    
                    if (data.running) {
                        indicator.className = 'status-indicator status-online';
                        statusText.textContent = 'ONLINE';
                        startBtn.disabled = true;
                        stopBtn.disabled = false;
                        ramSlider.disabled = true;
                    } else {
                        indicator.className = 'status-indicator status-offline';
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
                    const max = data.total_ram_mb;
                    document.getElementById('systemRam').textContent = data.total_ram_gb + ' GB (' + max + ' MB)';
                    document.getElementById('ramSlider').max = Math.floor(max * 0.75);
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
            
            addLog('> ' + cmd, 'info');
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
            logBox.innerHTML = logs.map(l => 
                `<div class="log-entry ${l.type === 'error' ? 'log-error' : l.type === 'success' ? 'log-success' : ''}">${l.msg}</div>`
            ).join('');
            logBox.scrollTop = logBox.scrollHeight;
        }
        
        function handleKeyPress(e) {
            if (e.key === 'Enter') sendCommand();
        }
        
        document.getElementById('ramSlider').addEventListener('input', (e) => {
            document.getElementById('ramValue').textContent = e.target.value;
        });
        
        // Initial setup
        getSystemInfo();
        updateStatus();
        setInterval(updateStatus, 2000);
        addLog('Server manager ready', 'success');
    </script>
</body>
</html>
'''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
