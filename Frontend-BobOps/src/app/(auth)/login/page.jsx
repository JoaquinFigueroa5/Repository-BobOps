"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { useAuth } from "@/hooks/useAuth"
import PageTransition from "@/components/PageTransition"
import { viewTransitionPush } from "@/lib/navigation"

function validate(email, password) {
  const errors = {}
  if (!email.trim()) errors.email = "El correo es obligatorio"
  else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) errors.email = "Correo inválido"
  if (!password) errors.password = "La contraseña es obligatoria"
  else if (password.length < 6) errors.password = "Mínimo 6 caracteres"
  return errors
}

export default function LoginPage() {
  const router = useRouter()
  const { login } = useAuth()
  const [form, setForm] = useState({ email: "", password: "" })
  const [errors, setErrors] = useState({})
  const [serverError, setServerError] = useState(null)
  const [loading, setLoading] = useState(false)

  const handleChange = (e) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }))
    setErrors((prev) => ({ ...prev, [e.target.name]: null }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setServerError(null)
    const validation = validate(form.email, form.password)
    if (Object.keys(validation).length > 0) {
      setErrors(validation)
      return
    }
    setLoading(true)
    try {
      await login(form.email, form.password)
      viewTransitionPush(router, "/")
    } catch (err) {
      setServerError(err.message || "Error al iniciar sesión")
    } finally {
      setLoading(false)
    }
  }

  return (
    <PageTransition>
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <Link
          href="/"
          transitionTypes={["nav-back"]}
          className="inline-flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-300 transition-colors mb-6"
        >
          ← Regresar al inicio
        </Link>
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-white tracking-tight">BobOps</h1>
          <p className="text-zinc-500 text-sm mt-1">Inicia sesión para continuar</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="email" className="block text-xs font-medium text-zinc-400 mb-1">
              Correo electrónico
            </label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              value={form.email}
              onChange={handleChange}
              className={`w-full px-3 py-2.5 bg-zinc-900 border rounded-lg text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 transition-colors ${
                errors.email
                  ? "border-red-500 focus:ring-red-500"
                  : "border-zinc-800 focus:ring-zinc-500 focus:border-zinc-500"
              }`}
              placeholder="correo@ejemplo.com"
            />
            {errors.email && <p className="text-red-400 text-xs mt-1">{errors.email}</p>}
          </div>

          <div>
            <label htmlFor="password" className="block text-xs font-medium text-zinc-400 mb-1">
              Contraseña
            </label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              value={form.password}
              onChange={handleChange}
              className={`w-full px-3 py-2.5 bg-zinc-900 border rounded-lg text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 transition-colors ${
                errors.password
                  ? "border-red-500 focus:ring-red-500"
                  : "border-zinc-800 focus:ring-zinc-500 focus:border-zinc-500"
              }`}
              placeholder="••••••••"
            />
            {errors.password && <p className="text-red-400 text-xs mt-1">{errors.password}</p>}
          </div>

          {serverError && (
            <div className="bg-red-900/30 border border-red-800 rounded-lg px-3 py-2">
              <p className="text-red-400 text-xs">{serverError}</p>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-white text-black text-sm font-medium rounded-lg hover:bg-zinc-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? "Iniciando sesión..." : "Iniciar sesión"}
          </button>
        </form>

        <p className="text-center text-xs text-zinc-600 mt-6">
          ¿No tienes cuenta?{" "}
          <Link href="/register" transitionTypes={["nav-forward"]} className="text-zinc-300 hover:text-white transition-colors">
            Regístrate
          </Link>
        </p>
      </div>
    </div>
    </PageTransition>
  )
}
