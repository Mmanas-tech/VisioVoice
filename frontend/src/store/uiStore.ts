import { create } from 'zustand'

interface UIState {
  sidebarOpen: boolean
  activeTab: string
  theme: 'dark' | 'light'
  toasts: Toast[]
  setSidebarOpen: (open: boolean) => void
  setActiveTab: (tab: string) => void
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

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,
  activeTab: 'upload',
  theme: 'dark',
  toasts: [],

  setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
  setActiveTab: (activeTab) => set({ activeTab }),
  addToast: (toast) =>
    set((state) => ({
      toasts: [...state.toasts, { ...toast, id: String(++toastId) }],
    })),
  removeToast: (id) =>
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),
}))
