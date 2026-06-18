const { contextBridge, ipcRenderer } = require('electron')

// Expose filesystem API an toàn qua context bridge
contextBridge.exposeInMainWorld('electronAPI', {
  // Filesystem
  readDir:    (path)          => ipcRenderer.invoke('fs:readdir', path),
  readFile:   (path)          => ipcRenderer.invoke('fs:readfile', path),
  writeFile:  (path, content) => ipcRenderer.invoke('fs:writefile', path, content),
  createFile: (path, content) => ipcRenderer.invoke('fs:createfile', path, content),
  mkdir:      (path)          => ipcRenderer.invoke('fs:mkdir', path),
  selectDir:  ()              => ipcRenderer.invoke('fs:selectdir'),
  stat:       (path)          => ipcRenderer.invoke('fs:stat', path),

  // Platform info
  platform: process.platform,
  sep: process.platform === 'win32' ? '\\' : '/'
})
