const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"

function getTokens() {
  if (typeof window === "undefined") return { access: null, refresh: null }
  try {
    const access = localStorage.getItem("access_token")
    const refresh = localStorage.getItem("refresh_token")
    return { access, refresh }
  } catch {
    return { access: null, refresh: null }
  }
}

function setTokens(access, refresh) {
  localStorage.setItem("access_token", access)
  if (refresh) localStorage.setItem("refresh_token", refresh)
  document.cookie = "auth-token=true; path=/; max-age=86400; SameSite=Lax"
}

function clearTokens() {
  localStorage.removeItem("access_token")
  localStorage.removeItem("refresh_token")
  document.cookie = "auth-token=; path=/; max-age=0; SameSite=Lax"
}

class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
    this.name = "ApiError"
  }
}

async function request(endpoint, options = {}) {
  const { access } = getTokens()
  const headers = { "Content-Type": "application/json", ...options.headers }

  if (access) {
    headers["Authorization"] = `Bearer ${access}`
  }

  const url = `${API_BASE}${endpoint}`
  const res = await fetch(url, { ...options, headers })

  if (res.status === 401 && access) {
    const { refresh } = getTokens()
    if (refresh) {
      try {
        const refreshRes = await fetch(`${API_BASE}/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refresh }),
        })

        if (refreshRes.ok) {
          const data = await refreshRes.json()
          setTokens(data.access_token, data.refresh_token)
          headers["Authorization"] = `Bearer ${data.access_token}`
          const retryRes = await fetch(url, { ...options, headers })
          if (!retryRes.ok) {
            const err = await parseError(retryRes)
            throw new ApiError(retryRes.status, err)
          }
          return retryRes.json()
        }
      } catch {}
    }

    clearTokens()
    if (typeof window !== "undefined") {
      window.location.href = "/login"
    }
    throw new ApiError(401, "Sesión expirada")
  }

  if (!res.ok) {
    const err = await parseError(res)
    throw new ApiError(res.status, err)
  }

  if (res.status === 204) return null
  return res.json()
}

async function parseError(res) {
  try {
    const body = await res.json()
    return body.detail || body.message || "Error desconocido"
  } catch {
    return `Error ${res.status}`
  }
}

export const api = {
  get: (endpoint, options) => request(endpoint, { ...options, method: "GET" }),
  post: (endpoint, body, options) =>
    request(endpoint, { ...options, method: "POST", body: JSON.stringify(body) }),
  put: (endpoint, body, options) =>
    request(endpoint, { ...options, method: "PUT", body: JSON.stringify(body) }),
  delete: (endpoint, options) => request(endpoint, { ...options, method: "DELETE" }),
}

export { setTokens, clearTokens, getTokens, ApiError }
