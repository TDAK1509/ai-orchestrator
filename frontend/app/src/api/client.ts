const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"
// allow-comment: VITE_API_TOKEN ships inside this public JS bundle, so it gates direct API/WS access from a random client, not this frontend page itself -- keep the page's own hosting private if that page needs to be the boundary.
const API_TOKEN = import.meta.env.VITE_API_TOKEN as string | undefined

function authHeaders(): HeadersInit {
  return API_TOKEN ? { Authorization: `Bearer ${API_TOKEN}` } : {}
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const hasBody = body !== undefined
  const response = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: { ...(hasBody ? { "Content-Type": "application/json" } : {}), ...authHeaders() },
    body: hasBody ? JSON.stringify(body) : undefined,
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

// allow-comment: any value interpolated into a URL path that didn't originate as a UUID from our own backend (e.g. an MCP server name from .mcp.json) must go through this, or a value like "../.." can retarget the request to a different endpoint entirely.
export function pathSegment(value: string): string {
  return encodeURIComponent(value)
}

export function wsUrl(): string {
  const url = new URL(BASE_URL)
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:"
  url.pathname = "/ws"
  if (API_TOKEN) url.searchParams.set("token", API_TOKEN)
  return url.toString()
}
