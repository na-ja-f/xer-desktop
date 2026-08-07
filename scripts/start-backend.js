const path = require('path');
const os = require('os');
const fs = require('fs');
const { spawn, execSync } = require('child_process');
const net = require('net');

const isWindows = os.platform() === 'win32';
const backendDir = path.join(__dirname, '..', 'engine');
const PORT = 8000;

const pythonPath = isWindows 
  ? path.join(__dirname, '..', 'venv_desktop', 'Scripts', 'python.exe')
  : path.join(__dirname, '..', 'venv_desktop', 'bin', 'python3');

function killPort(port) {
  try {
    if (isWindows) {
      // Windows: find PID using netstat and kill it
      const result = execSync(`netstat -ano | findstr :${port}`, { encoding: 'utf8' }).trim();
      const lines = result.split('\n');
      const pids = new Set();
      lines.forEach(line => {
        const parts = line.trim().split(/\s+/);
        const pid = parts[parts.length - 1];
        if (pid && !isNaN(pid)) pids.add(pid);
      });
      pids.forEach(pid => {
        try { execSync(`taskkill /F /PID ${pid}`, { stdio: 'ignore' }); } catch(e) {}
      });
    } else {
      // Mac/Linux
      execSync(`lsof -ti tcp:${port} | xargs kill -9`, { stdio: 'ignore' });
    }
    console.log(`Killed stale process on port ${port}`);
  } catch (e) {
    // Port was free - that's fine
  }
}

function isPortFree(port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once('error', () => resolve(false));
    server.once('listening', () => { server.close(); resolve(true); });
    server.listen(port);
  });
}

async function start() {
  console.log(`--- Backend Diagnostic Start ---`);
  console.log(`Platform: ${os.platform()}`);
  console.log(`Current Dir: ${process.cwd()}`);
  console.log(`Backend Dir: ${backendDir}`);
  console.log(`Python Path: ${pythonPath}`);
  console.log(`Python Exists: ${fs.existsSync(pythonPath)}`);
  console.log(`--------------------------------`);

  const free = await isPortFree(PORT);
  if (!free) {
    console.log(`Port ${PORT} is in use — killing stale process...`);
    killPort(PORT);
    // Give OS time to release the port
    await new Promise(r => setTimeout(r, 1500));
  }

  const exe = fs.existsSync(pythonPath) ? pythonPath : (isWindows ? 'python' : 'python3');
  spawnBackend(exe);
}

function spawnBackend(exe) {
  console.log(`Spawning uvicorn with: ${exe} on port ${PORT}`);
  const backend = spawn(exe, ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', String(PORT), '--reload'], {
    cwd: backendDir,
    stdio: 'pipe',
    shell: isWindows 
  });

  backend.stdout.on('data', (data) => process.stdout.write(`[Backend-Out]: ${data}`));
  backend.stderr.on('data', (data) => process.stderr.write(`[Backend-Err]: ${data}`));
  backend.on('error', (err) => console.error('CRITICAL: Failed to start backend spawn:', err));
  backend.on('exit', (code) => {
    console.log(`Backend process exited with code ${code}`);
    if (code !== 0) console.error(`Backend exited with error. Check logs above.`);
  });
}

start();
