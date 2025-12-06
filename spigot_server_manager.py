import React, { useState, useEffect } from 'react';
import { Play, Square, Send, Zap, HardDrive, Cpu } from 'lucide-react';

export default function ServerManager() {
  const [running, setRunning] = useState(false);
  const [ram, setRam] = useState(2048);
  const [maxRam, setMaxRam] = useState(8192);
  const [allocatedRam, setAllocatedRam] = useState(0);
  const [command, setCommand] = useState('');
  const [logs, setLogs] = useState(['Server manager ready']);

  useEffect(() => {
    fetchSystemInfo();
    fetchStatus();
    const interval = setInterval(fetchStatus, 2000);
    return () => clearInterval(interval);
  }, []);

  const API_URL = `http://${window.location.hostname}`;

  const fetchSystemInfo = async () => {
    try {
      const res = await fetch(`${API_URL}/api/system-info`);
      const data = await res.json();
      setMaxRam(data.total_ram_mb);
    } catch (e) {
      addLog('Failed to fetch system info', 'error');
    }
  };

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_URL}/api/server-status`);
      const data = await res.json();
      setRunning(data.running);
      setAllocatedRam(data.allocated_ram);
    } catch (e) {
      console.error('Status fetch failed');
    }
  };

  const startServer = async () => {
    addLog(`Starting server with ${ram}MB RAM...`, 'info');
    try {
      const res = await fetch('http://192.168.110.46:5000/api/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ram: parseInt(ram) })
      });
      const data = await res.json();
      addLog(data.message, data.status === 'success' ? 'success' : 'error');
      setTimeout(fetchStatus, 1000);
    } catch (e) {
      addLog('Error starting server', 'error');
    }
  };

  const stopServer = async () => {
    addLog('Stopping server...', 'info');
    try {
      const res = await fetch('http://192.168.110.46:5000/api/stop', {
        method: 'POST'
      });
      const data = await res.json();
      addLog(data.message, data.status === 'success' ? 'success' : 'error');
      setTimeout(fetchStatus, 1000);
    } catch (e) {
      addLog('Error stopping server', 'error');
    }
  };

  const sendCommand = async () => {
    if (!command.trim()) return;
    addLog(`> ${command}`, 'command');
    try {
      const res = await fetch('http://192.168.110.46:5000/api/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command })
      });
      const data = await res.json();
      addLog(data.message, data.status === 'success' ? 'success' : 'error');
      setCommand('');
    } catch (e) {
      addLog('Error sending command', 'error');
    }
  };

  const addLog = (msg, type = 'log') => {
    setLogs(prev => [...prev.slice(-99), { msg, type, id: Date.now() }]);
  };

  const ramPercent = (allocatedRam / maxRam) * 100;
  const cpuPercent = running ? Math.random() * 80 : 0;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-5xl font-bold text-white mb-2">⛏ Server Manager</h1>
          <p className="text-slate-400">Spigot Server Control Panel</p>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          {/* CPU */}
          <div className="bg-gradient-to-br from-red-500/20 to-red-600/10 border border-red-500/30 rounded-xl p-6 backdrop-blur">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-red-200 text-sm font-medium">CPU</p>
                <p className="text-3xl font-bold text-red-400">{cpuPercent.toFixed(0)}%</p>
              </div>
              <Cpu className="text-red-400" size={40} />
            </div>
          </div>

          {/* RAM */}
          <div className="bg-gradient-to-br from-amber-500/20 to-amber-600/10 border border-amber-500/30 rounded-xl p-6 backdrop-blur">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-amber-200 text-sm font-medium">RAM</p>
                <p className="text-3xl font-bold text-amber-400">{ramPercent.toFixed(0)}%</p>
                <p className="text-amber-200 text-xs mt-1">{allocatedRam} MB</p>
              </div>
              <Zap className="text-amber-400" size={40} />
            </div>
          </div>

          {/* Status */}
          <div className={`bg-gradient-to-br ${running ? 'from-green-500/20 to-green-600/10 border-green-500/30' : 'from-slate-500/20 to-slate-600/10 border-slate-500/30'} border rounded-xl p-6 backdrop-blur`}>
            <div className="flex items-center justify-between">
              <div>
                <p className={`${running ? 'text-green-200' : 'text-slate-200'} text-sm font-medium`}>STATUS</p>
                <p className={`text-3xl font-bold ${running ? 'text-green-400' : 'text-slate-400'}`}>
                  {running ? 'ONLINE' : 'OFFLINE'}
                </p>
              </div>
              <div className={`w-12 h-12 rounded-full ${running ? 'bg-green-500 shadow-lg shadow-green-500/50' : 'bg-slate-500'}`}></div>
            </div>
          </div>

          {/* Max RAM */}
          <div className="bg-gradient-to-br from-blue-500/20 to-blue-600/10 border border-blue-500/30 rounded-xl p-6 backdrop-blur">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-blue-200 text-sm font-medium">MAX RAM</p>
                <p className="text-3xl font-bold text-blue-400">{Math.round(maxRam / 1024)}GB</p>
                <p className="text-blue-200 text-xs mt-1">{maxRam} MB</p>
              </div>
              <HardDrive className="text-blue-400" size={40} />
            </div>
          </div>
        </div>

        {/* Control Panel */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - Controls */}
          <div className="lg:col-span-2 space-y-6">
            {/* RAM Allocation */}
            <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-6 backdrop-blur">
              <h2 className="text-xl font-bold text-white mb-4">RAM Allocation</h2>
              <div className="space-y-4">
                <input
                  type="range"
                  min="512"
                  max={Math.floor(maxRam * 0.75)}
                  step="256"
                  value={ram}
                  onChange={(e) => setRam(parseInt(e.target.value))}
                  disabled={running}
                  className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
                />
                <div className="flex justify-between items-center">
                  <span className="text-slate-300">{ram} MB</span>
                  <span className="text-slate-400 text-sm">Max: {Math.floor(maxRam * 0.75)} MB (75%)</span>
                </div>
              </div>
            </div>

            {/* Start/Stop Buttons */}
            <div className="grid grid-cols-2 gap-4">
              <button
                onClick={startServer}
                disabled={running}
                className="bg-gradient-to-r from-green-600 to-green-700 hover:from-green-500 hover:to-green-600 disabled:from-slate-600 disabled:to-slate-700 disabled:opacity-50 text-white font-bold py-4 px-6 rounded-xl flex items-center justify-center gap-2 transition-all duration-200 text-lg"
              >
                <Play size={24} /> START
              </button>
              <button
                onClick={stopServer}
                disabled={!running}
                className="bg-gradient-to-r from-red-600 to-red-700 hover:from-red-500 hover:to-red-600 disabled:from-slate-600 disabled:to-slate-700 disabled:opacity-50 text-white font-bold py-4 px-6 rounded-xl flex items-center justify-center gap-2 transition-all duration-200 text-lg"
              >
                <Square size={24} /> STOP
              </button>
            </div>

            {/* Console */}
            <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-6 backdrop-blur">
              <h2 className="text-xl font-bold text-white mb-4">Console Commands</h2>
              <div className="flex gap-2 mb-4">
                <input
                  type="text"
                  value={command}
                  onChange={(e) => setCommand(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && sendCommand()}
                  placeholder="say Hello World"
                  disabled={!running}
                  className="flex-1 bg-slate-900/50 border border-slate-600 rounded-lg px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                />
                <button
                  onClick={sendCommand}
                  disabled={!running}
                  className="bg-blue-600 hover:bg-blue-500 disabled:bg-slate-600 disabled:opacity-50 text-white font-bold py-3 px-6 rounded-lg flex items-center gap-2 transition-all duration-200"
                >
                  <Send size={20} />
                </button>
              </div>
            </div>
          </div>

          {/* Right Column - Logs */}
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-6 backdrop-blur flex flex-col">
            <h2 className="text-xl font-bold text-white mb-4">Activity Log</h2>
            <div className="flex-1 bg-slate-900/50 rounded-lg p-4 overflow-y-auto font-mono text-sm space-y-2">
              {logs.map((log) => (
                <div
                  key={log.id}
                  className={`${
                    log.type === 'error'
                      ? 'text-red-400'
                      : log.type === 'success'
                      ? 'text-green-400'
                      : log.type === 'command'
                      ? 'text-blue-400'
                      : 'text-slate-300'
                  }`}
                >
                  {log.msg}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
