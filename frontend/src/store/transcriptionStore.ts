import { create } from 'zustand'
import type { Transcription } from '@/types/api'

interface TranscriptionState {
  transcriptions: Record<string, Transcription>
  currentTranscription: Transcription | null
  progress: Record<string, number>
  isLoading: boolean
  setCurrentTranscription: (t: Transcription | null) => void
  updateTranscription: (id: string, data: Partial<Transcription>) => void
  setProgress: (id: string, progress: number) => void
  setIsLoading: (loading: boolean) => void
}

export const useTranscriptionStore = create<TranscriptionState>((set) => ({
  transcriptions: {},
  currentTranscription: null,
  progress: {},
  isLoading: false,

  setCurrentTranscription: (t) => set({ currentTranscription: t }),
  updateTranscription: (id, data) =>
    set((state) => ({
      transcriptions: {
        ...state.transcriptions,
        [id]: { ...state.transcriptions[id], ...data } as Transcription,
      },
      currentTranscription:
        state.currentTranscription?.id === id
          ? { ...state.currentTranscription, ...data }
          : state.currentTranscription,
    })),
  setProgress: (id, progress) =>
    set((state) => ({ progress: { ...state.progress, [id]: progress } })),
  setIsLoading: (isLoading) => set({ isLoading }),
}))
