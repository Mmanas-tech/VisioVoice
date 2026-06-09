import { create } from 'zustand'
import type { Video, UploadProgress } from '@/types/api'

interface VideoState {
  videos: Video[]
  currentVideo: Video | null
  uploads: UploadProgress[]
  isLoading: boolean
  page: number
  total: number
  setVideos: (videos: Video[]) => void
  setCurrentVideo: (video: Video | null) => void
  addUpload: (upload: UploadProgress) => void
  updateUpload: (fileName: string, updates: Partial<UploadProgress>) => void
  removeUpload: (fileName: string) => void
  setIsLoading: (loading: boolean) => void
  setPage: (page: number) => void
  setTotal: (total: number) => void
}

export const useVideoStore = create<VideoState>((set) => ({
  videos: [],
  currentVideo: null,
  uploads: [],
  isLoading: false,
  page: 1,
  total: 0,

  setVideos: (videos) => set({ videos }),
  setCurrentVideo: (video) => set({ currentVideo: video }),
  addUpload: (upload) => set((state) => ({ uploads: [...state.uploads, upload] })),
  updateUpload: (fileName, updates) =>
    set((state) => ({
      uploads: state.uploads.map((u) => (u.fileName === fileName ? { ...u, ...updates } : u)),
    })),
  removeUpload: (fileName) =>
    set((state) => ({ uploads: state.uploads.filter((u) => u.fileName !== fileName) })),
  setIsLoading: (isLoading) => set({ isLoading }),
  setPage: (page) => set({ page }),
  setTotal: (total) => set({ total }),
}))
