import { create } from 'zustand'

interface UIState {
  sidebarOpen: boolean
  activeTab: string
  theme: 'dark' | 'light'
  toasts: Toast[]
  setSidebarOpen: (open: boolean) => void
  setActiveTab: (tab: string) => void
  setTheme: (theme: 'dark' | 'light') => void
  addToast: (toast: Omit<Toast, 'id'>) => void
  removeToast: (id: string) => void
}

interface Toast {
  id: string
  title: string
  description?: string
  variant?: 'default' | 'success' | 'error' | 'warning'
}

let toastId = 0

const getInitialTheme = (): 'dark' | 'light' => {
  if (typeof window !== 'undefined') {
    const stored = localStorage.getItem('theme')
    if (stored === 'dark' || stored === 'light') return stored
  }
  return 'dark'
}

const applyTheme = (theme: 'dark' | 'light') => {
  const root = document.documentElement
  if (theme === 'dark') {
    root.classList.add('dark')
    root.classList.remove('light')
  } else {
    root.classList.add('light')
    root.classList.remove('dark')
  }
  localStorage.setItem('theme', theme)
}

const initialTheme = getInitialTheme()
applyTheme(initialTheme)

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,
  activeTab: 'upload',
  theme: initialTheme,
  toasts: [],

  setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
  setActiveTab: (activeTab) => set({ activeTab }),
  setTheme: (theme) => {
    applyTheme(theme)
    set({ theme })
  },
  addToast: (toast) =>
    set((state) => ({
      toasts: [...state.toasts, { ...toast, id: String(++toastId) }],
    })),
  removeToast: (id) =>
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),
}))
