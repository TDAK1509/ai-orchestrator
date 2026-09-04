import { wsUrl } from "../api/client"
import type { EventEnvelope } from "../api/types"

const RECONNECT_DELAY_MS = 2000

type Listener = (envelope: EventEnvelope) => void

let socket: WebSocket | null = null
const listeners = new Set<Listener>()

export function onEvent(listener: Listener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function connectRealtime(): void {
  if (socket) return
  openSocket()
}

function openSocket(): void {
  socket = new WebSocket(wsUrl())
  socket.addEventListener("message", handleMessage)
  socket.addEventListener("close", handleClose)
}

function handleMessage(event: MessageEvent<string>): void {
  const envelope = JSON.parse(event.data) as EventEnvelope
  if (envelope.type === "ping") return
  for (const listener of listeners) listener(envelope)
}

function handleClose(): void {
  socket = null
  setTimeout(openSocket, RECONNECT_DELAY_MS)
}
