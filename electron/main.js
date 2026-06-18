const { app, BrowserWindow, ipcMain, dialog } = require('electron')
const path = require('path')
const fs = require('fs')
const { spawn } = require('child_process')

const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged

let mainWindow
let pythonProcess

// ─── Khởi động Python backend ────────────────────────────────────────────────
function startPythonServer() {
  const pythonPath = isDev
    ? path.join(__dirname, '../python/server.py')
    : path.join(process.resourcesPath, 'python/server.py')

  const pythonExe = process.platform === 'win32' ? 'python' : 'python3'
  pythonProcess = spawn(pythonExe, [pythonPath], {
    cwd: path.dirname(pythonPath),
    stdio: ['pipe', 'pipe', 'pipe']
  })

  pythonProcess.stdout.on('data', (data) => {
    console.log('[Python]', data.toString())
  })
  pythonProcess.stderr.on('data', (data) => {
    console.error('[Python Error]', data.toString())
  })
  pythonProcess.on('close', (code) => {
    console.log(`[Python] exited with code ${code}`)
  })
}

// ─── Tạo main window ─────────────────────────────────────────────────────────
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 900,
    minHeight: 600,
    titleBarStyle: 'hiddenInset',
    backgroundColor: '#0f0f0f',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  })

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools()
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
  }
}

app.whenReady().then(() => {
  startPythonServer()
  createWindow()
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (pythonProcess) pythonProcess.kill()
  if (process.platform !== 'darwin') app.quit()
})

// ─── IPC Handlers — Filesystem ───────────────────────────────────────────────

// Đọc directory tree
ipcMain.handle('fs:readdir', async (_, dirPath) => {
  try {
    const entries = fs.readdirSync(dirPath, { withFileTypes: true })
    return entries.map(e => ({
      name: e.name,
      type: e.isDirectory() ? 'dir' : 'file',
      path: path.join(dirPath, e.name),
      ext: e.isFile() ? path.extname(e.name) : null
    }))
  } catch (err) {
    return { error: err.message }
  }
})

// Đọc nội dung file
ipcMain.handle('fs:readfile', async (_, filePath) => {
  try {
    const stat = fs.statSync(filePath)
    if (stat.size > 2 * 1024 * 1024) {
      return { error: 'File quá lớn (> 2MB)' }
    }
    const content = fs.readFileSync(filePath, 'utf-8')
    return { content, size: stat.size, mtime: stat.mtime }
  } catch (err) {
    return { error: err.message }
  }
})

// Ghi file
ipcMain.handle('fs:writefile', async (_, filePath, content) => {
  try {
    fs.mkdirSync(path.dirname(filePath), { recursive: true })
    fs.writeFileSync(filePath, content, 'utf-8')
    return { success: true }
  } catch (err) {
    return { error: err.message }
  }
})

// Tạo file mới
ipcMain.handle('fs:createfile', async (_, filePath, content = '') => {
  try {
    if (fs.existsSync(filePath)) return { error: 'File đã tồn tại' }
    fs.mkdirSync(path.dirname(filePath), { recursive: true })
    fs.writeFileSync(filePath, content, 'utf-8')
    return { success: true }
  } catch (err) {
    return { error: err.message }
  }
})

// Tạo thư mục
ipcMain.handle('fs:mkdir', async (_, dirPath) => {
  try {
    fs.mkdirSync(dirPath, { recursive: true })
    return { success: true }
  } catch (err) {
    return { error: err.message }
  }
})

// Dialog chọn thư mục
ipcMain.handle('fs:selectdir', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory']
  })
  return result.canceled ? null : result.filePaths[0]
})

// Lấy path info
ipcMain.handle('fs:stat', async (_, filePath) => {
  try {
    const stat = fs.statSync(filePath)
    return {
      exists: true,
      isDir: stat.isDirectory(),
      size: stat.size,
      mtime: stat.mtime
    }
  } catch {
    return { exists: false }
  }
})
