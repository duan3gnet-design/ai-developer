import React, { useEffect, useRef, useState, useCallback } from 'react'
import { useAppStore } from '../store/appStore'
import { agentApi } from '../hooks/useAgent'
import ReactMarkdown from 'react-markdown'
import { readTreeRecursive } from '../helpers/helpers';

const QUICK_PROMPTS = [
  { label: '🔍 Phân tích cấu trúc', prompt: 'Phân tích cấu trúc và kiến trúc của dự án này' },
  { label: '🐛 Tìm bug',            prompt: 'Tìm các bug tiềm ẩn và vấn đề trong code' },
  { label: '✨ Tối ưu',             prompt: 'Đề xuất cách tối ưu performance và refactor code' },
  { label: '🧪 Tạo test',           prompt: 'Viết unit test cho các class/function chính' },
  { label: '📄 Giải thích',         prompt: 'Giải thích chi tiết code trong file đang mở' },
  { label: '🚀 Phát triển thêm',    prompt: 'Đề xuất và implement tính năng mới phù hợp với kiến trúc hiện tại' },
]

const mdComponents = {
  code({ inline, children }) {
    if (inline) return <code style={{ background:'var(--bg-3)', padding:'1px 5px', borderRadius:3, fontSize:12, fontFamily:'var(--font-code)' }}>{children}</code>
    return <pre style={{ background:'var(--bg-0)', border:'1px solid var(--border)', borderRadius:'var(--radius-sm)', padding:'10px 12px', fontSize:12, fontFamily:'var(--font-code)', overflowX:'auto', marginTop:8 }}><code>{children}</code></pre>
  },
  p({ children })      { return <p style={{ marginBottom:8 }}>{children}</p> },
  ul({ children })     { return <ul style={{ paddingLeft:20, marginBottom:8 }}>{children}</ul> },
  ol({ children })     { return <ol style={{ paddingLeft:20, marginBottom:8 }}>{children}</ol> },
  li({ children })     { return <li style={{ marginBottom:4 }}>{children}</li> },
  h1({ children })     { return <h1 style={{ fontSize:16, fontWeight:500, marginBottom:8 }}>{children}</h1> },
  h2({ children })     { return <h2 style={{ fontSize:14, fontWeight:500, marginBottom:6 }}>{children}</h2> },
  h3({ children })     { return <h3 style={{ fontSize:13, fontWeight:500, marginBottom:4, color:'var(--text-2)' }}>{children}</h3> },
  strong({ children }) { return <strong style={{ fontWeight:500 }}>{children}</strong> },
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function Chip({ file, onRemove }) {
  return (
    <span style={{ display:'inline-flex', alignItems:'center', gap:4, padding:'2px 8px', borderRadius:20, background:'var(--accent-dim)', color:'var(--accent)', fontSize:11, border:'1px solid var(--accent-dim)' }}>
      {file.name}
      <button onClick={() => onRemove(file.path)} style={{ color:'var(--accent)', fontSize:10 }}>✕</button>
    </span>
  )
}

function CopyButton({ content }) {
  const [copied, setCopied] = useState(false)
  return (
    <button onClick={() => { navigator.clipboard.writeText(content); setCopied(true); setTimeout(() => setCopied(false), 1500) }}
      style={{ fontSize:11, padding:'2px 8px', border:'1px solid var(--border)', borderRadius:'var(--radius-sm)', color:'var(--text-3)', cursor:'pointer', background:'transparent' }}
      onMouseEnter={e => e.currentTarget.style.color='var(--text-1)'}
      onMouseLeave={e => e.currentTarget.style.color='var(--text-3)'}
    >{copied ? '✓ Đã copy' : '⎘ Copy'}</button>
  )
}

function shortPath(p = '') { return p.replace(/\\/g,'/').split('/').slice(-3).join('/') }

// Badge file ops (write + delete)
function FileOpsBadge({ filesWritten = [], filesDeleted = [] }) {
  const [exp, setExp] = useState(false)
  if (!filesWritten.length && !filesDeleted.length) return null
  const okW = filesWritten.filter(f=>f.success), okD = filesDeleted.filter(f=>f.success)
  const fail = [...filesWritten,...filesDeleted].filter(f=>!f.success)
  const BADGE = {
    create: { label:'NEW',    color:'var(--green)', bg:'var(--green-dim)' },
    update: { label:'UPDATE', color:'var(--blue)',  bg:'rgba(96,165,250,0.15)' },
    delete: { label:'DEL',    color:'var(--amber)', bg:'rgba(251,191,36,0.15)' },
  }
  return (
    <div style={{ marginTop:8, border:'1px solid var(--border)', borderRadius:'var(--radius-md)', overflow:'hidden', fontSize:12 }}>
      <div onClick={() => setExp(e=>!e)} style={{ display:'flex', alignItems:'center', gap:8, padding:'5px 10px', background:'var(--bg-3)', cursor:'pointer' }}>
        <span>{fail.length ? '⚠️' : '✅'}</span>
        <span style={{ flex:1, display:'flex', gap:8 }}>
          {okW.length > 0 && <span style={{ color:'var(--green)' }}>✓ {okW.length} ghi</span>}
          {okD.length > 0 && <span style={{ color:'var(--amber)' }}>🗑 {okD.length} xóa</span>}
          {fail.length > 0 && <span style={{ color:'var(--red)' }}>✗ {fail.length} lỗi</span>}
        </span>
        <span style={{ color:'var(--text-3)', fontSize:10 }}>{exp ? '▲' : '▼'}</span>
      </div>
      {exp && (
        <div style={{ background:'var(--bg-1)' }}>
          {filesWritten.map((f,i) => {
            const b = BADGE[f.action] || BADGE.create
            return (
              <div key={'w'+i} style={{ display:'flex', alignItems:'center', gap:8, padding:'4px 10px', borderTop:'1px solid var(--border)' }}>
                <span style={{ fontSize:10, padding:'1px 4px', borderRadius:3, background:b.bg, color:b.color }}>{b.label}</span>
                <span style={{ fontFamily:'var(--font-code)', fontSize:11, color:f.success?'var(--text-1)':'var(--red)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{shortPath(f.path)}</span>
                {f.error && <span style={{ color:'var(--red)', fontSize:10 }}>{f.error}</span>}
              </div>
            )
          })}
          {filesDeleted.map((f,i) => (
            <div key={'d'+i} style={{ display:'flex', alignItems:'center', gap:8, padding:'4px 10px', borderTop:'1px solid var(--border)' }}>
              <span style={{ fontSize:10, padding:'1px 4px', borderRadius:3, background:BADGE.delete.bg, color:BADGE.delete.color }}>DEL</span>
              <span style={{ fontFamily:'var(--font-code)', fontSize:11, color:f.success?'var(--text-1)':'var(--red)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{shortPath(f.path)}</span>
              {f.error && <span style={{ color:'var(--red)', fontSize:10 }}>{f.error}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// Plan overview + step progress
function AgentPlan({ plan, steps, currentStepId, doneStepIds }) {
  if (!plan) return null
  return (
    <div style={{ marginTop:10, border:'1px solid var(--border)', borderRadius:'var(--radius-md)', overflow:'hidden', fontSize:12 }}>
      <div style={{ padding:'6px 10px', background:'var(--bg-3)', color:'var(--text-2)', display:'flex', alignItems:'center', gap:6 }}>
        <span>🗂</span>
        <span style={{ flex:1 }}>{plan}</span>
      </div>
      {steps.length > 0 && (
        <div style={{ background:'var(--bg-1)' }}>
          {steps.map(s => {
            const isDone    = doneStepIds.includes(s.id)
            const isCurrent = currentStepId === s.id && !isDone
            return (
              <div key={s.id} style={{ display:'flex', alignItems:'flex-start', gap:8, padding:'5px 10px', borderTop:'1px solid var(--border)' }}>
                <span style={{ flexShrink:0, width:16, textAlign:'center', marginTop:1 }}>
                  {isDone ? '✓' : isCurrent ? <span style={{ display:'inline-block', animation:'spin 1s linear infinite' }}>⟳</span> : '○'}
                </span>
                <div>
                  <div style={{ color: isDone ? 'var(--green)' : isCurrent ? 'var(--accent)' : 'var(--text-3)', fontWeight: isCurrent ? 500 : 400 }}>
                    {s.title}
                  </div>
                  {(isCurrent || isDone) && s.description && (
                    <div style={{ color:'var(--text-3)', fontSize:11, marginTop:2 }}>{s.description}</div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  )
}

function Message({ msg, isLast, onRetry }) {
  const isUser  = msg.role === 'user'
  const isError = !isUser && msg.content?.startsWith('❌')
  const [hovered, setHovered] = useState(false)

  return (
    <div style={{ display:'flex', flexDirection:'column', alignItems:isUser?'flex-end':'flex-start', marginBottom:12 }}
      onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}
    >
      <div style={{ display:'flex', alignItems:'flex-start', gap:8, maxWidth:'82%', flexDirection:isUser?'row-reverse':'row' }}>
        {!isUser && (
          <div style={{ width:28, height:28, borderRadius:'50%', background:isError?'rgba(248,113,113,0.15)':'var(--accent-dim)', color:isError?'var(--red)':'var(--accent)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:13, flexShrink:0, marginTop:2 }}>
            AI
          </div>
        )}
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ padding:'10px 14px', borderRadius:isUser?'12px 12px 4px 12px':'12px 12px 12px 4px', background:isUser?'var(--accent-dim)':isError?'rgba(248,113,113,0.07)':'var(--bg-2)', border:`1px solid ${isUser?'var(--accent-dim)':isError?'rgba(248,113,113,0.3)':'var(--border)'}`, color:'var(--text-1)', fontSize:13, lineHeight:1.7 }}>
            {isUser
              ? <span style={{ whiteSpace:'pre-wrap' }}>{msg.content}</span>
              : <ReactMarkdown components={mdComponents}>{msg.content}</ReactMarkdown>
            }
          </div>

          {/* Plan + steps */}
          {!isUser && msg.plan != null && (
            <AgentPlan
              plan={msg.plan}
              steps={msg.planSteps || []}
              currentStepId={msg.currentStepId}
              doneStepIds={msg.doneStepIds || []}
            />
          )}

          {/* File ops badge */}
          {!isUser && (msg.filesWritten?.length > 0 || msg.filesDeleted?.length > 0) && (
            <FileOpsBadge filesWritten={msg.filesWritten} filesDeleted={msg.filesDeleted} />
          )}
        </div>
      </div>

      <div style={{ display:'flex', gap:4, marginTop:4, paddingLeft:isUser?0:36, opacity:hovered||isLast?1:0, transition:'opacity 0.15s', justifyContent:isUser?'flex-end':'flex-start' }}>
        {!isUser && <CopyButton content={msg.content} />}
        {((isUser && isLast) || (isError && isLast)) && (
          <button onClick={() => onRetry(msg)}
            style={{ fontSize:11, padding:'2px 8px', border:'1px solid var(--border)', borderRadius:'var(--radius-sm)', color:'var(--text-3)', cursor:'pointer', background:'transparent' }}
            onMouseEnter={e => { e.currentTarget.style.color='var(--accent)'; e.currentTarget.style.borderColor='var(--accent)' }}
            onMouseLeave={e => { e.currentTarget.style.color='var(--text-3)'; e.currentTarget.style.borderColor='var(--border)' }}
          >↺ Thử lại</button>
        )}
      </div>
    </div>
  )
}

function ThinkingIndicator({ label, onCancel }) {
  return (
    <div style={{ display:'flex', alignItems:'center', gap:8, padding:'8px 0' }}>
      <div style={{ width:28, height:28, borderRadius:'50%', background:'var(--accent-dim)', color:'var(--accent)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:13 }}>AI</div>
      <div style={{ display:'flex', gap:4 }}>
        {[0,150,300].map(d => <div key={d} style={{ width:6, height:6, borderRadius:'50%', background:'var(--accent)', animation:'pulse 1.2s ease infinite', animationDelay:`${d}ms` }} />)}
      </div>
      {label && <span style={{ fontSize:11, color:'var(--text-3)' }}>{label}</span>}
      <button onClick={onCancel}
        style={{ marginLeft:8, fontSize:11, padding:'2px 8px', border:'1px solid var(--border)', borderRadius:'var(--radius-sm)', color:'var(--text-3)', cursor:'pointer', background:'transparent' }}
        onMouseEnter={e => { e.currentTarget.style.color='var(--red)'; e.currentTarget.style.borderColor='var(--red)' }}
        onMouseLeave={e => { e.currentTarget.style.color='var(--text-3)'; e.currentTarget.style.borderColor='var(--border)' }}
      >✕ Hủy</button>
      <style>{`@keyframes pulse{0%,80%,100%{opacity:.2}40%{opacity:1}}`}</style>
    </div>
  )
}

// ─── Auto-extract helper ────────────────────────────────────────────────────

async function triggerAutoExtract(userMsg, aiReply) {
  if (!aiReply || aiReply.length < 200) return []
  try {
    const res = await fetch('http://localhost:8765/experiences/auto-extract', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ user_message: userMsg, ai_reply: aiReply }),
    })
    const data = await res.json()
    return data.saved || []
  } catch {
    return []
  }
}

// ─── Toast kinh nghiệm được lưu ──────────────────────────────────────────────

function ExperienceToast({ experiences, onClose }) {
  useEffect(() => {
    const t = setTimeout(onClose, 6000)
    return () => clearTimeout(t)
  }, [onClose])

  if (!experiences.length) return null
  return (
    <div style={{
      position: 'fixed', bottom: 24, right: 24, zIndex: 9999,
      display: 'flex', flexDirection: 'column', gap: 6, maxWidth: 320,
    }}>
      {experiences.map(exp => (
        <div key={exp.id} style={{
          background: 'var(--bg-2)', border: '1px solid var(--accent-dim)',
          borderLeft: '3px solid var(--accent)', borderRadius: 'var(--radius-md)',
          padding: '10px 14px', boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
          animation: 'slideIn 0.2s ease',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <span style={{ fontSize: 14 }}>📚</span>
            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent)' }}>Đã lưu kinh nghiệm</span>
            <button onClick={onClose} style={{
              marginLeft: 'auto', background: 'none', border: 'none',
              color: 'var(--text-3)', cursor: 'pointer', fontSize: 13, lineHeight: 1,
            }}>×</button>
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-1)', fontWeight: 500, marginBottom: 2 }}>
            {exp.title}
          </div>
          {exp.tags?.length > 0 && (
            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginTop: 4 }}>
              {exp.tags.map(t => (
                <span key={t} style={{
                  fontSize: 10, padding: '1px 6px', borderRadius: 20,
                  background: 'var(--accent-dim)', color: 'var(--accent)',
                }}>{t}</span>
              ))}
            </div>
          )}
        </div>
      ))}
      <style>{`@keyframes slideIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}`}</style>
    </div>
  )
}

// ─── Main ChatPanel ───────────────────────────────────────────────────────────

export default function ChatPanel() {
  const { messages, addMessage, setThinking, isThinking, fileContexts, removeFileContext, projectPath, setFileTree } = useAppStore()
  const [input, setInput]           = useState('')
  const [backendOk, setBackendOk]   = useState(null)
  const [thinkLabel, setThinkLabel] = useState('')
  const [toastExps, setToastExps]   = useState([])
  const bottomRef      = useRef(null)
  const cancelRef      = useRef(null)
  const aiMsgIdRef     = useRef(null)
  const lastUserMsgRef = useRef('')

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior:'smooth' }) }, [messages, isThinking])
  useEffect(() => { agentApi.health().then(() => setBackendOk(true)).catch(() => setBackendOk(false)) }, [])

  const reloadTree = useCallback(async () => {
    const { projectPath: proj } = useAppStore.getState()
    if (!proj || !window.electronAPI) return
    try {
      const tree = await readTreeRecursive(proj, 0, 6)
      setFileTree(tree)
    } catch {}
  }, [setFileTree])

  // Patch AI message đang stream (by index)
  const patchAiMsg = useCallback((patch) => {
    const idx = aiMsgIdRef.current
    if (idx == null) return
    useAppStore.setState(s => {
      const msgs = [...s.messages]
      if (msgs[idx]) msgs[idx] = { ...msgs[idx], ...patch }
      return { messages: msgs }
    })
  }, [])

  const callAgent = useCallback((userMsg) => {
    if (cancelRef.current) cancelRef.current.cancel()

    setThinking(true)
    setThinkLabel('Đang lập kế hoạch...')

    // Thêm AI message placeholder
    const { messages: cur, fileContexts: ctx, projectPath: proj } = useAppStore.getState()
    const history = cur.slice(-20, -1).map(m => ({ role:m.role, content:m.content }))

    addMessage({
      role:'assistant', content:'', isStreaming:true,
      plan:null, planSteps:[], currentStepId:null, doneStepIds:[],
      filesWritten:[], filesDeleted:[],
    })
    // Lấy index của message vừa thêm
    setTimeout(() => {
      aiMsgIdRef.current = useAppStore.getState().messages.length - 1
    }, 0)

    let anyFileOp = false

    const stream = agentApi.chatStream(userMsg, ctx, history, proj, (event) => {
      const { type, data } = event

      if (type === 'plan') {
        setThinkLabel(data.is_complex ? `Lập kế hoạch: ${data.steps?.length} bước` : 'Đang xử lý...')
        patchAiMsg({
          plan:      data.summary,
          planSteps: data.steps || [],
        })

      } else if (type === 'step_start') {
        setThinkLabel(`Bước ${data.step_id}: ${data.title}`)
        patchAiMsg({ currentStepId: data.step_id })

      } else if (type === 'step_done') {
        const written  = data.files_written  || []
        const deleted  = data.files_deleted  || []
        if (written.some(f=>f.success) || deleted.some(f=>f.success)) reloadTree()
        useAppStore.setState(s => {
          const msgs = [...s.messages]
          const idx  = aiMsgIdRef.current
          if (msgs[idx]) {
            msgs[idx] = {
              ...msgs[idx],
              doneStepIds:  [...(msgs[idx].doneStepIds||[]), data.step_id],
              currentStepId: null,
              filesWritten:  [...(msgs[idx].filesWritten||[]),  ...written],
              filesDeleted:  [...(msgs[idx].filesDeleted||[]), ...deleted],
            }
          }
          return { messages: msgs }
        })

      } else if (type === 'done') {
        const written = data.files_written  || []
        const deleted = data.files_deleted  || []
        if (written.some(f=>f.success) || deleted.some(f=>f.success)) reloadTree()
        const finalReply = data.reply || ''
        patchAiMsg({
          content:       finalReply,
          isStreaming:   false,
          currentStepId: null,
          filesWritten:  [...(useAppStore.getState().messages[aiMsgIdRef.current]?.filesWritten||[]), ...written],
          filesDeleted:  [...(useAppStore.getState().messages[aiMsgIdRef.current]?.filesDeleted||[]), ...deleted],
        })
        setThinking(false)
        setThinkLabel('')
        // Auto-extract trong background — không block UI
        triggerAutoExtract(lastUserMsgRef.current, finalReply).then(saved => {
          if (saved.length > 0) setToastExps(saved)
        })

      } else if (type === 'error') {
        patchAiMsg({ content:`❌ ${data.message}`, isStreaming:false })
        setThinking(false)
        setThinkLabel('')
      }
    })

    cancelRef.current = stream
  }, [addMessage, setThinking, patchAiMsg, reloadTree])

  const send = useCallback((text) => {
    const msg = (text || input).trim()
    if (!msg || isThinking) return
    setInput('')
    lastUserMsgRef.current = msg
    addMessage({ role:'user', content:msg })
    callAgent(msg)
  }, [input, isThinking, addMessage, callAgent])

  const handleRetry = useCallback((msg) => {
    if (isThinking) return
    const { messages: cur } = useAppStore.getState()
    let userContent = ''
    if (msg.role === 'user') {
      userContent = msg.content
      const idx = cur.findIndex(m => m.timestamp === msg.timestamp)
      useAppStore.setState({ messages: cur.slice(0, idx) })
    } else {
      const last = [...cur].reverse().find(m => m.role === 'user')
      if (!last) return
      userContent = last.content
      useAppStore.setState({ messages: cur.slice(0, -1) })
    }
    addMessage({ role:'user', content:userContent })
    callAgent(userContent)
  }, [isThinking, addMessage, callAgent])

  const handleCancel = useCallback(() => {
    if (cancelRef.current) cancelRef.current.cancel()
    patchAiMsg({ content:'⚠️ Đã hủy.', isStreaming:false })
    setThinking(false)
    setThinkLabel('')
  }, [patchAiMsg, setThinking])

  const s = {
    root:       { display:'flex', flexDirection:'column', height:'100%', background:'var(--bg-0)' },
    messages:   { flex:1, overflowY:'auto', padding:'16px 20px' },
    empty:      { textAlign:'center', color:'var(--text-3)', marginTop:60 },
    quickRow:   { display:'flex', gap:6, flexWrap:'wrap', padding:'10px 20px', borderTop:'1px solid var(--border)' },
    quickBtn:   { fontSize:11, padding:'4px 10px', border:'1px solid var(--border)', borderRadius:20, color:'var(--text-2)', cursor:'pointer', background:'var(--bg-1)' },
    inputArea:  { padding:'10px 16px 14px', background:'var(--bg-1)', borderTop:'1px solid var(--border)' },
    contextRow: { display:'flex', gap:6, flexWrap:'wrap', marginBottom:8 },
    inputRow:   { display:'flex', gap:8, alignItems:'flex-end' },
    textarea:   { flex:1, padding:'8px 12px', resize:'none', height:72, lineHeight:1.5, background:'var(--bg-2)', border:'1px solid var(--border)', borderRadius:'var(--radius-md)', color:'var(--text-1)', fontSize:13 },
    sendBtn:    { padding:'8px 16px', background:'var(--accent)', border:'none', borderRadius:'var(--radius-md)', color:'#fff', fontWeight:500, cursor:'pointer', height:36, alignSelf:'flex-end', opacity:isThinking?0.5:1 },
    status:     { fontSize:10, color:backendOk===false?'var(--red)':'var(--green)', marginTop:6 },
  }

  return (
    <div style={s.root}>
      {toastExps.length > 0 && (
        <ExperienceToast experiences={toastExps} onClose={() => setToastExps([])} />
      )}
      <div style={s.messages}>
        {messages.length === 0 && (
          <div style={s.empty}>
            <div style={{ fontSize:32, marginBottom:12 }}>🤖</div>
            <div style={{ color:'var(--text-2)', fontSize:14 }}>AI Developer Agent sẵn sàng</div>
            <div style={{ color:'var(--text-3)', fontSize:12, marginTop:6 }}>Thử: "Implement module authentication với JWT" hoặc "Tạo Circuit Breaker cho api-gateway"</div>
          </div>
        )}
        {messages.map((m, i) => (
          <Message key={i} msg={m} isLast={i===messages.length-1} onRetry={handleRetry} />
        ))}
        {isThinking && <ThinkingIndicator label={thinkLabel} onCancel={handleCancel} />}
        <div ref={bottomRef} />
      </div>

      <div style={s.quickRow}>
        {QUICK_PROMPTS.map(q => (
          <button key={q.label} style={s.quickBtn} onClick={() => send(q.prompt)}
            onMouseEnter={e => e.currentTarget.style.borderColor='var(--accent)'}
            onMouseLeave={e => e.currentTarget.style.borderColor='var(--border)'}
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
          <textarea style={s.textarea} value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key==='Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
            placeholder="Ví dụ: 'Implement module Payment với Stripe' hoặc 'Refactor toàn bộ auth service'"
            disabled={isThinking}
          />
          <button style={s.sendBtn} onClick={() => send()} disabled={isThinking}>
            {isThinking ? '...' : '↑ Gửi'}
          </button>
        </div>
        {backendOk !== null && (
          <div style={s.status}>{backendOk ? '● backend connected' : '● backend offline'}</div>
        )}
      </div>
    </div>
  )
}
