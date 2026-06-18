import React, { useState } from 'react'
import Sidebar from './components/Sidebar'
import ChatPanel from './components/ChatPanel'
import CodeEditor from './components/CodeEditor'
import AnalyzePanel from './components/AnalyzePanel'
import { useAppStore } from './store/appStore'

const PANELS = [
  { id: 'chat', label: '💬 Chat', title: 'Chat với AI' },
  { id: 'editor', label: '</> Editor', title: 'Code Editor' },
  { id: 'analyze', label: '📊 Analyze', title: 'Phân tích' },
]

export default function App() {
  const [activePanel, setActivePanel] = useState('chat')
  const { openFiles } = useAppStore()

  const s = {
    root: { display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' },
    topbar: {
      height: 'var(--topbar-h)', display: 'flex', alignItems: 'center',
      borderBottom: '1px solid var(--border)', background: 'var(--bg-1)',
      padding: '0 12px', gap: 0, flexShrink: 0,
      WebkitAppRegion: 'drag',          // Electron drag region
    },
    appIcon: { fontSize: 16, marginRight: 10, WebkitAppRegion: 'no-drag' },
    appName: { fontSize: 13, fontWeight: 500, color: 'var(--text-1)', marginRight: 20, minWidth: 120 },
    tabs: { display: 'flex', gap: 0, WebkitAppRegion: 'no-drag' },
    tab: (active) => ({
      padding: '0 16px', height: 'var(--topbar-h)', display: 'flex', alignItems: 'center',
      cursor: 'pointer', fontSize: 12,
      color: active ? 'var(--text-1)' : 'var(--text-3)',
      borderBottom: `2px solid ${active ? 'var(--accent)' : 'transparent'}`,
      background: 'transparent',
    }),
    tabBadge: { marginLeft: 4, fontSize: 10, padding: '1px 5px', borderRadius: 10, background: 'var(--accent-dim)', color: 'var(--accent)' },
    body: { display: 'flex', flex: 1, overflow: 'hidden' },
    main: { flex: 1, overflow: 'hidden' },
    statusbar: {
      height: 'var(--statusbar-h)', display: 'flex', alignItems: 'center',
      padding: '0 12px', gap: 16, borderTop: '1px solid var(--border)',
      background: 'var(--bg-1)', flexShrink: 0, fontSize: 11, color: 'var(--text-3)',
    },
  }

  return (
    <div style={s.root}>
      {/* Topbar */}
      <div style={s.topbar}>
        <span style={s.appIcon}>🤖</span>
        <span style={s.appName}>AI Developer Agent</span>
        <div style={s.tabs}>
          {PANELS.map(p => (
            <button key={p.id} style={s.tab(activePanel === p.id)} onClick={() => setActivePanel(p.id)}>
              {p.label}
              {p.id === 'editor' && openFiles.length > 0 && (
                <span style={s.tabBadge}>{openFiles.length}</span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Body */}
      <div style={s.body}>
        <Sidebar />
        <div style={s.main}>
          {activePanel === 'chat' && <ChatPanel />}
          {activePanel === 'editor' && <CodeEditor />}
          {activePanel === 'analyze' && <AnalyzePanel />}
        </div>
      </div>

      {/* Statusbar */}
      <div style={s.statusbar}>
        <span>AI Developer Agent v1.0</span>
        <span>·</span>
        <span>{openFiles.length} file đang mở</span>
        <span style={{ marginLeft: 'auto' }}>Spring Boot · Java 21 · Microservices</span>
      </div>
    </div>
  )
}
