import apiClient from './api'
import type { User, TokenResponse, AuthResponse } from '@/types/api'

interface RegisterInput {
  username: string
  email: string
  password: string
  full_name?: string
}

export const authService = {
  login: async (email: string, password: string): Promise<AuthResponse> => {
    const response = await apiClient.post<TokenResponse>('/auth/login', {
      email,
      password,
    })
    const tokens = response.data

    const userResponse = await apiClient.get<User>('/auth/me', {
      headers: { Authorization: `Bearer ${tokens.access_token}` },
    })

    return { user: userResponse.data, tokens }
  },

  register: async (data: RegisterInput): Promise<AuthResponse> => {
    const userResponse = await apiClient.post<User>('/auth/register', data)

    const loginResponse = await authService.login(data.email, data.password)
    return { user: userResponse.data, tokens: loginResponse.tokens }
  },

  logout: async (): Promise<void> => {
    try {
      await apiClient.post('/auth/logout')
    } catch {
      // Ignore logout errors
    }
  },

  refreshToken: async (refreshToken: string): Promise<TokenResponse> => {
    const response = await apiClient.post<TokenResponse>('/auth/refresh-token', {
      refresh_token: refreshToken,
    })
    return response.data
  },

  getMe: async (): Promise<User> => {
    const response = await apiClient.get<User>('/auth/me')
    return response.data
  },
}
