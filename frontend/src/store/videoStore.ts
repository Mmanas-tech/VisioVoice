import { create } from 'zustand'
import type { Video, UploadProgress } from '@/types/api'

interface VideoState {
  uploads: UploadProgress[]
  addUpload: (upload: UploadProgress) => void
  updateUpload: (fileName: string, updates: Partial<UploadProgress>) => void
  removeUpload: (fileName: string) => void
}

export const useVideoStore = create<VideoState>((set) => ({
  uploads: [],

  addUpload: (upload) => set((state) => ({ uploads: [...state.uploads, upload] })),
  updateUpload: (fileName, updates) =>
    set((state) => ({
      uploads: state.uploads.map((u) => (u.fileName === fileName ? { ...u, ...updates } : u)),
    })),
  removeUpload: (fileName) =>
    set((state) => ({ uploads: state.uploads.filter((u) => u.fileName !== fileName) })),
}))
