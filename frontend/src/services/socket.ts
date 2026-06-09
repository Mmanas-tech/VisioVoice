import { io, Socket } from 'socket.io-client'
import { WS_URL } from '@/config/constants'

let socket: Socket | null = null

export function getSocket(token?: string): Socket {
  if (socket && socket.connected) return socket

  const opts: Record<string, unknown> = {
    reconnection: true,
    reconnectionAttempts: 10,
    reconnectionDelay: 1000,
    transports: ['websocket', 'polling'],
  }
  if (token) {
    opts.auth = { token }
  }

  socket = io(WS_URL, opts)

  socket.on('connect', () => {
    console.log('[WebSocket] Connected')
  })

  socket.on('disconnect', (reason) => {
    console.log('[WebSocket] Disconnected:', reason)
  })

  socket.on('connect_error', (error) => {
    console.error('[WebSocket] Connection error:', error.message)
  })

  return socket
}

export function joinTranscription(transcriptionId: string): void {
  if (socket) {
    socket.emit('join_transcription', { transcription_id: transcriptionId })
  }
}

export function leaveTranscription(transcriptionId: string): void {
  if (socket) {
    socket.emit('leave_transcription', { transcription_id: transcriptionId })
  }
}

export function onTranscriptionProgress(
  callback: (data: { transcription_id: string; progress: number; message: string }) => void
): () => void {
  if (socket) {
    socket.on('transcription_progress', callback)
    return () => { socket?.off('transcription_progress', callback) }
  }
  return () => {}
}

export function onAudioProgress(
  callback: (data: { transcription_id: string; progress: number; message: string }) => void
): () => void {
  if (socket) {
    socket.on('audio_progress', callback)
    return () => { socket?.off('audio_progress', callback) }
  }
  return () => {}
}

export function onTranscriptionComplete(
  callback: (data: { transcription_id: string; status: string }) => void
): () => void {
  if (socket) {
    socket.on('transcription_complete', callback)
    return () => { socket?.off('transcription_complete', callback) }
  }
  return () => {}
}

export function onAudioComplete(
  callback: (data: { transcription_id: string; status: string }) => void
): () => void {
  if (socket) {
    socket.on('audio_complete', callback)
    return () => { socket?.off('audio_complete', callback) }
  }
  return () => {}
}

export function onError(
  callback: (data: { transcription_id: string; error: string }) => void
): () => void {
  if (socket) {
    socket.on('error', callback)
    return () => { socket?.off('error', callback) }
  }
  return () => {}
}

export function disconnectSocket(): void {
  if (socket) {
    socket.disconnect()
    socket = null
  }
}

export function getSocketInstance(): Socket | null {
  return socket
}
