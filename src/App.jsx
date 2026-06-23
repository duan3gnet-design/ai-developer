import React, { useState } from 'react'
import Sidebar from './components/Sidebar'
import ChatPanel from './components/ChatPanel'
import CodeEditor from './components/CodeEditor'
import AnalyzePanel from './components/AnalyzePanel'
import ExperiencePanel from './components/ExperiencePanel'
import { useAppStore } from './store/appStore'

const PANELS = [
  { id: 'chat',       label: '💬 Chat',        },
  { id: 'editor',     label: '</> Editor',     },
  { id: 'analyze',    label: '📊 Analyze',     },
  { id: 'experience', label: '📚 Experience',  },
]

export default function App() {
  const [activePanel, setActivePanel] = useState('chat')
  const { openFiles, messages, clearMessages, clearFileContexts, isThinking } = useAppStore()

  const handleNewChat = () => {
    if (isThinking) return       // đang thinking thì không clear
    clearMessages()
    clearFileContexts()
    setActivePanel('chat')
  }

  const hasMessages = messages.length > 0

  const s = {
    root:    { display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' },
    topbar:  { height: 'var(--topbar-h)', display: 'flex', alignItems: 'center', borderBottom: '1px solid var(--border)', background: 'var(--bg-1)', padding: '0 12px', flexShrink: 0, WebkitAppRegion: 'drag' },
    appIcon: { fontSize: 16, marginRight: 8, WebkitAppRegion: 'no-drag' },
    appName: { fontSize: 13, fontWeight: 500, color: 'var(--text-1)', marginRight: 20 },
    tabs:    { display: 'flex', WebkitAppRegion: 'no-drag' },
    tab: (active) => ({
      padding: '0 16px', height: 'var(--topbar-h)', display: 'flex', alignItems: 'center',
      cursor: 'pointer', fontSize: 12, background: 'transparent',
      color: active ? 'var(--text-1)' : 'var(--text-3)',
      borderBottom: `2px solid ${active ? 'var(--accent)' : 'transparent'}`,
    }),
    tabBadge: { marginLeft: 4, fontSize: 10, padding: '1px 5px', borderRadius: 10, background: 'var(--accent-dim)', color: 'var(--accent)' },

    // New Chat button — góc phải topbar
    newChatBtn: {
      marginLeft: 'auto', WebkitAppRegion: 'no-drag',
      display: 'flex', alignItems: 'center', gap: 6,
      padding: '5px 12px', fontSize: 12, fontWeight: 500,
      border: `1px solid ${hasMessages ? 'var(--accent-dim)' : 'var(--border)'}`,
      borderRadius: 'var(--radius-md)', cursor: hasMessages ? 'pointer' : 'default',
      color: hasMessages ? 'var(--accent)' : 'var(--text-3)',
      background: hasMessages ? 'var(--accent-dim)' : 'transparent',
      opacity: isThinking ? 0.4 : 1,
      transition: 'all 0.15s',
    },

    body:    { display: 'flex', flex: 1, overflow: 'hidden' },
    main:    { flex: 1, overflow: 'hidden' },
    statusbar: { height: 'var(--statusbar-h)', display: 'flex', alignItems: 'center', padding: '0 12px', gap: 12, borderTop: '1px solid var(--border)', background: 'var(--bg-1)', flexShrink: 0, fontSize: 11, color: 'var(--text-3)' },
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
              {p.id === 'chat' && hasMessages && (
                <span style={s.tabBadge}>{messages.length}</span>
              )}
            </button>
          ))}
        </div>

        <button
          style={s.newChatBtn}
          onClick={handleNewChat}
          disabled={!hasMessages || isThinking}
          title={hasMessages ? 'Bắt đầu cuộc trò chuyện mới' : 'Chưa có tin nhắn nào'}
          onMouseEnter={e => { if (hasMessages && !isThinking) e.currentTarget.style.background = 'rgba(124,109,234,0.25)' }}
          onMouseLeave={e => { e.currentTarget.style.background = hasMessages ? 'var(--accent-dim)' : 'transparent' }}
        >
          ✦ New Chat
        </button>
      </div>

      {/* Body */}
      <div style={s.body}>
        <Sidebar />
        <div style={s.main}>
          {activePanel === 'chat'    && <ChatPanel />}
          {activePanel === 'editor'  && <CodeEditor />}
          {activePanel === 'analyze'    && <AnalyzePanel />}
          {activePanel === 'experience' && <ExperiencePanel />}
        </div>
      </div>

      {/* Statusbar */}
      <div style={s.statusbar}>
        <span>AI Developer Agent v1.0</span>
        <span>·</span>
        <span>{openFiles.length} file đang mở</span>
        {hasMessages && <><span>·</span><span>{messages.length} tin nhắn</span></>}
        <span style={{ marginLeft: 'auto' }}>Groq · Qwen3-32B</span>
      </div>
    </div>
  )
}
