import axios, { AxiosError } from 'axios'
import { useAuthStore } from '@/store/authStore'
import { API_BASE_URL } from '@/config/constants'
import type { ApiError } from '@/types/api'

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

apiClient.interceptors.request.use((config) => {
  const tokens = useAuthStore.getState().tokens
  if (tokens?.access_token) {
    config.headers.Authorization = `Bearer ${tokens.access_token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiError>) => {
    const originalRequest = error.config

    if (error.response?.status === 401 && originalRequest) {
      try {
        await useAuthStore.getState().refreshToken()
        const tokens = useAuthStore.getState().tokens
        if (tokens?.access_token && originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${tokens.access_token}`
        }
        return apiClient(originalRequest)
      } catch {
        useAuthStore.getState().logout()
      }
    }

    return Promise.reject(error)
  }
)

export default apiClient
