const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"
const API_TOKEN = import.meta.env.VITE_API_TOKEN as string | undefined

function authHeaders(): HeadersInit {
  return API_TOKEN ? { Authorization: `Bearer ${API_TOKEN}` } : {}
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`${method} ${path} failed: ${response.status} ${detail}`)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
  delete: <T>(path: string) => request<T>("DELETE", path),
}

export function wsUrl(): string {
  const url = new URL(BASE_URL)
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:"
  url.pathname = "/ws"
  if (API_TOKEN) url.searchParams.set("token", API_TOKEN)
  return url.toString()
}
