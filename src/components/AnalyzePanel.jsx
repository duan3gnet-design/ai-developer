import React, { useState } from 'react'
import { useAppStore } from '../store/appStore'
import { agentApi } from '../hooks/useAgent'
import ReactMarkdown from 'react-markdown'

const FOCUS_OPTIONS = [
  { value: null, label: '🔭 Tổng quan', desc: 'Phân tích toàn diện' },
  { value: 'bugs', label: '🐛 Bug hunt', desc: 'Tìm lỗi logic và tiềm ẩn' },
  { value: 'architecture', label: '🏗 Architecture', desc: 'Kiến trúc và design pattern' },
  { value: 'performance', label: '⚡ Performance', desc: 'Bottleneck và tối ưu' },
]

export default function AnalyzePanel() {
  const { projectPath } = useAppStore()
  const [focus, setFocus] = useState(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const run = async () => {
    if (!projectPath) { setError('Chưa chọn project path'); return }
    setLoading(true)
    setResult(null)
    setError(null)
    try {
      const res = await agentApi.analyze(projectPath, focus)
      setResult(res.data)
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setLoading(false)
    }
  }

  const s = {
    root: { display: 'flex', flexDirection: 'column', height: '100%', background: 'var(--bg-0)', padding: 24, overflowY: 'auto' },
    title: { fontSize: 15, fontWeight: 500, marginBottom: 4 },
    subtitle: { fontSize: 12, color: 'var(--text-3)', marginBottom: 20 },
    focusGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 20 },
    focusCard: (active) => ({
      padding: '10px 14px', border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
      borderRadius: 'var(--radius-md)', cursor: 'pointer',
      background: active ? 'var(--accent-dim)' : 'var(--bg-1)',
      transition: 'all 0.1s',
    }),
    focusLabel: { fontSize: 13, color: 'var(--text-1)', marginBottom: 2 },
    focusDesc: { fontSize: 11, color: 'var(--text-3)' },
    runBtn: { padding: '10px 24px', background: 'var(--accent)', border: 'none', borderRadius: 'var(--radius-md)', color: '#fff', fontWeight: 500, cursor: 'pointer', fontSize: 13, marginBottom: 20, opacity: loading ? 0.6 : 1 },
    resultBox: { background: 'var(--bg-1)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: 20, fontSize: 13, lineHeight: 1.7, color: 'var(--text-1)' },
    error: { color: 'var(--red)', fontSize: 12, marginBottom: 12 },
    spinner: { color: 'var(--text-3)', marginTop: 20 },
    langs: { display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 },
    langBadge: { fontSize: 11, padding: '2px 8px', borderRadius: 20, background: 'var(--bg-3)', color: 'var(--text-2)', border: '1px solid var(--border)' },
  }

  return (
    <div style={s.root}>
      <div style={s.title}>📊 Phân tích Project</div>
      <div style={s.subtitle}>{projectPath || 'Chưa chọn project'}</div>

      <div style={s.focusGrid}>
        {FOCUS_OPTIONS.map(opt => (
          <div key={String(opt.value)} style={s.focusCard(focus === opt.value)} onClick={() => setFocus(opt.value)}>
            <div style={s.focusLabel}>{opt.label}</div>
            <div style={s.focusDesc}>{opt.desc}</div>
          </div>
        ))}
      </div>

      {error && <div style={s.error}>❌ {error}</div>}

      <button style={s.runBtn} onClick={run} disabled={loading}>
        {loading ? '⏳ Đang phân tích...' : '▶ Chạy phân tích'}
      </button>

      {result && (
        <>
          {result.summary?.languages && (
            <div style={s.langs}>
              {Object.entries(result.summary.languages).map(([lang, count]) => (
                <span key={lang} style={s.langBadge}>{lang} ({count})</span>
              ))}
            </div>
          )}
          <div style={s.resultBox}>
            <ReactMarkdown
              components={{
                code({ inline, children }) {
                  return inline
                    ? <code style={{ background: 'var(--bg-3)', padding: '1px 5px', borderRadius: 3, fontSize: 12, fontFamily: 'var(--font-code)' }}>{children}</code>
                    : <pre style={{ background: 'var(--bg-0)', border: '1px solid var(--border)', borderRadius: 4, padding: 10, overflowX: 'auto', fontSize: 12, fontFamily: 'var(--font-code)' }}><code>{children}</code></pre>
                },
                p({ children }) { return <p style={{ marginBottom: 10 }}>{children}</p> },
                h2({ children }) { return <h2 style={{ fontSize: 14, fontWeight: 500, margin: '16px 0 8px', color: 'var(--accent)' }}>{children}</h2> },
                h3({ children }) { return <h3 style={{ fontSize: 13, fontWeight: 500, margin: '12px 0 6px' }}>{children}</h3> },
                ul({ children }) { return <ul style={{ paddingLeft: 20, marginBottom: 8 }}>{children}</ul> },
                li({ children }) { return <li style={{ marginBottom: 4 }}>{children}</li> },
              }}
            >
              {result.analysis}
            </ReactMarkdown>
          </div>
        </>
      )}
    </div>
  )
}
