const fs = window.electronAPI
const IGNORE = new Set(['node_modules', '.git', 'dist', 'build', 'target', '__pycache__', '.idea', '.vscode', 'venv', '.venv', 'out', 'bin', '.gradle', '.mvn'])

// Đọc đệ quy toàn bộ cây — dừng ở maxDepth để tránh quá nặng
export const readTreeRecursive = async(path, depth = 0, maxDepth = 6) => {
  const entries = await readDirSorted(path)
  return Promise.all(entries.map(async entry => {
    if (entry.type === 'dir') {
      const children = depth < maxDepth
        ? await readTreeRecursive(entry.path, depth + 1, maxDepth)
        : null   // null = chưa load, phân biệt với [] = rỗng
      return { ...entry, children, loaded: depth < maxDepth }
    }
    return entry
  }))
}


// Đọc một tầng directory, trả về entries đã sort (dirs trước, files sau)
async function readDirSorted(path) {
  const raw = await fs.readDir(path)
  if (!raw || raw.error || !Array.isArray(raw)) return []
  return raw
    .filter(e => !IGNORE.has(e.name) && !e.name.startsWith('.'))
    .sort((a, b) => {
      if (a.type !== b.type) return a.type === 'dir' ? -1 : 1
      return a.name.localeCompare(b.name)
    })
}
