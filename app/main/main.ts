import { app, BrowserWindow, ipcMain } from 'electron'
import path from 'path'
import net from 'net'
import { spawn, exec, ChildProcessWithoutNullStreams } from 'child_process'
import http from 'http'
import https from 'https'
import fs from 'fs'
import os from 'os'

let mainWindow: BrowserWindow | null = null
let backendProcess: ChildProcessWithoutNullStreams | null = null
let apiPort = 8000

function getAvailablePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = net.createServer()
    server.unref()
    server.on('error', reject)
    server.listen(0, () => {
      const address = server.address()
      const port = typeof address === 'object' && address ? address.port : 0
      server.close(() => resolve(port))
    })
  })
}

function checkUrlReady(url: string, retries = 30): Promise<void> {
  return new Promise((resolve, reject) => {
    const check = (currentRetry: number) => {
      http.get(url, (res) => {
        if (res.statusCode === 200 || res.statusCode === 404) {
          resolve() // 404 is fine for an API root, means the server is running
        } else {
          retryOrReject(currentRetry)
        }
      }).on('error', () => {
        retryOrReject(currentRetry)
      })
    }

    const retryOrReject = (currentRetry: number) => {
      if (currentRetry >= retries) {
        reject(new Error(`Service at ${url} not ready`))
      } else {
        setTimeout(() => check(currentRetry + 1), 1000)
      }
    }

    check(0)
  })
}

async function startBackend(): Promise<boolean> {
  try {
    apiPort = await getAvailablePort()
    console.log(`Starting backend on port ${apiPort}`)

    const isPackaged = app.isPackaged

    let command: string
    let args: string[]

    if (isPackaged) {
      command = path.join(process.resourcesPath, 'backend.exe')
      args = []
    } else {
      command = path.join(__dirname, '..', '..', '..', 'venv_desktop', 'Scripts', 'python.exe')
      if (process.platform === 'darwin') {
        command = path.join(__dirname, '..', '..', '..', 'venv_desktop', 'bin', 'python')
        if (!fs.existsSync(command)) {
          command = path.join(__dirname, '..', '..', '..', '.venv', 'bin', 'python')
          if (!fs.existsSync(command)) command = 'python3'
        }
      }
      args = [path.join(__dirname, '..', '..', '..', 'engine', 'main.py')]
    }

    backendProcess = spawn(command, args, {
      env: { ...process.env, API_PORT: apiPort.toString() }
    }) as ChildProcessWithoutNullStreams

    backendProcess.stdout.on('data', (data) => console.log(`[Backend]: ${data.toString()}`))
    backendProcess.stderr.on('data', (data) => console.error(`[Backend ERR]: ${data.toString()}`))

    backendProcess.on('close', (code) => {
      console.log(`Backend process exited with code ${code}`)
    })

    await checkUrlReady(`http://127.0.0.1:${apiPort}/docs`)
    console.log('Backend is ready!')
    return true
  } catch (err) {
    console.error('Failed to start backend:', err)
    return false
  }
}

function checkOllamaInstall(): Promise<boolean> {
  return new Promise((resolve) => {
    exec('ollama --version', (err) => {
      if (err) resolve(false)
      else resolve(true)
    })
  })
}

function installOllama(): Promise<boolean> {
  return new Promise((resolve, reject) => {
    if (process.platform !== 'win32') {
      reject(new Error('Auto-install is only supported on Windows. Please install Ollama manually from ollama.com'))
      return
    }

    const installerPath = path.join(os.tmpdir(), 'OllamaSetup.exe')
    const file = fs.createWriteStream(installerPath)

    https.get('https://ollama.com/download/OllamaSetup.exe', (response) => {
      response.pipe(file)
      file.on('finish', () => {
        file.close(() => {
          console.log('Downloaded Ollama installer. Running silent install...')
          if (mainWindow) mainWindow.webContents.send('setup-status', 'Installing Ollama AI Engine... (Admin prompt may appear)')

          exec(`"${installerPath}" /S`, (err) => {
            if (err) {
              console.error('Silent install failed, manual install required.')
              reject(new Error('Silent install failed. Manual install required.'))
            } else {
              resolve(true)
            }
          })
        })
      })
    }).on('error', (err) => {
      fs.unlink(installerPath, () => {})
      reject(err)
    })
  })
}

function checkModel(): Promise<boolean> {
  return new Promise((resolve) => {
    exec('ollama list', (err, stdout) => {
      if (err) return resolve(false)
      if (stdout.includes('llama3')) resolve(true)
      else resolve(false)
    })
  })
}

function pullModel(): Promise<boolean> {
  return new Promise((resolve, reject) => {
    const pullProcess = spawn('ollama', ['pull', 'llama3'])

    pullProcess.stdout.on('data', (data) => {
      if (mainWindow) mainWindow.webContents.send('setup-status', `Downloading AI Model: ${data.toString().trim()}`)
    })

    pullProcess.stderr.on('data', (data) => {
      const output = data.toString().trim()
      if (output && mainWindow) mainWindow.webContents.send('setup-status', `Downloading AI Model: ${output}`)
    })

    pullProcess.on('close', (code) => {
      if (code === 0) resolve(true)
      else reject(new Error('Failed to pull llama3 model'))
    })
  })
}

async function runSetupSequence(): Promise<void> {
  const isDev = !app.isPackaged
  if (!mainWindow) return

  if (isDev) {
    // In dev mode: backend is already started by start-backend.js on port 8000
    // Just wait for it to be ready, then signal complete
    try {
      mainWindow.webContents.send('setup-status', 'Connecting to dev backend...')
      await checkUrlReady('http://127.0.0.1:8000', 30)
      apiPort = 8000
      mainWindow.webContents.send('setup-complete', { apiPort })
    } catch (err) {
      mainWindow.webContents.send('setup-error', 'Backend not ready. Make sure npm run dev-backend is running. ' + (err as Error).message)
    }
    return
  }

  // Production mode: full setup sequence
  try {
    mainWindow.webContents.send('setup-status', 'Checking AI environment...')
    const hasOllama = await checkOllamaInstall()

    if (!hasOllama) {
      mainWindow.webContents.send('setup-status', 'Downloading Ollama AI Engine...')
      await installOllama()
    }

    mainWindow.webContents.send('setup-status', 'Verifying LLM Model availability...')
    const hasModel = await checkModel()
    if (!hasModel) {
      await pullModel()
    }

    mainWindow.webContents.send('setup-status', 'Waiting for AI Service (localhost:11434)...')
    await checkUrlReady('http://127.0.0.1:11434', 10)

    mainWindow.webContents.send('setup-status', 'Starting Application Backend...')
    const backendReady = await startBackend()

    if (!backendReady) throw new Error('Backend failed to start')

    mainWindow.webContents.send('setup-complete', { apiPort })
  } catch (err) {
    mainWindow.webContents.send('setup-error', (err as Error).message)
  }
}

function waitForVite(url: string, retries = 30): Promise<void> {
  return new Promise((resolve, reject) => {
    const check = (remaining: number) => {
      http.get(url, () => {
        resolve()
      }).on('error', () => {
        if (remaining <= 0) {
          reject(new Error('Vite dev server did not start in time'))
        } else {
          setTimeout(() => check(remaining - 1), 500)
        }
      })
    }
    check(retries)
  })
}

// Preserves the exact same (weak, "gating not auth") domain-allowlist check that
// used to read window.process directly in the renderer — relocated here because
// contextIsolation removes the renderer's Node access, not upgraded.
ipcMain.handle('get-user-context', () => {
  let username = ''
  try {
    username = os.userInfo().username
  } catch {
    // best-effort, matches the old renderer-side try/catch around window.require('os').userInfo()
  }
  return {
    platform: process.platform,
    userDomain: process.env.USERDOMAIN || '',
    username,
  }
})

ipcMain.handle('get-app-version', () => app.getVersion())

async function createWindow(): Promise<void> {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    show: false, // Don't show until ready
    webPreferences: {
      preload: path.join(__dirname, '..', 'bridge', 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    }
  })

  let startUrl = process.env.ELECTRON_START_URL || 'http://127.0.0.1:5173'
  if (app.isPackaged) {
    const indexPath = path.join(__dirname, '..', '..', 'renderer', 'dist', 'index.html')
    startUrl = `file://${indexPath}`
  }

  // In dev mode, wait for Vite to be ready before loading
  if (!app.isPackaged) {
    try {
      console.log('Waiting for Vite dev server...')
      await waitForVite('http://127.0.0.1:5173')
      console.log('Vite is ready!')
    } catch (e) {
      console.error('Could not connect to Vite:', (e as Error).message)
    }
  }

  mainWindow.loadURL(startUrl)

  // Show window only after page has loaded (no white flash)
  mainWindow.webContents.on('did-finish-load', () => {
    mainWindow?.show()
    runSetupSequence()
  })

  mainWindow.on('closed', function () {
    mainWindow = null
    if (backendProcess) {
      backendProcess.kill()
    }
  })
}

app.whenReady().then(() => {
  createWindow()
})

app.on('window-all-closed', function () {
  if (process.platform !== 'darwin') {
    app.quit()
  }
  if (backendProcess) {
    backendProcess.kill()
  }
})

app.on('activate', function () {
  if (mainWindow === null) {
    createWindow()
  }
})
