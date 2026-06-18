import React, { useState, useCallback } from 'react'
import { useAppStore } from '../store/appStore'

const fs = window.electronAPI

const EXT_ICON = {
  '.java': '☕', '.py': '🐍', '.js': '📜', '.ts': '📘',
  '.tsx': '⚛️', '.jsx': '⚛️', '.xml': '📋', '.yml': '⚙️',
  '.yaml': '⚙️', '.json': '{}', '.sql': '🗄️', '.md': '📝',
  '.gradle': '🐘', '.sh': '💲', '.html': '🌐', '.css': '🎨',
  '.kt': '🦊', '.properties': '⚙️',
}

function getIcon(name, isDir) {
  if (isDir) return null
  const ext = '.' + name.split('.').pop()
  return EXT_ICON[ext] || '📄'
}

function TreeNode({ node, depth = 0, onFileClick }) {
  const [expanded, setExpanded] = useState(depth < 2)
  const { activeFilePath } = useAppStore()
  const isActive = activeFilePath === node.path
  const isDir = node.type === 'dir'

  const style = {
    paddingLeft: `${12 + depth * 14}px`,
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    padding: `4px 8px 4px ${12 + depth * 14}px`,
    cursor: 'pointer',
    borderRadius: 'var(--radius-sm)',
    color: isActive ? 'var(--accent)' : isDir ? 'var(--text-1)' : 'var(--text-2)',
    background: isActive ? 'var(--accent-dim)' : 'transparent',
    fontSize: 12,
    userSelect: 'none',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  }

  const handleClick = useCallback(() => {
    if (isDir) {
      setExpanded(e => !e)
    } else {
      onFileClick(node)
    }
  }, [isDir, node, onFileClick])

  return (
    <>
      <div style={style} onClick={handleClick}
        onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = 'var(--bg-hover)' }}
        onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = 'transparent' }}
      >
        <span style={{ fontSize: 11, width: 14, flexShrink: 0 }}>
          {isDir ? (expanded ? '▾' : '▸') : getIcon(node.name, false)}
        </span>
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{node.name}</span>
      </div>

      {isDir && expanded && node.children?.map(child => (
        <TreeNode key={child.path} node={child} depth={depth + 1} onFileClick={onFileClick} />
      ))}
    </>
  )
}

export default function Sidebar() {
  const {
    projectPath, setProjectPath, fileTree, setFileTree,
    openFile, addFileContext
  } = useAppStore()

  const [loading, setLoading] = useState(false)

  const loadDir = useCallback(async (path) => {
    if (!path || !fs) return
    setLoading(true)
    try {
      const entries = await fs.readDir(path)
      if (entries.error) { alert(entries.error); return }

      // Build tree with children loaded lazily on expand — for now flat+sort
      const buildNode = async (entry) => {
        if (entry.type === 'dir') {
          const children = await fs.readDir(entry.path)
          return { ...entry, children: Array.isArray(children) ? children.map(c => ({ ...c, children: c.type === 'dir' ? [] : undefined })) : [] }
        }
        return entry
      }
      const nodes = await Promise.all(entries.map(buildNode))
      setFileTree(nodes)
    } finally {
      setLoading(false)
    }
  }, [setFileTree])

  const handleSelectDir = useCallback(async () => {
    if (!fs) return
    const dir = await fs.selectDir()
    if (dir) {
      setProjectPath(dir)
      await loadDir(dir)
    }
  }, [loadDir, setProjectPath])

  const handleFileClick = useCallback(async (node) => {
    if (!fs) return
    const result = await fs.readFile(node.path)
    if (result.error) { console.error(result.error); return }
    const ext = '.' + node.name.split('.').pop()
    const langMap = { '.java':'java','.py':'python','.js':'javascript','.ts':'typescript','.tsx':'tsx','.jsx':'jsx','.xml':'xml','.yml':'yaml','.yaml':'yaml','.json':'json','.sql':'sql','.md':'markdown','.html':'html','.css':'css' }
    const file = { path: node.path, name: node.name, content: result.content, language: langMap[ext] || 'text', dirty: false }
    openFile(file)
    addFileContext(file)
  }, [openFile, addFileContext])

  const s = {
    root: { display: 'flex', flexDirection: 'column', width: 'var(--sidebar-w)', background: 'var(--bg-1)', borderRight: '1px solid var(--border)', height: '100%', overflow: 'hidden' },
    header: { padding: '8px', borderBottom: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: 6 },
    pathRow: { display: 'flex', gap: 4 },
    pathInput: { flex: 1, padding: '4px 8px', fontSize: 11, fontFamily: 'var(--font-code)', background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', color: 'var(--text-2)' },
    btn: { padding: '4px 8px', background: 'var(--bg-3)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', color: 'var(--text-2)', fontSize: 11, cursor: 'pointer' },
    sectionLabel: { fontSize: 10, color: 'var(--text-3)', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.08em', padding: '8px 12px 4px' },
    tree: { flex: 1, overflowY: 'auto', padding: '4px' },
    empty: { color: 'var(--text-3)', fontSize: 12, padding: '20px 16px', textAlign: 'center' },
    spinner: { color: 'var(--text-3)', fontSize: 12, padding: '12px 16px' },
  }

  return (
    <div style={s.root}>
      <div style={s.header}>
        <div style={s.pathRow}>
          <input
            style={s.pathInput}
            value={projectPath}
            onChange={e => setProjectPath(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && loadDir(projectPath)}
            placeholder="Đường dẫn project..."
          />
          <button style={s.btn} onClick={() => loadDir(projectPath)} title="Tải thư mục">↺</button>
          <button style={s.btn} onClick={handleSelectDir} title="Chọn thư mục">…</button>
        </div>
      </div>

      <div style={s.sectionLabel}>Explorer</div>

      <div style={s.tree}>
        {loading && <div style={s.spinner}>Đang tải...</div>}
        {!loading && fileTree.length === 0 && (
          <div style={s.empty}>Chưa có project nào.<br />Nhập đường dẫn hoặc nhấn "…" để chọn.</div>
        )}
        {!loading && fileTree.map(node => (
          <TreeNode key={node.path} node={node} depth={0} onFileClick={handleFileClick} />
        ))}
      </div>
    </div>
  )
}
