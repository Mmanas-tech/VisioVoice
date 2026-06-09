import apiClient from './api'
import type { Transcription, TranscriptionJob } from '@/types/api'

export const transcriptionService = {
  startTranscription: async (
    videoId: string,
    language = 'en',
    priority = 'normal'
  ): Promise<TranscriptionJob> => {
    const response = await apiClient.post<TranscriptionJob>('/transcriptions/process', {
      video_id: videoId,
      language,
      include_timestamps: true,
      priority,
    })
    return response.data
  },

  getTranscription: async (transcriptionId: string): Promise<Transcription> => {
    const response = await apiClient.get<Transcription>(`/transcriptions/${transcriptionId}`)
    return response.data
  },

  getStatus: async (
    transcriptionId: string
  ): Promise<{ status: string; progress: number; error_message?: string }> => {
    const response = await apiClient.get(`/transcriptions/${transcriptionId}/status`)
    return response.data
  },

  exportTranscription: async (
    transcriptionId: string,
    format: string
  ): Promise<Blob> => {
    const response = await apiClient.get(`/transcriptions/${transcriptionId}/export`, {
      params: { format },
      responseType: 'blob',
    })
    return response.data
  },

  deleteTranscription: async (transcriptionId: string): Promise<void> => {
    await apiClient.delete(`/transcriptions/${transcriptionId}`)
  },
}
