import { io, Socket } from 'socket.io-client'
import { WS_URL } from '@/config/constants'

let socket: Socket | null = null

export function getSocket(token: string): Socket {
  if (socket && socket.connected) return socket

  socket = io(WS_URL, {
    auth: { token },
    reconnection: true,
    reconnectionAttempts: 10,
    reconnectionDelay: 1000,
    transports: ['websocket', 'polling'],
  })

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

export function disconnectSocket(): void {
  if (socket) {
    socket.disconnect()
    socket = null
  }
}

export function getSocketInstance(): Socket | null {
  return socket
}
