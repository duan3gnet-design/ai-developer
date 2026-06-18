import axios from 'axios'

const BASE = 'http://localhost:8765'
const api = axios.create({ baseURL: BASE, timeout: 120_000 })

export const agentApi = {
  health: () => api.get('/health'),

  chat: (message, fileContexts, history, projectPath) =>
    api.post('/chat', { message, file_contexts: fileContexts, conversation_history: history, project_path: projectPath }),

  analyze: (projectPath, focus = null) =>
    api.post('/analyze', { project_path: projectPath, focus }),

  generate: (prompt, targetPath, fileContexts, language) =>
    api.post('/generate', { prompt, target_path: targetPath, file_contexts: fileContexts, language }),

  writeFile: (path, content) =>
    api.post('/write-file', { path, content }),

  readProject: (path) =>
    api.get('/read-project', { params: { path } }),
}
