export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'
export const WS_URL = import.meta.env.VITE_WS_URL || 'http://localhost:8000'
export const APP_NAME = import.meta.env.VITE_APP_NAME || 'LipRead AI'

export const VIDEO_MAX_SIZE_MB = 2048
export const ALLOWED_VIDEO_TYPES = ['.mp4', '.mov', '.avi', '.mkv']
export const ALLOWED_VIDEO_MIME_TYPES = [
  'video/mp4',
  'video/quicktime',
  'video/x-msvideo',
  'video/x-matroska',
]

export const TRANSCRIPTION_STATUS = {
  PENDING: 'pending',
  PROCESSING: 'processing',
  COMPLETED: 'completed',
  FAILED: 'failed',
} as const

export const EXPORT_FORMATS = [
  { value: 'json', label: 'JSON', description: 'Structured data' },
  { value: 'srt', label: 'SRT', description: 'Subtitle format' },
  { value: 'vtt', label: 'VTT', description: 'WebVTT subtitles' },
  { value: 'docx', label: 'DOCX', description: 'Word document' },
  { value: 'pdf', label: 'PDF', description: 'PDF document' },
] as const

export const TTS_BACKENDS = [
  { value: 'pyttsx3', label: 'Local TTS', description: 'Basic offline TTS' },
  { value: 'google', label: 'Google Cloud', description: 'High quality cloud TTS' },
  { value: 'bark', label: 'Bark', description: 'Expressive AI voice' },
  { value: 'elevenlabs', label: 'ElevenLabs', description: 'Premium voice synthesis' },
] as const
