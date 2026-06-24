/**
 * ExperiencePanel — Quản lý kinh nghiệm người dùng
 * để cải thiện chất lượng sinh code của AI.
 */

import React, { useState, useEffect, useCallback } from 'react'
import { useAppStore } from '../store/appStore'

const API = 'http://localhost:8765'

// ─── helpers ─────────────────────────────────────────────────────────────────

async function apiFetch(path, options = {}) {
  const res = await fetch(API + path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

function TagBadge({ tag, onRemove }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 3,
      padding: '1px 8px', borderRadius: 20,
      background: 'var(--accent-dim)', color: 'var(--accent)',
      fontSize: 11, fontWeight: 500,
    }}>
      {tag}
      {onRemove && (
        <span
          onClick={onRemove}
          style={{ cursor: 'pointer', opacity: 0.7, marginLeft: 2 }}
        >×</span>
      )}
    </span>
  )
}

// ─── Form tạo / sửa ──────────────────────────────────────────────────────────

function ExperienceForm({ initial, onSave, onCancel }) {
  const [form, setForm] = useState({
    title:    initial?.title    || '',
    context:  initial?.context  || '',
    problem:  initial?.problem  || '',
    solution: initial?.solution || '',
    tagInput: '',
    tags:     initial?.tags     || [],
  })
  const [saving, setSaving] = useState(false)
  const [error, setError]   = useState(null)

  const set = (key) => (e) => setForm(f => ({ ...f, [key]: e.target.value }))

  const addTag = () => {
    const t = form.tagInput.trim().toLowerCase()
    if (t && !form.tags.includes(t)) {
      setForm(f => ({ ...f, tags: [...f.tags, t], tagInput: '' }))
    } else {
      setForm(f => ({ ...f, tagInput: '' }))
    }
  }

  const removeTag = (tag) => setForm(f => ({ ...f, tags: f.tags.filter(t => t !== tag) }))

  const handleSubmit = async () => {
    if (!form.title.trim() || !form.problem.trim() || !form.solution.trim()) {
      setError('Vui lòng điền đủ Tiêu đề, Vấn đề và Giải pháp.')
      return
    }
    setSaving(true); setError(null)
    try {
      const body = {
        title:    form.title.trim(),
        context:  form.context.trim(),
        problem:  form.problem.trim(),
        solution: form.solution.trim(),
        tags:     form.tags,
      }
      if (initial?.id) {
        const data = await apiFetch(`/experiences/${initial.id}`, {
          method: 'PUT', body: JSON.stringify(body),
        })
        onSave(data.experience, 'update')
      } else {
        const data = await apiFetch('/experiences', {
          method: 'POST', body: JSON.stringify(body),
        })
        onSave(data.experience, 'create')
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const inp = {
    width: '100%', padding: '7px 10px', fontSize: 12,
    background: 'var(--bg-3)', border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)', color: 'var(--text-1)',
    fontFamily: 'var(--font-ui)', boxSizing: 'border-box', outline: 'none',
  }
  const label = { fontSize: 11, color: 'var(--text-3)', fontWeight: 600,
    textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 4, display: 'block' }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div>
        <span style={label}>Tiêu đề *</span>
        <input style={inp} value={form.title} onChange={set('title')}
          placeholder="VD: Luôn dùng @Transactional cho service method" />
      </div>
      <div>
        <span style={label}>Ngữ cảnh</span>
        <input style={inp} value={form.context} onChange={set('context')}
          placeholder="VD: Spring Boot, JPA, PostgreSQL" />
      </div>
      <div>
        <span style={label}>Vấn đề / Yêu cầu *</span>
        <textarea style={{ ...inp, minHeight: 70, resize: 'vertical', lineHeight: 1.5 }}
          value={form.problem} onChange={set('problem')}
          placeholder="Mô tả vấn đề hoặc pattern hay gặp..." />
      </div>
      <div>
        <span style={label}>Giải pháp / Quy tắc *</span>
        <textarea style={{ ...inp, minHeight: 120, resize: 'vertical', lineHeight: 1.5,
          fontFamily: 'var(--font-code)', fontSize: 12 }}
          value={form.solution} onChange={set('solution')}
          placeholder="Giải pháp, code mẫu, hoặc quy tắc cụ thể..." />
      </div>
      <div>
        <span style={label}>Tags</span>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 6 }}>
          {form.tags.map(t => (
            <TagBadge key={t} tag={t} onRemove={() => removeTag(t)} />
          ))}
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <input style={{ ...inp, flex: 1 }} value={form.tagInput}
            onChange={set('tagInput')}
            onKeyDown={e => (e.key === 'Enter' || e.key === ',') && (e.preventDefault(), addTag())}
            placeholder="Nhập tag rồi Enter..." />
          <button onClick={addTag} style={{
            padding: '6px 12px', background: 'var(--bg-3)',
            border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
            color: 'var(--text-2)', fontSize: 12, cursor: 'pointer',
          }}>+</button>
        </div>
      </div>

      {error && (
        <div style={{ padding: '7px 10px', background: 'rgba(248,113,113,0.1)',
          border: '1px solid rgba(248,113,113,0.3)', borderRadius: 'var(--radius-sm)',
          color: 'var(--red)', fontSize: 12 }}>⚠ {error}</div>
      )}

      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
        <button onClick={onCancel} style={{
          padding: '7px 16px', background: 'transparent',
          border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
          color: 'var(--text-2)', fontSize: 12, cursor: 'pointer',
        }}>Hủy</button>
        <button onClick={handleSubmit} disabled={saving} style={{
          padding: '7px 16px', background: 'var(--accent)',
          border: 'none', borderRadius: 'var(--radius-sm)',
          color: '#fff', fontSize: 12, cursor: saving ? 'not-allowed' : 'pointer',
          opacity: saving ? 0.6 : 1,
        }}>{saving ? 'Đang lưu...' : initial?.id ? '💾 Cập nhật' : '✅ Lưu'}</button>
      </div>
    </div>
  )
}

// ─── Card hiển thị 1 experience ───────────────────────────────────────────────

function ExperienceCard({ exp, onEdit, onDelete }) {
  const [expanded, setExpanded] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const handleDelete = async () => {
    if (!window.confirm(`Xóa "${exp.title}"?`)) return
    setDeleting(true)
    try {
      await apiFetch(`/experiences/${exp.id}`, { method: 'DELETE' })
      onDelete(exp.id)
    } catch (e) {
      alert('Lỗi xóa: ' + e.message)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div style={{
      border: '1px solid var(--border)', borderRadius: 'var(--radius-md)',
      background: 'var(--bg-2)', overflow: 'hidden',
      transition: 'border-color 0.15s',
      minHeight: expanded ? '300px' : '75px'
    }}
      onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--accent-dim)'}
      onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border)'}
    >
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'flex-start', gap: 10,
        padding: '10px 12px', cursor: 'pointer',
      }} onClick={() => setExpanded(v => !v)}>
        <span style={{ fontSize: 14, marginTop: 1, flexShrink: 0, color: 'var(--accent)' }}>
          {expanded ? '▾' : '▸'}
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-1)',
            marginBottom: 4, lineHeight: 1.3 }}>{exp.title}</div>
          {exp.context && (
            <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 4 }}>
              📌 {exp.context}
            </div>
          )}
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            {exp.tags.map(t => <TagBadge key={t} tag={t} />)}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
          <button onClick={e => { e.stopPropagation(); onEdit(exp) }} style={{
            padding: '3px 8px', background: 'var(--bg-3)',
            border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
            color: 'var(--text-3)', fontSize: 11, cursor: 'pointer',
          }}>✏️</button>
          <button onClick={e => { e.stopPropagation(); handleDelete() }} disabled={deleting} style={{
            padding: '3px 8px', background: 'var(--bg-3)',
            border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
            color: 'var(--red)', fontSize: 11,
            cursor: deleting ? 'not-allowed' : 'pointer', opacity: deleting ? 0.5 : 1,
          }}>🗑</button>
        </div>
      </div>

      {/* Body (expanded) */}
      {expanded && (
        <div style={{ borderTop: '1px solid var(--border)', padding: '10px 14px',
          display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div>
            <div style={{ fontSize: 11, color: 'var(--text-3)', fontWeight: 600,
              textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 4 }}>
              Vấn đề
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-2)', lineHeight: 1.6,
              whiteSpace: 'pre-wrap' }}>{exp.problem}</div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: 'var(--text-3)', fontWeight: 600,
              textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 4 }}>
              Giải pháp
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-1)', lineHeight: 1.6,
              whiteSpace: 'pre-wrap', fontFamily: 'var(--font-code)',
              background: 'var(--bg-3)', padding: '8px 10px',
              borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
              {exp.solution}
            </div>
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-3)', textAlign: 'right' }}>
            Cập nhật: {new Date(exp.updated_at).toLocaleString('vi-VN')}
          </div>
        </div>
      )}
    </div>
  )
}

// ─── ExperiencePanel (main) ───────────────────────────────────────────────────

export default function ExperiencePanel() {
  const [experiences, setExperiences] = useState([])
  const [loading, setLoading]         = useState(true)
  const [error, setError]             = useState(null)
  const [search, setSearch]           = useState('')
  const [mode, setMode]               = useState('list')   // 'list' | 'create' | 'edit'
  const [editing, setEditing]         = useState(null)

  const load = useCallback(async (q = '') => {
    setLoading(true); setError(null)
    try {
      const url = q ? `/experiences?q=${encodeURIComponent(q)}` : '/experiences'
      const data = await apiFetch(url)
      setExperiences(data.experiences)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  // Debounce search
  useEffect(() => {
    const t = setTimeout(() => load(search), 350)
    return () => clearTimeout(t)
  }, [search, load])

  const handleSave = (record, action) => {
    if (action === 'create') {
      setExperiences(prev => [record, ...prev])
    } else {
      setExperiences(prev => prev.map(e => e.id === record.id ? record : e))
    }
    setMode('list')
    setEditing(null)
  }

  const handleDelete = (id) => {
    setExperiences(prev => prev.filter(e => e.id !== id))
  }

  const handleEdit = (exp) => {
    setEditing(exp)
    setMode('edit')
  }

  const s = {
    root: { display: 'flex', flexDirection: 'column', height: '100%',
      background: 'var(--bg-0)', overflow: 'hidden' },
    header: { padding: '12px 16px', borderBottom: '1px solid var(--border)',
      background: 'var(--bg-1)', flexShrink: 0 },
    title: { fontSize: 14, fontWeight: 700, color: 'var(--text-1)', marginBottom: 8 },
    subtitle: { fontSize: 11, color: 'var(--text-3)', lineHeight: 1.5 },
    toolbar: { display: 'flex', gap: 8, alignItems: 'center' },
    searchBox: {
      flex: 1, padding: '6px 10px', fontSize: 12,
      background: 'var(--bg-2)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius-sm)', color: 'var(--text-1)',
      fontFamily: 'var(--font-ui)', outline: 'none',
    },
    addBtn: {
      padding: '6px 14px', background: 'var(--accent)', border: 'none',
      borderRadius: 'var(--radius-sm)', color: '#fff', fontSize: 12,
      cursor: 'pointer', fontWeight: 600, whiteSpace: 'nowrap',
    },
    body: { flex: 1, overflowY: 'auto', padding: '14px 16px',
      display: 'flex', flexDirection: 'column', gap: 10 },
    formBox: { flex: 1, overflowY: 'auto', padding: '16px' },
    formCard: { background: 'var(--bg-1)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius-md)', padding: '16px', maxWidth: 760, margin: '0 auto' },
    formTitle: { fontSize: 14, fontWeight: 700, color: 'var(--text-1)', marginBottom: 16 },
    empty: { color: 'var(--text-3)', fontSize: 13, textAlign: 'center',
      padding: '48px 24px', lineHeight: 2 },
    badge: { display: 'inline-flex', alignItems: 'center', padding: '2px 8px',
      background: 'var(--bg-3)', border: '1px solid var(--border)',
      borderRadius: 20, fontSize: 11, color: 'var(--text-3)', marginLeft: 8 },
  }

  return (
    <div style={s.root}>
      {/* Header */}
      <div style={s.header}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <div>
            <span style={s.title}>📚 Kinh nghiệm</span>
            <span style={s.badge}>{experiences.length}</span>
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-3)' }}>
            AI tự động học từ đây khi sinh code
          </div>
        </div>
        {mode === 'list' && (
          <div style={s.toolbar}>
            <input
              style={s.searchBox}
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="🔍 Tìm theo từ khóa..."
            />
            <button style={s.addBtn} onClick={() => setMode('create')}>
              + Thêm mới
            </button>
          </div>
        )}
        {mode !== 'list' && (
          <button onClick={() => { setMode('list'); setEditing(null) }} style={{
            padding: '5px 12px', background: 'var(--bg-3)',
            border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
            color: 'var(--text-2)', fontSize: 12, cursor: 'pointer',
          }}>← Quay lại</button>
        )}
      </div>

      {/* Form create/edit */}
      {(mode === 'create' || mode === 'edit') && (
        <div style={s.formBox}>
          <div style={s.formCard}>
            <div style={s.formTitle}>
              {mode === 'create' ? '✨ Thêm kinh nghiệm mới' : '✏️ Chỉnh sửa kinh nghiệm'}
            </div>
            <ExperienceForm
              initial={editing}
              onSave={handleSave}
              onCancel={() => { setMode('list'); setEditing(null) }}
            />
          </div>
        </div>
      )}

      {/* List */}
      {mode === 'list' && (
        <div style={s.body}>
          {loading && (
            <div style={{ color: 'var(--text-3)', fontSize: 12, textAlign: 'center', padding: 24 }}>
              ⟳ Đang tải...
            </div>
          )}
          {error && (
            <div style={{ padding: '8px 12px', background: 'rgba(248,113,113,0.1)',
              border: '1px solid rgba(248,113,113,0.3)', borderRadius: 'var(--radius-sm)',
              color: 'var(--red)', fontSize: 12 }}>
              ⚠ {error} — Backend có đang chạy không?
            </div>
          )}
          {!loading && !error && experiences.length === 0 && (
            <div style={s.empty}>
              📭<br />
              {search ? `Không tìm thấy kết quả cho "${search}"` : (
                <>
                  Chưa có kinh nghiệm nào.<br />
                  Nhấn <strong>+ Thêm mới</strong> để lưu quy tắc, pattern, hoặc<br />
                  giải pháp bạn muốn AI ghi nhớ khi sinh code.
                </>
              )}
            </div>
          )}
          {!loading && experiences.map(exp => (
            <ExperienceCard
              key={exp.id}
              exp={exp}
              onEdit={handleEdit}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}
    </div>
  )
}
