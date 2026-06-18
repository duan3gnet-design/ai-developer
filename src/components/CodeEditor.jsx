import React, { useCallback } from 'react'
import Editor from '@monaco-editor/react'
import { useAppStore } from '../store/appStore'

const fs = window.electronAPI

export default function CodeEditor() {
  const {
    openFiles, activeFilePath,
    closeFile, updateFileContent, markFileSaved,
    addFileContext, removeFileContext, fileContexts,
  } = useAppStore()

  const activeFile = openFiles.find(f => f.path === activeFilePath)

  const handleSave = useCallback(async () => {
    if (!activeFile || !fs) return
    const res = await fs.writeFile(activeFile.path, activeFile.content)
    if (res.success) {
      markFileSaved(activeFile.path)
    } else {
      alert('Lỗi khi lưu: ' + res.error)
    }
  }, [activeFile, markFileSaved])

  // Ctrl+S
  const handleEditorMount = (editor) => {
    editor.addCommand(
      // monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS
      2097 | 49,  // numeric shortcut
      handleSave
    )
  }

  const inContext = activeFile && fileContexts.some(f => f.path === activeFile.path)

  const s = {
    root: { display: 'flex', flexDirection: 'column', height: '100%', background: 'var(--bg-0)' },
    tabs: { display: 'flex', borderBottom: '1px solid var(--border)', background: 'var(--bg-1)', overflowX: 'auto', flexShrink: 0 },
    tab: (active, dirty) => ({
      display: 'flex', alignItems: 'center', gap: 6,
      padding: '0 14px', height: 36, cursor: 'pointer', flexShrink: 0,
      fontSize: 12, color: active ? 'var(--text-1)' : 'var(--text-3)',
      borderBottom: `2px solid ${active ? 'var(--accent)' : 'transparent'}`,
      background: active ? 'var(--bg-0)' : 'transparent',
      whiteSpace: 'nowrap',
    }),
    tabDot: { width: 6, height: 6, borderRadius: '50%', background: 'var(--amber)' },
    closeBtn: { fontSize: 11, color: 'var(--text-3)', width: 16, height: 16, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 3 },
    toolbar: { display: 'flex', alignItems: 'center', gap: 8, padding: '6px 12px', borderBottom: '1px solid var(--border)', background: 'var(--bg-1)', flexShrink: 0 },
    toolBtn: { padding: '3px 10px', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', color: 'var(--text-2)', fontSize: 11, cursor: 'pointer', background: 'var(--bg-2)' },
    pathLabel: { fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--font-code)', marginLeft: 'auto', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 400 },
    empty: { flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 12, color: 'var(--text-3)' },
  }

  if (openFiles.length === 0) {
    return (
      <div style={s.root}>
        <div style={s.empty}>
          <div style={{ fontSize: 40 }}>📂</div>
          <div>Chọn file từ sidebar để bắt đầu</div>
        </div>
      </div>
    )
  }

  return (
    <div style={s.root}>
      {/* Tabs */}
      <div style={s.tabs}>
        {openFiles.map(f => (
          <div key={f.path} style={s.tab(f.path === activeFilePath, f.dirty)}
            onClick={() => useAppStore.getState().openFile(f)}
          >
            {f.dirty && <div style={s.tabDot} />}
            <span>{f.name}</span>
            <button style={s.closeBtn}
              onClick={e => { e.stopPropagation(); closeFile(f.path) }}
              onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
            >✕</button>
          </div>
        ))}
      </div>

      {/* Toolbar */}
      {activeFile && (
        <div style={s.toolbar}>
          <button style={s.toolBtn} onClick={handleSave}>💾 Lưu</button>
          <button
            style={{ ...s.toolBtn, borderColor: inContext ? 'var(--accent)' : 'var(--border)', color: inContext ? 'var(--accent)' : 'var(--text-2)' }}
            onClick={() => inContext ? removeFileContext(activeFile.path) : addFileContext(activeFile)}
          >
            {inContext ? '✓ Trong chat context' : '+ Thêm vào chat'}
          </button>
          <span style={s.pathLabel}>{activeFile.path}</span>
        </div>
      )}

      {/* Monaco Editor */}
      {activeFile && (
        <div style={{ flex: 1, overflow: 'hidden' }}>
          <Editor
            height="100%"
            language={activeFile.language}
            value={activeFile.content}
            theme="vs-dark"
            onMount={handleEditorMount}
            onChange={val => updateFileContent(activeFile.path, val)}
            options={{
              fontSize: 13,
              fontFamily: 'JetBrains Mono, Fira Code, monospace',
              fontLigatures: true,
              lineHeight: 22,
              minimap: { enabled: false },
              scrollBeyondLastLine: false,
              wordWrap: 'on',
              padding: { top: 12 },
              smoothScrolling: true,
              cursorBlinking: 'smooth',
              renderLineHighlight: 'gutter',
              bracketPairColorization: { enabled: true },
              guides: { bracketPairs: true },
              tabSize: 2,
            }}
          />
        </div>
      )}
    </div>
  )
}
