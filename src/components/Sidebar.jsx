import React, { useState, useCallback, useEffect } from 'react'
import { useAppStore } from '../store/appStore'
import { readTreeRecursive } from '../helpers/helpers';

const fs = window.electronAPI

const EXT_ICON = {
  '.java': '☕', '.py': '🐍', '.js': '📜', '.ts': '📘',
  '.tsx': '⚛️', '.jsx': '⚛️', '.xml': '📋', '.yml': '⚙️',
  '.yaml': '⚙️', '.json': '{}', '.sql': '🗄️', '.md': '📝',
  '.gradle': '🐘', '.sh': '💲', '.html': '🌐', '.css': '🎨',
  '.kt': '🦊', '.properties': '⚙️', '.env': '🔑', '.txt': '📃',
  '.rs': '🦀', '.go': '🐹', '.toml': '⚙️', '.lock': '🔒',
}

const LANG_MAP = {
  '.java': 'java', '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
  '.tsx': 'tsx', '.jsx': 'jsx', '.xml': 'xml', '.yml': 'yaml', '.yaml': 'yaml',
  '.json': 'json', '.sql': 'sql', '.md': 'markdown', '.html': 'html',
  '.css': 'css', '.scss': 'scss', '.sh': 'shell', '.kt': 'kotlin',
  '.rs': 'rust', '.go': 'go', '.toml': 'toml', '.properties': 'properties',
}

function fileIcon(name) {
  const ext = '.' + name.split('.').pop().toLowerCase()
  return EXT_ICON[ext] || '📄'
}

// ─── TreeNode ─────────────────────────────────────────────────────────────────

function TreeNode({ node, depth, onFileClick, onDirLoad }) {
  const { activeFilePath } = useAppStore()
  const isDir = node.type === 'dir'
  const isActive = !isDir && activeFilePath === node.path

  // Dirs mở sẵn ở 2 tầng đầu
  const [expanded, setExpanded] = useState(depth < 2 && isDir)
  const [loading, setLoading] = useState(false)

  const handleClick = useCallback(async () => {
    if (!isDir) { onFileClick(node); return }

    const willExpand = !expanded

    // Nếu expand nhưng children chưa load (null) → load lúc này
    if (willExpand && node.children === null) {
      setLoading(true)
      try {
        const children = await readTreeRecursive(node.path, 0, 4)
        onDirLoad(node.path, children)
      } finally {
        setLoading(false)
      }
    }

    setExpanded(willExpand)
  }, [isDir, expanded, node, onFileClick, onDirLoad])

  const pad = 10 + depth * 14

  return (
    <>
      <div
        onClick={handleClick}
        style={{
          display: 'flex', alignItems: 'center', gap: 5,
          padding: `3px 8px 3px ${pad}px`,
          cursor: 'pointer', userSelect: 'none',
          borderRadius: 'var(--radius-sm)', fontSize: 12,
          color: isActive ? 'var(--accent)' : isDir ? 'var(--text-1)' : 'var(--text-2)',
          background: isActive ? 'var(--accent-dim)' : 'transparent',
          whiteSpace: 'nowrap', overflow: 'hidden',
        }}
        onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = 'var(--bg-hover)' }}
        onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = 'transparent' }}
        title={node.path}
      >
        {/* Indent guide line */}
        {depth > 0 && (
          <span style={{ position: 'absolute', left: pad - 7, top: 0, bottom: 0, width: 1, background: 'var(--border)', opacity: 0.4 }} />
        )}

        {/* Arrow / icon */}
        <span style={{ fontSize: 10, width: 12, flexShrink: 0, textAlign: 'center', color: 'var(--text-3)' }}>
          {isDir
            ? loading ? '⋯' : expanded ? '▾' : '▸'
            : fileIcon(node.name)
          }
        </span>

        {/* Folder icon for dirs */}
        {isDir && (
          <span style={{ fontSize: 12, flexShrink: 0 }}>
            {expanded ? '📂' : '📁'}
          </span>
        )}

        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', flex: 1 }}>
          {node.name}
        </span>
      </div>

      {isDir && expanded && Array.isArray(node.children) && node.children.map(child => (
        <TreeNode
          key={child.path}
          node={child}
          depth={depth + 1}
          onFileClick={onFileClick}
          onDirLoad={onDirLoad}
        />
      ))}
    </>
  )
}

// ─── Sidebar ──────────────────────────────────────────────────────────────────

export default function Sidebar() {
  const { projectPath, setProjectPath, fileTree, setFileTree, openFile, addFileContext,
          projectContext, setProjectContext, clearProjectContext } = useAppStore()
  const [loading, setLoading]         = useState(false)
  const [scanning, setScanning]       = useState(false)
  const [error, setError]             = useState(null)
  const [ctxExpanded, setCtxExpanded] = useState(false)

  const loadProject = useCallback(async (path) => {
    if (!path || !fs) return
    setLoading(true)
    setError(null)
    try {
      const tree = await readTreeRecursive(path, 0, 6)
      setFileTree(tree)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [setFileTree])

  // Khi một dir được lazy-load, cập nhật đúng node trong tree
  const handleDirLoad = useCallback((dirPath, children) => {
    function patchTree(nodes) {
      return nodes.map(n => {
        if (n.path === dirPath) return { ...n, children, loaded: true }
        if (n.type === 'dir' && Array.isArray(n.children)) return { ...n, children: patchTree(n.children) }
        return n
      })
    }
    setFileTree(patchTree(useAppStore.getState().fileTree))
  }, [setFileTree])

  const handleSelectDir = useCallback(async () => {
    if (!fs) return
    const dir = await fs.selectDir()
    if (dir) { setProjectPath(dir); clearProjectContext(); await loadProject(dir) }
  }, [loadProject, setProjectPath, clearProjectContext])

  const handleScanContext = useCallback(async (force = false) => {
    if (!projectPath) return
    setScanning(true)
    try {
      const res = await fetch('http://localhost:8765/project-context/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_path: projectPath, force }),
      })
      const data = await res.json()
      if (data.context) {
        setProjectContext(data.context)
        setCtxExpanded(true)
      }
    } catch (e) {
      console.error('[ScanContext]', e)
    } finally {
      setScanning(false)
    }
  }, [projectPath, setProjectContext])

  const handleFileClick = useCallback(async (node) => {
    if (!fs) return
    const result = await fs.readFile(node.path)
    if (result.error) { console.error(result.error); return }
    const ext = '.' + node.name.split('.').pop().toLowerCase()
    const file = {
      path: node.path,
      name: node.name,
      content: result.content,
      language: LANG_MAP[ext] || 'text',
      dirty: false
    }
    openFile(file)
    addFileContext(file)
  }, [openFile, addFileContext])

  const s = {
    root: { display: 'flex', flexDirection: 'column', width: 'var(--sidebar-w)', minWidth: 'var(--sidebar-w)', background: 'var(--bg-1)', borderRight: '1px solid var(--border)', height: '100%', overflow: 'hidden', position: 'relative' },
    header: { padding: '8px', borderBottom: '1px solid var(--border)', flexShrink: 0 },
    pathRow: { display: 'flex', gap: 4 },
    pathInput: { flex: 1, minWidth: 0, padding: '4px 8px', fontSize: 11, fontFamily: 'var(--font-code)', background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', color: 'var(--text-2)' },
    btn: { padding: '4px 8px', background: 'var(--bg-3)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', color: 'var(--text-2)', fontSize: 13, cursor: 'pointer', flexShrink: 0 },
    label: { fontSize: 10, color: 'var(--text-3)', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.08em', padding: '8px 12px 4px', flexShrink: 0 },
    tree: { flex: 1, overflowY: 'auto', overflowX: 'hidden', padding: '2px 4px 12px', position: 'relative' },
    empty: { color: 'var(--text-3)', fontSize: 12, padding: '24px 16px', textAlign: 'center', lineHeight: 1.8 },
    spinner: { display: 'flex', alignItems: 'center', gap: 8, padding: '12px 14px', color: 'var(--text-3)', fontSize: 12 },
    errorBox: { margin: '8px', padding: '8px 10px', background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.3)', borderRadius: 'var(--radius-sm)', fontSize: 11, color: 'var(--red)' },
    fileCount: { fontSize: 10, color: 'var(--text-3)', padding: '4px 12px 6px', flexShrink: 0 },
  }

  // Đếm tổng số nodes để hiện ở footer
  function countNodes(nodes) {
    if (!nodes) return 0
    return nodes.reduce((acc, n) => acc + 1 + (n.children ? countNodes(n.children) : 0), 0)
  }
  const total = countNodes(fileTree)

  return (
    <div style={s.root}>
      <div style={s.header}>
        <div style={s.pathRow}>
          <input
            style={s.pathInput}
            value={projectPath}
            onChange={e => setProjectPath(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && loadProject(projectPath)}
            placeholder="Đường dẫn project..."
          />
          <button style={s.btn} onClick={() => loadProject(projectPath)} title="Reload (↺)">↺</button>
          <button style={s.btn} onClick={handleSelectDir} title="Chọn thư mục (…)">…</button>
        </div>
        {/* Project Context bar */}
        {projectPath && (
          <div style={{ marginTop: 6 }}>
            {!projectContext ? (
              <button
                onClick={() => handleScanContext(false)}
                disabled={scanning}
                style={{
                  width: '100%', padding: '5px 8px', fontSize: 11,
                  background: 'var(--bg-3)', border: '1px dashed var(--border)',
                  borderRadius: 'var(--radius-sm)', color: 'var(--text-3)',
                  cursor: scanning ? 'not-allowed' : 'pointer',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                }}
              >
                {scanning
                  ? <><span style={{ animation: 'spin 1s linear infinite', display:'inline-block' }}>⧗</span> Đang scan...</>  
                  : <>🔍 Scan project context</>}
                <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
              </button>
            ) : (
              <div style={{ border: '1px solid var(--accent-dim)', borderRadius: 'var(--radius-sm)', overflow: 'hidden' }}>
                {/* Header badge */}
                <div
                  onClick={() => setCtxExpanded(v => !v)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 6,
                    padding: '4px 8px', cursor: 'pointer',
                    background: 'var(--accent-dim)',
                  }}
                >
                  <span style={{ fontSize: 11 }}>🏗️</span>
                  <span style={{ flex: 1, fontSize: 11, fontWeight: 600, color: 'var(--accent)' }}>
                    {projectContext.stack?.frameworks?.[0] || projectContext.project_name}
                  </span>
                  <span style={{ fontSize: 10, color: 'var(--text-3)' }}>
                    {projectContext.total_files}f
                  </span>
                  <button
                    onClick={e => { e.stopPropagation(); handleScanContext(true) }}
                    disabled={scanning}
                    title="Re-scan"
                    style={{
                      background: 'none', border: 'none', cursor: 'pointer',
                      fontSize: 11, color: 'var(--text-3)', padding: '0 2px',
                    }}
                  >{scanning ? '⧗' : '↻'}</button>
                  <span style={{ fontSize: 10, color: 'var(--text-3)' }}>{ctxExpanded ? '▴' : '▾'}</span>
                </div>
                {/* Detail */}
                {ctxExpanded && (
                  <div style={{ padding: '6px 8px', background: 'var(--bg-1)', fontSize: 11 }}>
                    {projectContext.stack?.languages?.length > 0 && (
                      <div style={{ color: 'var(--text-2)', marginBottom: 3 }}>
                        💻 {projectContext.stack.languages.join(', ')}
                      </div>
                    )}
                    {projectContext.stack?.databases?.length > 0 && (
                      <div style={{ color: 'var(--text-2)', marginBottom: 3 }}>
                        🗄 {projectContext.stack.databases.join(', ')}
                      </div>
                    )}
                    {/* Features section */}
                    {projectContext.features?.description && (
                      <div style={{ color: 'var(--text-2)', marginBottom: 3, fontStyle: 'italic' }}>
                        “{projectContext.features.description}”
                      </div>
                    )}
                    {projectContext.features?.features?.length > 0 && (
                      <div style={{ marginBottom: 3 }}>
                        {projectContext.features.features.map((f, i) => (
                          <div key={i} style={{ fontSize: 10, color: 'var(--text-3)', paddingLeft: 4 }}>
                            • {f}
                          </div>
                        ))}
                      </div>
                    )}
                    {projectContext.stack?.build_tools?.length > 0 && (
                      <div style={{ color: 'var(--text-3)', marginBottom: 3 }}>
                        ⚙️ {projectContext.stack.build_tools.join(', ')}
                      </div>
                    )}
                    {projectContext.conventions?.indent && (
                      <div style={{ color: 'var(--text-3)', marginBottom: 3 }}>
                        ≣ {projectContext.conventions.indent} | {projectContext.conventions.structure}
                      </div>
                    )}
                    <div style={{ color: 'var(--text-3)', marginTop: 4, borderTop: '1px solid var(--border)', paddingTop: 4 }}>
                      📄 Key files: {projectContext.key_files?.length || 0}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      <div style={s.label}>Explorer</div>

      {error && <div style={s.errorBox}>⚠ {error}</div>}

      <div style={s.tree}>
        {loading && (
          <div style={s.spinner}>
            <span style={{ animation: 'spin 1s linear infinite', display: 'inline-block' }}>⟳</span>
            Đang đọc cây thư mục...
            <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
          </div>
        )}

        {!loading && fileTree.length === 0 && (
          <div style={s.empty}>
            📂<br />
            Nhập đường dẫn rồi nhấn Enter<br />
            hoặc nhấn <strong>…</strong> để chọn thư mục
          </div>
        )}

        {!loading && fileTree.map(node => (
          <TreeNode
            key={node.path}
            node={node}
            depth={0}
            onFileClick={handleFileClick}
            onDirLoad={handleDirLoad}
          />
        ))}
      </div>

      {total > 0 && !loading && (
        <div style={s.fileCount}>{total} items</div>
      )}
    </div>
  )
}
