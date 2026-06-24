import { create } from 'zustand'

export const useAppStore = create((set, get) => ({

  // ─── Project / Filesystem ─────────────────────────────────────────────────
  projectPath: '',
  fileTree: [],
  openFiles: [],        // [{ path, name, content, language, dirty }]
  activeFilePath: null,

  setProjectPath: (p) => set({ projectPath: p }),
  setFileTree: (tree) => set({ fileTree: tree }),

  openFile: (file) => {
    const { openFiles } = get()
    const exists = openFiles.find(f => f.path === file.path)
    if (!exists) {
      set({ openFiles: [...openFiles, file], activeFilePath: file.path })
    } else {
      set({ activeFilePath: file.path })
    }
  },

  closeFile: (path) => {
    const { openFiles, activeFilePath } = get()
    const filtered = openFiles.filter(f => f.path !== path)
    let newActive = activeFilePath
    if (activeFilePath === path) {
      const idx = openFiles.findIndex(f => f.path === path)
      newActive = filtered[Math.max(0, idx - 1)]?.path ?? null
    }
    set({ openFiles: filtered, activeFilePath: newActive })
  },

  updateFileContent: (path, content) => {
    set(s => ({
      openFiles: s.openFiles.map(f =>
        f.path === path ? { ...f, content, dirty: true } : f
      )
    }))
  },

  markFileSaved: (path) => {
    set(s => ({
      openFiles: s.openFiles.map(f =>
        f.path === path ? { ...f, dirty: false } : f
      )
    }))
  },

  getActiveFile: () => {
    const { openFiles, activeFilePath } = get()
    return openFiles.find(f => f.path === activeFilePath) ?? null
  },

  // ─── Chat ─────────────────────────────────────────────────────────────────
  messages: [],           // [{ role, content, timestamp }]
  isThinking: false,
  fileContexts: [],       // files đang được attach vào chat

  addMessage: (msg) =>
    set(s => ({ messages: [...s.messages, { ...msg, timestamp: Date.now() }] })),

  setThinking: (v) => set({ isThinking: v }),
  clearMessages: () => set({ messages: [] }),

  addFileContext: (file) => {
    const { fileContexts } = get()
    if (!fileContexts.find(f => f.path === file.path)) {
      set({ fileContexts: [...fileContexts, file] })
    }
  },
  removeFileContext: (path) =>
    set(s => ({ fileContexts: s.fileContexts.filter(f => f.path !== path) })),
  clearFileContexts: () => set({ fileContexts: [] }),

  // ─── Project Context ─────────────────────────────────────────────────────────────
  projectContext: null,   // { project_name, stack, conventions, key_files, ... }
  setProjectContext: (ctx) => set({ projectContext: ctx }),
  clearProjectContext: () => set({ projectContext: null }),

  // ─── UI state ─────────────────────────────────────────────────────────────
  sidebarWidth: 260,
  activePanel: 'chat',     // 'chat' | 'analyze'
  setActivePanel: (p) => set({ activePanel: p }),
}))
