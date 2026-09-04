import { wsUrl } from "../api/client"
import type { EventEnvelope } from "../api/types"

const BASE_RECONNECT_DELAY_MS = 1000
const MAX_RECONNECT_DELAY_MS = 30000

type Listener = (envelope: EventEnvelope) => void
type OpenListener = () => void

let socket: WebSocket | null = null
let reconnectDelayMs = BASE_RECONNECT_DELAY_MS
const listeners = new Set<Listener>()
const openListeners = new Set<OpenListener>()

export function onEvent(listener: Listener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function onOpen(listener: OpenListener): () => void {
  openListeners.add(listener)
  return () => openListeners.delete(listener)
}

export function connectRealtime(): void {
  if (socket) return
  openSocket()
}

function openSocket(): void {
  socket = new WebSocket(wsUrl())
  socket.addEventListener("open", handleOpen)
  socket.addEventListener("message", handleMessage)
  socket.addEventListener("close", handleClose)
}

function handleOpen(): void {
  reconnectDelayMs = BASE_RECONNECT_DELAY_MS
  for (const listener of openListeners) listener()
}

function handleMessage(event: MessageEvent<string>): void {
  const envelope = JSON.parse(event.data) as EventEnvelope
  if (envelope.type === "ping") return
  for (const listener of listeners) listener(envelope)
}

function handleClose(): void {
  socket = null
  const delay = reconnectDelayMs + Math.random() * reconnectDelayMs
  reconnectDelayMs = Math.min(reconnectDelayMs * 2, MAX_RECONNECT_DELAY_MS)
  setTimeout(openSocket, delay)
}
