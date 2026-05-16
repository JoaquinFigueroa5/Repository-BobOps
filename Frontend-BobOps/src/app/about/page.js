"use client";

import { ViewTransition } from "react";
import Link from "next/link";

export default function About() {
  return (
    <ViewTransition
      enter={{ "nav-forward": "nav-forward", "nav-back": "nav-back", default: "none" }}
      exit={{ "nav-forward": "nav-forward", "nav-back": "nav-back", default: "none" }}
      default="none"
    >
      <div className="min-h-screen bg-zinc-950 text-white flex flex-col items-center justify-center px-6">
        <div className="max-w-md w-full text-center">
          {/* Badge */}
          <span className="inline-block text-xs font-medium tracking-widest uppercase text-zinc-500 border border-zinc-800 px-3 py-1 rounded-full mb-6">
            app/about/page.js → /about
          </span>

          {/* Heading */}
          <h1 className="text-3xl sm:text-4xl font-black tracking-tighter leading-tight mb-4">
            Ejemplo de enrutamiento{" "}
            <span className="text-zinc-600">en Next.js</span>
          </h1>

          <p className="text-zinc-500 text-sm leading-relaxed mb-8">
            Esta página existe porque el archivo{" "}
            <code className="text-emerald-400 bg-zinc-800 px-1.5 py-0.5 rounded text-xs">
              page.js
            </code>{" "}
            está dentro de la carpeta{" "}
            <code className="text-emerald-400 bg-zinc-800 px-1.5 py-0.5 rounded text-xs">
              app/about/
            </code>
            . El App Router de Next.js convierte automáticamente esa ruta en{" "}
            <code className="text-emerald-400 bg-zinc-800 px-1.5 py-0.5 rounded text-xs">
              /about
            </code>
            .
          </p>

          {/* Back button — nav-back para animar en dirección correcta */}
          <Link
            href="/"
            transitionTypes={["nav-back"]}
            className="inline-flex items-center gap-2 text-sm px-5 py-2.5 rounded-full border border-zinc-700 text-zinc-300 hover:border-zinc-400 hover:text-white transition-all duration-150"
          >
            ← Regresar a la página anterior
          </Link>
        </div>
      </div>
    </ViewTransition>
  );
}

