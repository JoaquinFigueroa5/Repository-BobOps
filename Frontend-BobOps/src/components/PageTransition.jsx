"use client"

import { ViewTransition } from "react"

const config = {
  enter: { "nav-forward": "nav-forward", "nav-back": "nav-back", default: "nav-forward" },
  exit: { "nav-forward": "nav-forward", "nav-back": "nav-back", default: "nav-forward" },
  default: "nav-forward",
}

export default function PageTransition({ children }) {
  return <ViewTransition {...config}>{children}</ViewTransition>
}
