import apiClient from './api'
import type { SynthesisResult } from '@/types/api'

export const audioService = {
  requestSynthesis: async (
    transcriptionId: string,
    params: {
      ttsBackend?: string
      language?: string
      voice?: string
      pitch?: number
      speakingRate?: number
      exportFormats?: string
      enableEnhancement?: boolean
      enableLipsync?: boolean
    } = {}
  ): Promise<{ transcription_id: string; status: string; job_id: string }> => {
    const queryParams = new URLSearchParams()
    if (params.ttsBackend) queryParams.set('tts_backend', params.ttsBackend)
    if (params.language) queryParams.set('language', params.language)
    if (params.voice) queryParams.set('voice', params.voice)
    if (params.pitch !== undefined) queryParams.set('pitch', String(params.pitch))
    if (params.speakingRate !== undefined) queryParams.set('speaking_rate', String(params.speakingRate))
    if (params.exportFormats) queryParams.set('export_formats', params.exportFormats)
    if (params.enableEnhancement !== undefined) queryParams.set('enable_enhancement', String(params.enableEnhancement))
    if (params.enableLipsync !== undefined) queryParams.set('enable_lipsync', String(params.enableLipsync))

    const response = await apiClient.post(`/audio/synthesize/${transcriptionId}?${queryParams}`)
    return response.data
  },

  getSynthesisStatus: async (transcriptionId: string): Promise<SynthesisResult> => {
    const response = await apiClient.get(`/audio/synthesize/${transcriptionId}/status`)
    return response.data
  },

  downloadAudio: async (transcriptionId: string, format: string): Promise<Blob> => {
    const response = await apiClient.get(`/audio/synthesize/${transcriptionId}/download/${format}`, {
      responseType: 'blob',
    })
    return response.data
  },

  downloadSubtitle: async (transcriptionId: string, format: string): Promise<Blob> => {
    const response = await apiClient.get(`/audio/synthesize/${transcriptionId}/subtitle/${format}`, {
      responseType: 'blob',
    })
    return response.data
  },

  getBackends: async (): Promise<{ available_backends: string[]; backends: Record<string, unknown> }> => {
    const response = await apiClient.get('/audio/backends')
    return response.data
  },
}
