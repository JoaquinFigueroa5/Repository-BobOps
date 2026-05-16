"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/hooks/useAuth";
import PageTransition from "@/components/PageTransition";

const sections = [
  { id: "routing", label: "Enrutamiento", icon: "🗺️" },
  { id: "layouts", label: "Layouts", icon: "🧩" },
  { id: "data", label: "Fetching de datos", icon: "🗄️" },
  { id: "server", label: "Server & Client", icon: "⚙️" },
  { id: "api", label: "API Routes", icon: "🔌" },
  { id: "metadata", label: "Metadata & SEO", icon: "🌐" },
];

function CodeBlock({ filename, code }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-xl overflow-hidden border border-zinc-800 mb-4">
      <div className="flex items-center justify-between px-4 py-2 bg-zinc-900 border-b border-zinc-800">
        <span className="text-xs font-mono text-zinc-400">{filename}</span>
        <button
          onClick={handleCopy}
          className="text-xs text-zinc-500 hover:text-zinc-200 transition-colors px-2 py-1 rounded hover:bg-zinc-800"
        >
          {copied ? "✓ Copiado" : "Copiar"}
        </button>
      </div>
      <pre className="bg-zinc-950 px-4 py-4 overflow-x-auto text-sm font-mono text-zinc-300 leading-relaxed">
        <code dangerouslySetInnerHTML={{ __html: code }} />
      </pre>
    </div>
  );
}

function FileTree({ items }) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950 px-4 py-4 mb-4 font-mono text-sm">
      {items.map((item, i) => (
        <div
          key={i}
          className={`flex items-center gap-2 py-0.5 ${
            item.indent === 1
              ? "pl-5"
              : item.indent === 2
                ? "pl-10"
                : item.indent === 3
                  ? "pl-14"
                  : ""
          } ${
            item.type === "folder"
              ? "text-sky-400"
              : item.highlight === "green"
                ? "text-emerald-400"
                : item.highlight === "purple"
                  ? "text-purple-400"
                  : "text-zinc-400"
          }`}
        >
          <span>{item.type === "folder" ? "📁" : "📄"}</span>
          <span>{item.name}</span>
          {item.route && (
            <span className="text-zinc-600 text-xs ml-1">→ {item.route}</span>
          )}
        </div>
      ))}
    </div>
  );
}

function InfoCard({ label, value, sub }) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-4">
      <p className="text-xs uppercase tracking-widest text-zinc-500 mb-1">
        {label}
      </p>
      <p className="font-semibold text-white text-sm mb-1 font-mono">{value}</p>
      {sub && <p className="text-xs text-zinc-500 leading-relaxed">{sub}</p>}
    </div>
  );
}

function Tip({ label, children }) {
  return (
    <div className="border-l-2 border-white pl-4 py-1 my-4 bg-zinc-900/50 rounded-r-lg pr-4">
      <p className="text-xs uppercase tracking-widest text-zinc-500 mb-1">
        {label}
      </p>
      <p className="text-sm text-zinc-400 leading-relaxed">{children}</p>
    </div>
  );
}

function SectionRouting() {
  return (
    <div>
      <p className="text-zinc-400 text-sm leading-relaxed mb-6">
        Next.js usa el sistema de archivos como router. Cada archivo{" "}
        <code className="text-emerald-400 bg-zinc-800 px-1.5 py-0.5 rounded text-xs">
          page.jsx
        </code>{" "}
        dentro de{" "}
        <code className="text-emerald-400 bg-zinc-800 px-1.5 py-0.5 rounded text-xs">
          app/
        </code>{" "}
        se convierte automáticamente en una ruta accesible desde el navegador.
      </p>
      <p className="text-zinc-400 text-sm leading-relaxed mb-6">
        Ingresa a {" "}
        <Link
          className="text-emerald-400 bg-zinc-800 px-1.5 py-0.5 rounded text-xs"
          href="/about"
          transitionTypes={["nav-forward"]}
        >
          /about
        </Link>
        {" "} para ver un ejemplo de enrutamiento.
      </p>

      <FileTree
        items={[
          { name: "app/", type: "folder", indent: 0 },
          {
            name: "page.jsx",
            type: "file",
            indent: 1,
            route: "/",
            highlight: "green",
          },
          { name: "about/", type: "folder", indent: 1 },
          {
            name: "page.jsx",
            type: "file",
            indent: 2,
            route: "/about",
            highlight: "green",
          },
          { name: "blog/", type: "folder", indent: 1 },
          {
            name: "page.jsx",
            type: "file",
            indent: 2,
            route: "/blog",
            highlight: "green",
          },
          { name: "[slug]/", type: "folder", indent: 2 },
          {
            name: "page.jsx",
            type: "file",
            indent: 3,
            route: "/blog/:slug",
            highlight: "purple",
          },
        ]}
      />

      <h3 className="text-white font-semibold text-sm mb-3 mt-6">
        Rutas dinámicas
      </h3>
      <p className="text-zinc-400 text-sm leading-relaxed mb-4">
        Los corchetes{" "}
        <code className="text-purple-400 bg-zinc-800 px-1.5 py-0.5 rounded text-xs">
          [param]
        </code>{" "}
        crean segmentos dinámicos. El parámetro llega como prop al componente.
      </p>

      <CodeBlock
        filename="app/blog/[slug]/page.jsx"
        code={`<span style="color:#c084fc">export default function</span> <span style="color:#67e8f9">BlogPost</span>({ params }) {
  <span style="color:#c084fc">return</span> &lt;h1&gt;Post: {params.slug}&lt;/h1&gt;
}`}
      />

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-6">
        <InfoCard
          label="Ruta estática"
          value="app/about/page.jsx"
          sub="URL fija: /about"
        />
        <InfoCard
          label="Ruta dinámica"
          value="app/blog/[slug]/"
          sub="Captura cualquier segmento"
        />
        <InfoCard
          label="Catch-all"
          value="app/[...paths]/"
          sub="Captura múltiples segmentos"
        />
      </div>

      <Tip label="💡 Nota">
        El archivo se llama <strong>page.jsx</strong> (no index.jsx). Solo los
        archivos con este nombre son accesibles públicamente como rutas.
      </Tip>

      <h3 className="text-white font-semibold text-sm mb-3 mt-6">
        Grupos de rutas
      </h3>
      <p className="text-zinc-400 text-sm leading-relaxed mb-4">
        Usa paréntesis{" "}
        <code className="text-purple-400 bg-zinc-800 px-1.5 py-0.5 rounded text-xs">
          (grupo)
        </code>{" "}
        para organizar rutas sin afectar la URL.
      </p>
      <FileTree
        items={[
          { name: "app/", type: "folder", indent: 0 },
          {
            name: "(marketing)/",
            type: "folder",
            indent: 1,
            highlight: "purple",
          },
          {
            name: "page.jsx",
            type: "file",
            indent: 2,
            route: "/",
            highlight: "green",
          },
          {
            name: "about/page.jsx",
            type: "file",
            indent: 2,
            route: "/about",
            highlight: "green",
          },
          {
            name: "(dashboard)/",
            type: "folder",
            indent: 1,
            highlight: "purple",
          },
          {
            name: "settings/page.jsx",
            type: "file",
            indent: 2,
            route: "/settings",
            highlight: "green",
          },
        ]}
      />
    </div>
  );
}

function SectionLayouts() {
  return (
    <div>
      <p className="text-zinc-400 text-sm leading-relaxed mb-6">
        El archivo{" "}
        <code className="text-emerald-400 bg-zinc-800 px-1.5 py-0.5 rounded text-xs">
          layout.jsx
        </code>{" "}
        envuelve a sus páginas hijas y persiste entre navegaciones. Ideal para
        navbars, sidebars y estructura compartida.
      </p>

      <CodeBlock
        filename="app/layout.jsx — Layout raíz (obligatorio)"
        code={`<span style="color:#c084fc">export default function</span> <span style="color:#67e8f9">RootLayout</span>({ children }) {
  <span style="color:#c084fc">return</span> (
    &lt;html lang=<span style="color:#86efac">"es"</span>&gt;
      &lt;body&gt;
        &lt;Navbar /&gt;
        &lt;main&gt;{children}&lt;/main&gt;
        &lt;Footer /&gt;
      &lt;/body&gt;
    &lt;/html&gt;
  )
}`}
      />

      <h3 className="text-white font-semibold text-sm mb-3 mt-6">
        Layouts anidados
      </h3>
      <FileTree
        items={[
          {
            name: "app/layout.jsx",
            type: "file",
            indent: 0,
            route: "RootLayout",
            highlight: "green",
          },
          { name: "dashboard/", type: "folder", indent: 1 },
          {
            name: "layout.jsx",
            type: "file",
            indent: 2,
            route: "DashboardLayout (dentro de Root)",
            highlight: "green",
          },
          { name: "page.jsx", type: "file", indent: 2 },
          { name: "settings/", type: "folder", indent: 2 },
          { name: "page.jsx", type: "file", indent: 3 },
        ]}
      />

      <Tip label="Archivos especiales">
        <code className="text-emerald-400">loading.jsx</code> muestra UI de
        carga automáticamente con Suspense.{" "}
        <code className="text-emerald-400">error.jsx</code> captura errores en
        su segmento. <code className="text-emerald-400">not-found.jsx</code> se
        muestra cuando retornas{" "}
        <code className="text-emerald-400">notFound()</code>.
      </Tip>

      <CodeBlock
        filename="app/dashboard/loading.jsx"
        code={`<span style="color:#c084fc">export default function</span> <span style="color:#67e8f9">Loading</span>() {
  <span style="color:#c084fc">return</span> &lt;p&gt;Cargando dashboard...&lt;/p&gt;
}`}
      />
    </div>
  );
}

function SectionData() {
  return (
    <div>
      <p className="text-zinc-400 text-sm leading-relaxed mb-6">
        En el App Router, los Server Components pueden hacer fetch directamente
        con{" "}
        <code className="text-emerald-400 bg-zinc-800 px-1.5 py-0.5 rounded text-xs">
          async/await
        </code>
        . Next.js extiende la API{" "}
        <code className="text-emerald-400 bg-zinc-800 px-1.5 py-0.5 rounded text-xs">
          fetch
        </code>{" "}
        nativa con caché automático.
      </p>

      <CodeBlock
        filename="app/products/page.jsx"
        code={`<span style="color:#c084fc">async function</span> <span style="color:#67e8f9">getProducts</span>() {
  <span style="color:#c084fc">const</span> res = <span style="color:#c084fc">await</span> fetch(<span style="color:#86efac">'https://api.ejemplo.com/products'</span>, {
    next: { revalidate: <span style="color:#fb923c">3600</span> } <span style="color:#555">// revalida cada hora</span>
  })
  <span style="color:#c084fc">return</span> res.json()
}

<span style="color:#c084fc">export default async function</span> <span style="color:#67e8f9">Page</span>() {
  <span style="color:#c084fc">const</span> products = <span style="color:#c084fc">await</span> <span style="color:#67e8f9">getProducts</span>()
  <span style="color:#c084fc">return</span> &lt;ProductList products={products} /&gt;
}`}
      />

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-6">
        <InfoCard
          label="Sin caché"
          value="cache: 'no-store'"
          sub="Siempre datos frescos (SSR)"
        />
        <InfoCard
          label="Caché estático"
          value="cache: 'force-cache'"
          sub="Por defecto, data estática (SSG)"
        />
        <InfoCard
          label="Revalidar"
          value="revalidate: N"
          sub="Revalida cada N segundos (ISR)"
        />
      </div>

      <h3 className="text-white font-semibold text-sm mb-3 mt-6">
        generateStaticParams
      </h3>
      <p className="text-zinc-400 text-sm leading-relaxed mb-4">
        Para rutas dinámicas estáticas, define los parámetros en build time.
      </p>

      <CodeBlock
        filename="app/blog/[slug]/page.jsx"
        code={`<span style="color:#c084fc">export async function</span> <span style="color:#67e8f9">generateStaticParams</span>() {
  <span style="color:#c084fc">const</span> posts = <span style="color:#c084fc">await</span> <span style="color:#67e8f9">getPosts</span>()
  <span style="color:#c084fc">return</span> posts.map((post) => ({
    slug: post.slug,
  }))
}`}
      />
    </div>
  );
}

function SectionServer() {
  return (
    <div>
      <p className="text-zinc-400 text-sm leading-relaxed mb-6">
        Por defecto, todos los componentes en el App Router son{" "}
        <strong className="text-white">Server Components</strong>. Para usar
        hooks o interactividad, declara{" "}
        <code className="text-emerald-400 bg-zinc-800 px-1.5 py-0.5 rounded text-xs">
          'use client'
        </code>{" "}
        al inicio del archivo.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6">
        <div className="rounded-xl border border-zinc-700 bg-zinc-900 p-4 border-l-2 border-l-white">
          <p className="text-xs uppercase tracking-widest text-zinc-500 mb-1">
            Server Component
          </p>
          <p className="font-semibold text-white text-sm mb-2">Por defecto</p>
          <p className="text-xs text-zinc-500 leading-relaxed">
            Acceso a DB, APIs, sistema de archivos. Sin hooks de React. HTML
            generado en servidor.
          </p>
        </div>
        <div className="rounded-xl border border-zinc-700 bg-zinc-900 p-4 border-l-2 border-l-indigo-500">
          <p className="text-xs uppercase tracking-widest text-zinc-500 mb-1">
            Client Component
          </p>
          <p className="font-semibold text-white text-sm mb-2">'use client'</p>
          <p className="text-xs text-zinc-500 leading-relaxed">
            useState, useEffect, eventos DOM, browser APIs. Se hidrata en el
            cliente.
          </p>
        </div>
      </div>

      <CodeBlock
        filename="components/Counter.jsx — Client Component"
        code={`<span style="color:#86efac">'use client'</span>

<span style="color:#c084fc">import</span> { useState } <span style="color:#c084fc">from</span> <span style="color:#86efac">'react'</span>

<span style="color:#c084fc">export default function</span> <span style="color:#67e8f9">Counter</span>() {
  <span style="color:#c084fc">const</span> [count, setCount] = <span style="color:#67e8f9">useState</span>(<span style="color:#fb923c">0</span>)
  <span style="color:#c084fc">return</span> (
    &lt;button onClick={() => <span style="color:#67e8f9">setCount</span>(count + <span style="color:#fb923c">1</span>)}&gt;
      Clicks: {count}
    &lt;/button&gt;
  )
}`}
      />

      <Tip label="Patrón recomendado">
        Mantén la lógica de datos en Server Components y delega solo la
        interactividad a Client Components. Así maximizas el rendimiento y
        minimizas el JS enviado al cliente.
      </Tip>

      <h3 className="text-white font-semibold text-sm mb-3 mt-6">
        Server Actions
      </h3>
      <p className="text-zinc-400 text-sm leading-relaxed mb-4">
        Funciones del servidor que pueden ser llamadas directamente desde el
        cliente. Sin necesidad de crear un endpoint API.
      </p>

      <CodeBlock
        filename="app/actions.js"
        code={`<span style="color:#86efac">'use server'</span>

<span style="color:#c084fc">export async function</span> <span style="color:#67e8f9">createPost</span>(formData) {
  <span style="color:#c084fc">const</span> title = formData.<span style="color:#67e8f9">get</span>(<span style="color:#86efac">'title'</span>)
  <span style="color:#c084fc">await</span> db.post.<span style="color:#67e8f9">create</span>({ data: { title } })
  <span style="color:#67e8f9">revalidatePath</span>(<span style="color:#86efac">'/blog'</span>)
}`}
      />
    </div>
  );
}

function SectionAPI() {
  return (
    <div>
      <p className="text-zinc-400 text-sm leading-relaxed mb-6">
        El archivo{" "}
        <code className="text-emerald-400 bg-zinc-800 px-1.5 py-0.5 rounded text-xs">
          route.js
        </code>{" "}
        dentro de{" "}
        <code className="text-emerald-400 bg-zinc-800 px-1.5 py-0.5 rounded text-xs">
          app/
        </code>{" "}
        crea un endpoint HTTP. Exporta funciones nombradas por método:{" "}
        <code className="text-purple-400 bg-zinc-800 px-1.5 py-0.5 rounded text-xs">
          GET
        </code>
        ,{" "}
        <code className="text-purple-400 bg-zinc-800 px-1.5 py-0.5 rounded text-xs">
          POST
        </code>
        ,{" "}
        <code className="text-purple-400 bg-zinc-800 px-1.5 py-0.5 rounded text-xs">
          PUT
        </code>
        ,{" "}
        <code className="text-purple-400 bg-zinc-800 px-1.5 py-0.5 rounded text-xs">
          DELETE
        </code>
        .
      </p>

      <CodeBlock
        filename="app/api/users/route.js"
        code={`<span style="color:#c084fc">import</span> { NextResponse } <span style="color:#c084fc">from</span> <span style="color:#86efac">'next/server'</span>

<span style="color:#c084fc">export async function</span> <span style="color:#67e8f9">GET</span>() {
  <span style="color:#c084fc">const</span> users = <span style="color:#c084fc">await</span> db.<span style="color:#67e8f9">getUsers</span>()
  <span style="color:#c084fc">return</span> NextResponse.<span style="color:#67e8f9">json</span>(users)
}

<span style="color:#c084fc">export async function</span> <span style="color:#67e8f9">POST</span>(request) {
  <span style="color:#c084fc">const</span> body = <span style="color:#c084fc">await</span> request.<span style="color:#67e8f9">json</span>()
  <span style="color:#c084fc">const</span> user = <span style="color:#c084fc">await</span> db.<span style="color:#67e8f9">createUser</span>(body)
  <span style="color:#c084fc">return</span> NextResponse.<span style="color:#67e8f9">json</span>(user, { status: <span style="color:#fb923c">201</span> })
}`}
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6">
        <InfoCard
          label="Ruta estática"
          value="app/api/users/route.js"
          sub="Endpoint: GET /api/users"
        />
        <InfoCard
          label="Ruta dinámica"
          value="app/api/users/[id]/route.js"
          sub="Endpoint: GET /api/users/:id"
        />
      </div>

      <Tip label="Middleware">
        Crea un archivo <code className="text-emerald-400">middleware.js</code>{" "}
        en la raíz del proyecto para interceptar requests antes de que lleguen a
        las rutas. Ideal para autenticación y redirecciones.
      </Tip>

      <CodeBlock
        filename="middleware.js"
        code={`<span style="color:#c084fc">import</span> { NextResponse } <span style="color:#c084fc">from</span> <span style="color:#86efac">'next/server'</span>

<span style="color:#c084fc">export function</span> <span style="color:#67e8f9">middleware</span>(request) {
  <span style="color:#c084fc">const</span> isAuthenticated = request.cookies.<span style="color:#67e8f9">get</span>(<span style="color:#86efac">'token'</span>)
  <span style="color:#c084fc">if</span> (!isAuthenticated) {
    <span style="color:#c084fc">return</span> NextResponse.<span style="color:#67e8f9">redirect</span>(<span style="color:#c084fc">new</span> URL(<span style="color:#86efac">'/login'</span>, request.url))
  }
}

<span style="color:#c084fc">export const</span> config = {
  matcher: [<span style="color:#86efac">'/dashboard/:path*'</span>],
}`}
      />
    </div>
  );
}

function SectionMetadata() {
  return (
    <div>
      <p className="text-zinc-400 text-sm leading-relaxed mb-6">
        Next.js incluye una API de Metadata para definir{" "}
        <code className="text-emerald-400 bg-zinc-800 px-1.5 py-0.5 rounded text-xs">
          &lt;head&gt;
        </code>{" "}
        de forma declarativa. Exporta un objeto{" "}
        <code className="text-emerald-400 bg-zinc-800 px-1.5 py-0.5 rounded text-xs">
          metadata
        </code>{" "}
        o una función{" "}
        <code className="text-emerald-400 bg-zinc-800 px-1.5 py-0.5 rounded text-xs">
          generateMetadata
        </code>{" "}
        desde cualquier page o layout.
      </p>

      <CodeBlock
        filename="app/page.jsx — Metadata estática"
        code={`<span style="color:#c084fc">export const</span> metadata = {
  title: <span style="color:#86efac">'Mi App'</span>,
  description: <span style="color:#86efac">'Descripción para SEO'</span>,
  openGraph: {
    title: <span style="color:#86efac">'Mi App'</span>,
    images: [<span style="color:#86efac">'/og-image.png'</span>],
  },
}`}
      />

      <CodeBlock
        filename="app/blog/[slug]/page.jsx — Metadata dinámica"
        code={`<span style="color:#c084fc">export async function</span> <span style="color:#67e8f9">generateMetadata</span>({ params }) {
  <span style="color:#c084fc">const</span> post = <span style="color:#c084fc">await</span> <span style="color:#67e8f9">getPost</span>(params.slug)
  <span style="color:#c084fc">return</span> {
    title: post.title,
    description: post.excerpt,
  }
}`}
      />

      <h3 className="text-white font-semibold text-sm mb-3 mt-6">
        Fuentes con next/font
      </h3>

      <CodeBlock
        filename="app/layout.jsx"
        code={`<span style="color:#c084fc">import</span> { Geist } <span style="color:#c084fc">from</span> <span style="color:#86efac">'next/font/google'</span>

<span style="color:#c084fc">const</span> geist = <span style="color:#67e8f9">Geist</span>({
  subsets: [<span style="color:#86efac">'latin'</span>],
  display: <span style="color:#86efac">'swap'</span>,
})

<span style="color:#c084fc">export default function</span> <span style="color:#67e8f9">Layout</span>({ children }) {
  <span style="color:#c084fc">return</span> (
    &lt;html className={geist.className}&gt;
      &lt;body&gt;{children}&lt;/body&gt;
    &lt;/html&gt;
  )
}`}
      />

      <Tip label="Optimización de imágenes">
        Usa el componente{" "}
        <code className="text-emerald-400">&lt;Image&gt;</code> de{" "}
        <code className="text-emerald-400">next/image</code> para obtener lazy
        loading, redimensionado automático y formatos modernos (WebP/AVIF) sin
        configuración adicional.
      </Tip>

      <CodeBlock
        filename="Uso de next/image"
        code={`<span style="color:#c084fc">import</span> Image <span style="color:#c084fc">from</span> <span style="color:#86efac">'next/image'</span>

<span style="color:#c084fc">export default function</span> <span style="color:#67e8f9">Avatar</span>() {
  <span style="color:#c084fc">return</span> (
    &lt;Image
      src=<span style="color:#86efac">"/avatar.png"</span>
      alt=<span style="color:#86efac">"Avatar del usuario"</span>
      width={<span style="color:#fb923c">64</span>}
      height={<span style="color:#fb923c">64</span>}
      priority
    /&gt;
  )
}`}
      />
    </div>
  );
}

function Navbar() {
  const { user, isLoading, isAuthenticated, logout } = useAuth();

  return (
    <nav className="flex items-center justify-between px-6 sm:px-10 py-3 border-b border-zinc-900 bg-zinc-950">
      <Link href="/" transitionTypes={["nav-back"]} className="text-sm font-bold text-white tracking-tight">
        BobOps
      </Link>
      <div className="flex items-center gap-3">
        {isLoading ? (
          <span className="text-xs text-zinc-600">Cargando...</span>
        ) : isAuthenticated ? (
          <>
            <span className="text-xs text-zinc-400">{user?.email}</span>
            <button
              onClick={logout}
              className="text-xs px-3 py-1.5 rounded-full border border-zinc-800 text-zinc-400 hover:border-zinc-600 hover:text-zinc-200 transition-all"
            >
              Cerrar sesión
            </button>
          </>
        ) : (
          <Link
            href="/login"
            transitionTypes={["nav-forward"]}
            className="text-xs px-3 py-1.5 rounded-full bg-white text-black font-medium hover:bg-zinc-200 transition-all"
          >
            Iniciar sesión
          </Link>
        )}
      </div>
    </nav>
  );
}

const sectionComponents = {
  routing: SectionRouting,
  layouts: SectionLayouts,
  data: SectionData,
  server: SectionServer,
  api: SectionAPI,
  metadata: SectionMetadata,
};

export default function NextJsGuidePage() {
  const [active, setActive] = useState("routing");
  const ActiveSection = sectionComponents[active];
  const { isAuthenticated } = useAuth();

  return (
    <PageTransition>
    <div className="min-h-screen bg-zinc-950 text-white">
      <Navbar />
      {/* Hero */}
      <div className="bg-black border-b border-zinc-900 px-6 py-12 sm:px-10 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-zinc-900 rounded-full opacity-30 translate-x-1/2 -translate-y-1/2 pointer-events-none" />
        <div className="relative max-w-3xl">
          <span className="inline-block text-xs font-medium tracking-widest uppercase text-zinc-500 border border-zinc-800 px-3 py-1 rounded-full mb-5">
            Guía de referencia
          </span>
          <h1 className="text-4xl sm:text-5xl font-black tracking-tighter leading-none mb-4">
            Next.js <span className="text-zinc-600">desde cero</span>
          </h1>
          <p className="text-zinc-400 text-base leading-relaxed max-w-xl">
            Todo lo que necesitas para entender el enrutamiento, renderizado y
            las funciones clave del framework más popular de React.
          </p>
        </div>
      </div>

      {/* Nav */}
      <div className="border-b border-zinc-900 bg-zinc-950 px-6 sm:px-10 py-3 flex flex-wrap gap-2">
        {sections.map((s) => (
          <button
            key={s.id}
            onClick={() => setActive(s.id)}
            className={`text-xs px-3 py-1.5 rounded-full border transition-all duration-150 ${
              active === s.id
                ? "bg-white text-black border-white font-medium"
                : "border-zinc-800 text-zinc-400 hover:border-zinc-600 hover:text-zinc-200"
            }`}
          >
            {s.icon} {s.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="max-w-3xl mx-auto px-6 sm:px-10 py-10">
        {/* Section header */}
        <div className="flex items-center gap-3 mb-6">
          <div className="w-8 h-8 bg-white rounded-lg flex items-center justify-center text-sm">
            {sections.find((s) => s.id === active)?.icon}
          </div>
          <h2 className="text-lg font-bold tracking-tight">
            {sections.find((s) => s.id === active)?.label}
          </h2>
        </div>

        <ActiveSection />

        {/* Footer nav */}
        <div className="flex justify-between mt-12 pt-6 border-t border-zinc-900">
          {sections.findIndex((s) => s.id === active) > 0 ? (
            <button
              onClick={() =>
                setActive(
                  sections[sections.findIndex((s) => s.id === active) - 1].id,
                )
              }
              className="text-xs text-zinc-500 hover:text-white transition-colors flex items-center gap-1"
            >
              ← {sections[sections.findIndex((s) => s.id === active) - 1].label}
            </button>
          ) : (
            <span />
          )}
          {sections.findIndex((s) => s.id === active) < sections.length - 1 ? (
            <button
              onClick={() =>
                setActive(
                  sections[sections.findIndex((s) => s.id === active) + 1].id,
                )
              }
              className="text-xs text-zinc-500 hover:text-white transition-colors flex items-center gap-1"
            >
              {sections[sections.findIndex((s) => s.id === active) + 1].label} →
            </button>
          ) : (
            <span />
          )}
        </div>
      </div>
    </div>
    </PageTransition>
  );
}
