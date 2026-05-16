"use client"

import { createContext, useState, useEffect, useCallback } from "react"
import { api, setTokens, clearTokens, getTokens } from "@/lib/api"

export const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchUser = useCallback(async () => {
    try {
      const data = await api.get("/auth/me")
      setUser(data)
    } catch {
      const { refresh } = getTokens()
      if (refresh) {
        try {
          const data = await api.post("/auth/refresh", {
            refresh_token: refresh,
          })
          setTokens(data.access_token, data.refresh_token)
          const userData = await api.get("/auth/me")
          setUser(userData)
        } catch {
          clearTokens()
          setUser(null)
        }
      } else {
        setUser(null)
      }
    }
  }, [])

  useEffect(() => {
    const { access } = getTokens()
    if (access) {
      fetchUser().finally(() => setIsLoading(false))
    } else {
      setIsLoading(false)
    }
  }, [fetchUser])

  const login = useCallback(async (email, password) => {
    setError(null)
    const data = await api.post("/auth/login", { email, password })
    setTokens(data.access_token, data.refresh_token)
    const userData = await api.get("/auth/me")
    setUser(userData)
    return userData
  }, [])

  const register = useCallback(async (email, password) => {
    setError(null)
    const data = await api.post("/auth/register", { email, password })
    setTokens(data.access_token, data.refresh_token)
    const userData = await api.get("/auth/me")
    setUser(userData)
    return userData
  }, [])

  const logout = useCallback(() => {
    clearTokens()
    setUser(null)
    setError(null)
  }, [])

  return (
    <AuthContext.Provider
      value={{ user, isLoading, isAuthenticated: !!user, error, login, register, logout }}
    >
      {children}
    </AuthContext.Provider>
  )
}
