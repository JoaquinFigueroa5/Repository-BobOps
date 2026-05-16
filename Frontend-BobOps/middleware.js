import { NextResponse } from "next/server"

const publicRoutes = ["/login", "/register"]
const authCookie = "auth-token"

export function middleware(request) {
  const { pathname } = request.nextUrl

  if (publicRoutes.includes(pathname)) {
    const hasToken = request.cookies.get(authCookie)
    if (hasToken) {
      return NextResponse.redirect(new URL("/", request.url))
    }
    return NextResponse.next()
  }

  const hasToken = request.cookies.get(authCookie)
  if (!hasToken) {
    const loginUrl = new URL("/login", request.url)
    loginUrl.searchParams.set("redirect", pathname)
    return NextResponse.redirect(loginUrl)
  }

  return NextResponse.next()
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
}
