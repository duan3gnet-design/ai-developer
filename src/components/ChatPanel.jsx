import React, { useEffect, useRef, useState, useCallback } from 'react'
import { useAppStore } from '../store/appStore'
import { agentApi } from '../hooks/useAgent'
import ReactMarkdown from 'react-markdown'
import { readTreeRecursive } from '../helpers/helpers';

const QUICK_PROMPTS = [
  { label: '🔍 Phân tích cấu trúc', prompt: 'Phân tích cấu trúc và kiến trúc của dự án này' },
  { label: '🐛 Tìm bug', prompt: 'Tìm các bug tiềm ẩn và vấn đề trong code' },
  { label: '✨ Tối ưu', prompt: 'Đề xuất cách tối ưu performance và refactor code' },
  { label: '🧪 Tạo test', prompt: 'Viết unit test cho các class/function chính' },
  { label: '📄 Giải thích', prompt: 'Giải thích chi tiết code trong file đang mở' },
  { label: '🚀 Phát triển thêm', prompt: 'Đề xuất và implement tính năng mới phù hợp với kiến trúc hiện tại' },
]

const mdComponents = {
  code({ inline, children }) {
    if (inline) return <code style={{ background: 'var(--bg-3)', padding: '1px 5px', borderRadius: 3, fontSize: 12, fontFamily: 'var(--font-code)' }}>{children}</code>
    return <pre style={{ background: 'var(--bg-0)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: '10px 12px', fontSize: 12, fontFamily: 'var(--font-code)', overflowX: 'auto', marginTop: 8 }}><code>{children}</code></pre>
  },
  p({ children }) { return <p style={{ marginBottom: 8 }}>{children}</p> },
  ul({ children }) { return <ul style={{ paddingLeft: 20, marginBottom: 8 }}>{children}</ul> },
  ol({ children }) { return <ol style={{ paddingLeft: 20, marginBottom: 8 }}>{children}</ol> },
  li({ children }) { return <li style={{ marginBottom: 4 }}>{children}</li> },
  h1({ children }) { return <h1 style={{ fontSize: 16, fontWeight: 500, marginBottom: 8 }}>{children}</h1> },
  h2({ children }) { return <h2 style={{ fontSize: 14, fontWeight: 500, marginBottom: 6 }}>{children}</h2> },
  h3({ children }) { return <h3 style={{ fontSize: 13, fontWeight: 500, marginBottom: 4, color: 'var(--text-2)' }}>{children}</h3> },
  strong({ children }) { return <strong style={{ fontWeight: 500 }}>{children}</strong> },
}

function Chip({ file, onRemove }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 8px', borderRadius: 20, background: 'var(--accent-dim)', color: 'var(--accent)', fontSize: 11, border: '1px solid var(--accent-dim)' }}>
      {file.name}
      <button onClick={() => onRemove(file.path)} style={{ color: 'var(--accent)', fontSize: 10, lineHeight: 1 }}>✕</button>
    </span>
  )
}

function CopyButton({ content }) {
  const [copied, setCopied] = useState(false)
  const handle = () => { navigator.clipboard.writeText(content); setCopied(true); setTimeout(() => setCopied(false), 1500) }
  return (
    <button onClick={handle}
      style={{ fontSize: 11, padding: '2px 8px', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', color: 'var(--text-3)', cursor: 'pointer', background: 'transparent' }}
      onMouseEnter={e => e.currentTarget.style.color = 'var(--text-1)'}
      onMouseLeave={e => e.currentTarget.style.color = 'var(--text-3)'}
    >{copied ? '✓ Đã copy' : '⎘ Copy'}</button>
  )
}

function shortPath(p) {
  return (p || '').replace(/\\/g, '/').split('/').slice(-3).join('/')
}

// Badge tổng hợp: files ghi + files xóa
function FileOpsBadge({ filesWritten, filesDeleted }) {
  const [expanded, setExpanded] = useState(false)

  const written = filesWritten || []
  const deleted = filesDeleted || []
  if (written.length === 0 && deleted.length === 0) return null

  const writtenOk   = written.filter(f => f.success)
  const writtenFail = written.filter(f => !f.success)
  const deletedOk   = deleted.filter(f => f.success)
  const deletedFail = deleted.filter(f => !f.success)
  const anyFail     = writtenFail.length + deletedFail.length > 0

  // Summary label
  const parts = []
  if (writtenOk.length)   parts.push(<span key="w" style={{ color: 'var(--green)' }}>✓ {writtenOk.length} file ghi</span>)
  if (deletedOk.length)   parts.push(<span key="d" style={{ color: 'var(--amber)' }}>🗑 {deletedOk.length} file xóa</span>)
  if (writtenFail.length) parts.push(<span key="wf" style={{ color: 'var(--red)' }}>{writtenFail.length} ghi thất bại</span>)
  if (deletedFail.length) parts.push(<span key="df" style={{ color: 'var(--red)' }}>{deletedFail.length} xóa thất bại</span>)

  const BADGE = {
    create: { label: 'NEW',    bg: 'var(--green-dim)',              color: 'var(--green)' },
    update: { label: 'UPDATE', bg: 'rgba(96,165,250,0.15)',         color: 'var(--blue)'  },
    delete: { label: 'DELETE', bg: 'rgba(251,191,36,0.15)',         color: 'var(--amber)' },
    unknown:{ label: '?',      bg: 'var(--bg-3)',                   color: 'var(--text-3)'},
  }

  const Row = ({ icon, badge, path, error, success }) => (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '5px 10px', borderTop: '1px solid var(--border)' }}>
      <span style={{ flexShrink: 0, marginTop: 1, color: success ? (badge === 'DELETE' ? 'var(--amber)' : 'var(--green)') : 'var(--red)' }}>{icon}</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 10, padding: '1px 5px', borderRadius: 3, background: BADGE[badge?.toLowerCase()]?.bg, color: BADGE[badge?.toLowerCase()]?.color, flexShrink: 0 }}>
            {BADGE[badge?.toLowerCase()]?.label || badge}
          </span>
          <span style={{ fontFamily: 'var(--font-code)', fontSize: 11, color: success ? 'var(--text-1)' : 'var(--red)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {shortPath(path)}
          </span>
        </div>
        {error && <div style={{ color: 'var(--red)', fontSize: 11, marginTop: 2 }}>{error}</div>}
      </div>
    </div>
  )

  return (
    <div style={{ marginTop: 10, borderRadius: 'var(--radius-md)', border: `1px solid ${anyFail ? 'rgba(248,113,113,0.3)' : 'var(--border)'}`, overflow: 'hidden', fontSize: 12 }}>
      <div onClick={() => setExpanded(e => !e)}
        style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 10px', background: 'var(--bg-3)', cursor: 'pointer', userSelect: 'none' }}
      >
        <span>{anyFail ? '⚠️' : '✅'}</span>
        <span style={{ flex: 1, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {parts.map((p, i) => <React.Fragment key={i}>{i > 0 && <span style={{ color: 'var(--text-3)' }}>·</span>}{p}</React.Fragment>)}
        </span>
        <span style={{ color: 'var(--text-3)', fontSize: 10 }}>{expanded ? '▲' : '▼'}</span>
      </div>

      {expanded && (
        <div style={{ background: 'var(--bg-1)' }}>
          {written.map((f, i) => (
            <Row key={'w' + i} icon={f.success ? '✓' : '✗'} badge={f.action} path={f.path} error={f.error} success={f.success} />
          ))}
          {deleted.map((f, i) => (
            <Row key={'d' + i} icon={f.success ? '🗑' : '✗'} badge="delete" path={f.path} error={f.error} success={f.success} />
          ))}
        </div>
      )}
    </div>
  )
}

function Message({ msg, isLast, onRetry }) {
  const isUser = msg.role === 'user'
  const isError = !isUser && msg.content?.startsWith('❌')
  const [hovered, setHovered] = useState(false)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: isUser ? 'flex-end' : 'flex-start', marginBottom: 12 }}
      onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, maxWidth: '82%', flexDirection: isUser ? 'row-reverse' : 'row' }}>
        {!isUser && (
          <div style={{ width: 28, height: 28, borderRadius: '50%', background: isError ? 'rgba(248,113,113,0.15)' : 'var(--accent-dim)', color: isError ? 'var(--red)' : 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, flexShrink: 0, marginTop: 2 }}>
            AI
          </div>
        )}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ padding: '10px 14px', borderRadius: isUser ? '12px 12px 4px 12px' : '12px 12px 12px 4px', background: isUser ? 'var(--accent-dim)' : isError ? 'rgba(248,113,113,0.07)' : 'var(--bg-2)', border: `1px solid ${isUser ? 'var(--accent-dim)' : isError ? 'rgba(248,113,113,0.3)' : 'var(--border)'}`, color: 'var(--text-1)', fontSize: 13, lineHeight: 1.7 }}>
            {isUser
              ? <span style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</span>
              : <ReactMarkdown components={mdComponents}>{msg.content}</ReactMarkdown>
            }
          </div>
          {!isUser && (msg.filesWritten?.length > 0 || msg.filesDeleted?.length > 0) && (
            <FileOpsBadge filesWritten={msg.filesWritten} filesDeleted={msg.filesDeleted} />
          )}
        </div>
      </div>

      <div style={{ display: 'flex', gap: 4, marginTop: 4, paddingLeft: isUser ? 0 : 36, opacity: hovered || isLast ? 1 : 0, transition: 'opacity 0.15s', justifyContent: isUser ? 'flex-end' : 'flex-start' }}>
        {!isUser && <CopyButton content={msg.content} />}
        {((isUser && isLast) || (isError && isLast)) && (
          <button onClick={() => onRetry(msg)}
            style={{ fontSize: 11, padding: '2px 8px', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', color: 'var(--text-3)', cursor: 'pointer', background: 'transparent' }}
            onMouseEnter={e => { e.currentTarget.style.color = 'var(--accent)'; e.currentTarget.style.borderColor = 'var(--accent)' }}
            onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-3)'; e.currentTarget.style.borderColor = 'var(--border)' }}
          >↺ Thử lại</button>
        )}
      </div>
    </div>
  )
}

function ThinkingIndicator({ onCancel }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0' }}>
      <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'var(--accent-dim)', color: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13 }}>AI</div>
      <div style={{ display: 'flex', gap: 4 }}>
        {[0, 150, 300].map(d => <div key={d} style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent)', animation: 'pulse 1.2s ease infinite', animationDelay: `${d}ms` }} />)}
      </div>
      <button onClick={onCancel}
        style={{ marginLeft: 8, fontSize: 11, padding: '2px 8px', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', color: 'var(--text-3)', cursor: 'pointer', background: 'transparent' }}
        onMouseEnter={e => { e.currentTarget.style.color = 'var(--red)'; e.currentTarget.style.borderColor = 'var(--red)' }}
        onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-3)'; e.currentTarget.style.borderColor = 'var(--border)' }}
      >✕ Hủy</button>
      <style>{`@keyframes pulse { 0%,80%,100%{opacity:0.2} 40%{opacity:1} }`}</style>
    </div>
  )
}

export default function ChatPanel() {
  const { messages, addMessage, setThinking, isThinking, fileContexts, removeFileContext, projectPath, setFileTree } = useAppStore()
  const [input, setInput] = useState('')
  const [backendOk, setBackendOk] = useState(null)
  const bottomRef = useRef(null)
  const textareaRef = useRef(null)
  const abortRef = useRef(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, isThinking])
  useEffect(() => { agentApi.health().then(() => setBackendOk(true)).catch(() => setBackendOk(false)) }, [])

  const reloadFileTree = useCallback(async () => {
    const { projectPath: proj } = useAppStore.getState()
    if (!proj || !window.electronAPI) return
    try {
      const tree = await readTreeRecursive(proj, 0, 6)
      setFileTree(tree)
    } catch { /* silent */ }
  }, [setFileTree])

  const callAgent = useCallback(async (userMsg) => {
    if (abortRef.current) abortRef.current.abort()
    abortRef.current = new AbortController()
    setThinking(true)
    try {
      const { messages: currentMsgs, fileContexts: ctx, projectPath: proj } = useAppStore.getState()
      const history = currentMsgs.slice(-22, -1).map(m => ({ role: m.role, content: m.content }))
      const res = await agentApi.chat(userMsg, ctx, history, proj)
      const { reply, files_written, files_deleted } = res.data

      addMessage({ role: 'assistant', content: reply, filesWritten: files_written || [], filesDeleted: files_deleted || [] })

      if (files_written?.some(f => f.success) || files_deleted?.some(f => f.success)) {
        await reloadFileTree()
      }
    } catch (err) {
      if (err.name === 'CanceledError' || err.code === 'ERR_CANCELED') return
      addMessage({
        role: 'assistant',
        content: backendOk === false
          ? '❌ Python backend chưa khởi động. Chạy: `cd python && pip install -r requirements.txt && python server.py`'
          : `❌ Lỗi: ${err.message}`,
        filesWritten: [], filesDeleted: []
      })
    } finally {
      setThinking(false)
    }
  }, [addMessage, setThinking, backendOk, reloadFileTree])

  const send = useCallback(async (text) => {
    const msg = (text || input).trim()
    if (!msg || isThinking) return
    setInput('')
    addMessage({ role: 'user', content: msg })
    await callAgent(msg)
  }, [input, isThinking, addMessage, callAgent])

  const handleRetry = useCallback(async (msg) => {
    if (isThinking) return
    const { messages: currentMsgs } = useAppStore.getState()
    let userContent = ''
    if (msg.role === 'user') {
      userContent = msg.content
      const idx = currentMsgs.findIndex(m => m.timestamp === msg.timestamp)
      useAppStore.setState({ messages: currentMsgs.slice(0, idx) })
    } else {
      const lastUser = [...currentMsgs].reverse().find(m => m.role === 'user')
      if (!lastUser) return
      userContent = lastUser.content
      useAppStore.setState({ messages: currentMsgs.slice(0, -1) })
    }
    addMessage({ role: 'user', content: userContent })
    await callAgent(userContent)
  }, [isThinking, addMessage, callAgent])

  const handleCancel = useCallback(() => { if (abortRef.current) abortRef.current.abort(); setThinking(false) }, [setThinking])
  const handleKey = (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }

  const s = {
    root: { display: 'flex', flexDirection: 'column', height: '100%', background: 'var(--bg-0)' },
    messages: { flex: 1, overflowY: 'auto', padding: '16px 20px' },
    empty: { textAlign: 'center', color: 'var(--text-3)', marginTop: 60 },
    quickRow: { display: 'flex', gap: 6, flexWrap: 'wrap', padding: '10px 20px', borderTop: '1px solid var(--border)' },
    quickBtn: { fontSize: 11, padding: '4px 10px', border: '1px solid var(--border)', borderRadius: 20, color: 'var(--text-2)', cursor: 'pointer', background: 'var(--bg-1)' },
    inputArea: { padding: '10px 16px 14px', background: 'var(--bg-1)', borderTop: '1px solid var(--border)' },
    contextRow: { display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 },
    inputRow: { display: 'flex', gap: 8, alignItems: 'flex-end' },
    textarea: { flex: 1, padding: '8px 12px', resize: 'none', height: 72, lineHeight: 1.5, background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', color: 'var(--text-1)', fontSize: 13 },
    sendBtn: { padding: '8px 16px', background: 'var(--accent)', border: 'none', borderRadius: 'var(--radius-md)', color: '#fff', fontWeight: 500, cursor: 'pointer', height: 36, alignSelf: 'flex-end', opacity: isThinking ? 0.5 : 1 },
    status: { fontSize: 10, color: backendOk === false ? 'var(--red)' : 'var(--green)', marginTop: 6 },
  }

  return (
    <div style={s.root}>
      <div style={s.messages}>
        {messages.length === 0 && (
          <div style={s.empty}>
            <div style={{ fontSize: 32, marginBottom: 12 }}>🤖</div>
            <div style={{ color: 'var(--text-2)', fontSize: 14 }}>AI Developer Agent sẵn sàng</div>
            <div style={{ color: 'var(--text-3)', fontSize: 12, marginTop: 6 }}>Thử: "Đổi tên UserService thành AccountService" hoặc "Tạo CircuitBreakerConfig.java"</div>
          </div>
        )}
        {messages.map((m, i) => <Message key={i} msg={m} isLast={i === messages.length - 1} onRetry={handleRetry} />)}
        {isThinking && <ThinkingIndicator onCancel={handleCancel} />}
        <div ref={bottomRef} />
      </div>

      <div style={s.quickRow}>
        {QUICK_PROMPTS.map(q => (
          <button key={q.label} style={s.quickBtn} onClick={() => send(q.prompt)}
            onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--accent)'}
            onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border)'}
          >{q.label}</button>
        ))}
      </div>

      <div style={s.inputArea}>
        {fileContexts.length > 0 && (
          <div style={s.contextRow}>
            {fileContexts.map(f => <Chip key={f.path} file={f} onRemove={removeFileContext} />)}
          </div>
        )}
        <div style={s.inputRow}>
          <textarea ref={textareaRef} style={s.textarea} value={input} onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey} disabled={isThinking}
            placeholder="Ví dụ: 'Đổi tên UserController thành AccountController' hoặc 'Xóa file config cũ'"
          />
          <button style={s.sendBtn} onClick={() => send()} disabled={isThinking}>{isThinking ? '...' : '↑ Gửi'}</button>
        </div>
        {backendOk !== null && (
          <div style={s.status}>{backendOk ? '● Python backend connected' : '● Python backend offline — chạy server.py để kích hoạt'}</div>
        )}
      </div>
    </div>
  )
}
