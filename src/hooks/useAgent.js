const BASE = 'http://localhost:8765'

export const agentApi = {
  health: () => fetch(`${BASE}/health`).then(r => r.json()),

  /**
   * Stream chat qua SSE.
   * onEvent(event) được gọi mỗi khi nhận 1 event từ server.
   * Trả về { cancel } để hủy stream.
   */
  chatStream(message, fileContexts, history, projectPath, onEvent) {
    const controller = new AbortController()

    fetch(`${BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        file_contexts:        fileContexts,
        conversation_history: history,
        project_path:         projectPath,
      }),
      signal: controller.signal,
    }).then(async res => {
      if (!res.ok) {
        const text = await res.text()
        onEvent({ type: 'error', data: { message: `HTTP ${res.status}: ${text}` } })
        return
      }
      const reader  = res.body.getReader()
      const decoder = new TextDecoder()
      let   buffer  = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        // Parse từng dòng "data: {...}"
        const lines = buffer.split('\n')
        buffer = lines.pop() // phần chưa hoàn chỉnh giữ lại
        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed.startsWith('data:')) continue
          const json = trimmed.slice(5).trim()
          if (!json) continue
          try { onEvent(JSON.parse(json)) } catch { /* ignore malformed */ }
        }
      }
    }).catch(err => {
      if (err.name !== 'AbortError') {
        onEvent({ type: 'error', data: { message: err.message } })
      }
    })

    return { cancel: () => controller.abort() }
  },

  analyze: (projectPath, focus = null) =>
    fetch(`${BASE}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_path: projectPath, focus }),
    }).then(r => r.json()),
}
