'use client';

import { useState } from 'react';

const API_BASE =
  process.env.NEXT_PUBLIC_BACKEND_URL?.replace(/\/+$/, '') ||
  'https://teknovashop-forge.onrender.com'; // fallback por si no defines la env en Vercel

type GenerateResponse =
  | { status: 'ok'; stl_url: string }
  | { status: 'error'; message?: string };

export default function Page() {
  const [downloading, setDownloading] = useState(false);
  const [lastUrl, setLastUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleGenerate() {
    setError(null);
    setLastUrl(null);
    setDownloading(true);

    try {
      // Puedes enviar un payload real cuando tengas parámetros. De momento, uno mínimo válido.
      const payload = {
        order_id: `web-${Date.now()}`,
        model_slug: 'vesa-adapter',
        params: { width: 180, height: 180, thickness: 6, pattern: '100x100' },
        license: 'personal',
      };

      const res = await fetch(`${API_BASE}/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        // Si hay CORS y el back lo permite, no hace falta nada más
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const text = await res.text().catch(() => '');
        throw new Error(`Backend ${res.status}: ${text || res.statusText}`);
      }

      const data: GenerateResponse = await res.json();

      if (data.status !== 'ok') {
        throw new Error(
          'Error del backend' + ('message' in data && data.message ? `: ${data.message}` : '')
        );
      }

      const url = data.stl_url;
      setLastUrl(url);

      // Disparar descarga automática
      const a = document.createElement('a');
      a.href = url;
      // Nombre de archivo sugerido (si el servidor no fuerza cabeceras de filename)
      a.download = `teknovashop-${new Date().toISOString().replace(/[:.]/g, '-')}.stl`;
      a.target = '_blank'; // por si el navegador bloquea descargas, abre pestaña
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (e: any) {
      setError(e?.message || 'Fallo al generar/descargar el STL');
    } finally {
      setDownloading(false);
    }
  }

  return (
    <main
      style={{
        minHeight: '100dvh',
        display: 'grid',
        placeItems: 'start',
        padding: '3rem 1.25rem',
        gap: '1rem',
        maxWidth: 960,
        marginInline: 'auto',
        fontFamily:
          'ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Noto Sans, Helvetica Neue, Arial, "Apple Color Emoji","Segoe UI Emoji"',
      }}
    >
      <h1 style={{ fontSize: 'clamp(1.75rem, 1.2rem + 1.8vw, 2.25rem)', fontWeight: 700 }}>
        Teknovashop Forge
      </h1>

      <button
        onClick={handleGenerate}
        disabled={downloading}
        style={{
          appearance: 'none',
          border: 0,
          background: downloading ? '#94a3b8' : '#111827',
          color: 'white',
          padding: '0.75rem 1rem',
          borderRadius: 12,
          fontWeight: 600,
          cursor: downloading ? 'not-allowed' : 'pointer',
          transition: 'background .15s ease',
        }}
      >
        {downloading ? 'Generando…' : 'Generar STL'}
      </button>

      {error && (
        <p style={{ color: '#b91c1c', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
          Error: {error}
        </p>
      )}

      {lastUrl && (
        <pre
          style={{
            background: '#0b1220',
            color: '#e5e7eb',
            padding: '1rem',
            borderRadius: 12,
            overflowX: 'auto',
            maxWidth: '100%',
          }}
        >
{`{
  "status": "ok",
  "stl_url": "${lastUrl}"
}`}
        </pre>
      )}

      <section style={{ marginTop: '1rem', color: '#475569', fontSize: 14, lineHeight: 1.45 }}>
        <p style={{ margin: 0 }}>
          Backend: <code>{API_BASE}</code>
        </p>
        <p style={{ marginTop: 4 }}>
          Asegúrate de que el backend tiene CORS permitido para esta URL.
        </p>
      </section>
    </main>
  );
}
