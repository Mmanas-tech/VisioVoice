export interface User {
  id: string
  email: string
  username: string
  full_name: string | null
  is_active: boolean
  is_admin: boolean
  created_at: string
}

export interface Video {
  id: string
  filename: string
  original_filename: string
  title: string | null
  description: string | null
  file_size: number
  duration: number | null
  fps: number | null
  resolution: string | null
  status: string
  created_at: string
  updated_at: string
}

export interface TranscriptionSegment {
  id: string
  segment_index: number
  start_time_ms: number
  end_time_ms: number
  text: string
  confidence_score: number | null
  speaker_label: string | null
}

export interface Transcription {
  id: string
  video_id: string
  raw_transcript: string | null
  cleaned_transcript: string | null
  confidence_score: number | null
  processing_time_seconds: number | null
  model_version: string | null
  language_detected: string | null
  status: string
  error_message: string | null
  progress: number
  created_at: string
  updated_at: string
  segments: TranscriptionSegment[]
}

export interface TranscriptionJob {
  transcription_id: string
  video_id: string
  status: string
  estimated_processing_time_seconds: number | null
  job_id: string | null
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface AuthResponse {
  user: User
  tokens: TokenResponse
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  per_page: number
  pages: number
}

export interface HealthResponse {
  status: string
  timestamp: string
  components: Record<string, string | boolean>
  version: string
}

export interface ApiError {
  error: string
  message: string
  details?: string
  request_id?: string
}

export interface UploadProgress {
  fileName: string
  progress: number
  status: 'pending' | 'uploading' | 'completed' | 'error'
  videoId?: string
}

export interface SynthesisResult {
  transcription_id: string
  status: string
  audio_files: Record<string, string>
  subtitle_files: Record<string, string>
  metadata: Record<string, unknown>
}
