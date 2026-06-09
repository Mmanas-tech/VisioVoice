import apiClient from './api'
import type { Video, PaginatedResponse } from '@/types/api'

export const videoService = {
  uploadVideo: async (
    file: File,
    title?: string,
    onProgress?: (progress: number) => void
  ): Promise<Video> => {
    const formData = new FormData()
    formData.append('video_file', file)
    if (title) formData.append('title', title)

    const response = await apiClient.post<Video>('/videos/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total && onProgress) {
          const progress = Math.round((progressEvent.loaded / progressEvent.total) * 100)
          onProgress(progress)
        }
      },
    })
    return response.data
  },

  getVideos: async (
    page = 1,
    perPage = 20,
    status?: string
  ): Promise<PaginatedResponse<Video>> => {
    const params = new URLSearchParams({ page: String(page), per_page: String(perPage) })
    if (status) params.append('status', status)
    const response = await apiClient.get<PaginatedResponse<Video>>(`/videos?${params}`)
    return response.data
  },

  getVideo: async (videoId: string): Promise<Video> => {
    const response = await apiClient.get<Video>(`/videos/${videoId}`)
    return response.data
  },

  deleteVideo: async (videoId: string): Promise<void> => {
    await apiClient.delete(`/videos/${videoId}`)
  },
}
