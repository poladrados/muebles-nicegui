# main.py — Inventario El Jueves (NiceGUI + asyncpg)
# Fixes: desactiva y limpia Service Worker para evitar recargas, ancla miniaturas, botones admin operativos (diálogos completos + 'Vendido' = eliminar)

from nicegui import ui, app
from fastapi import Response, Request, status
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse, RedirectResponse, JSONResponse
import asyncpg
import os, base64, urllib.parse, urllib.request, hashlib, hmac, asyncio, html, math
from functools import partial
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime
from PIL import Image, features
from io import BytesIO
import json

load_dotenv()
PAGE_SIZE = 30
THUMB_VER = "4"  # cache-buster miniaturas (subido para forzar recarga)
BASE_URL = os.getenv('BASE_URL', 'https://inventarioeljueves.app')

try:
    import google.generativeai as genai
    _gem_key = os.getenv('GEMINI_API_KEY', '').strip()
    if _gem_key:
        genai.configure(api_key=_gem_key)
    HAS_GEMINI = bool(_gem_key)
except ImportError:
    HAS_GEMINI = False

# ---------- helpers ----------
def _esc(s: str) -> str:
    return html.escape(s or '')

def _origin_from(request: Request) -> str:
    """Origen absoluto fiable del host que ha hecho la petición."""
    # request.base_url == "https://host/"  -> quitamos la barra final
    return str(request.base_url).rstrip('/')
async def _read_upload_bytes(e) -> bytes:
    """Devuelve los bytes de un UploadEvent de NiceGUI, sea cual sea el formato."""
    # 1) bytes directos
    c = getattr(e, 'content', None)
    if isinstance(c, (bytes, bytearray, memoryview)):
        return bytes(c)

    # 2) UploadFile en e.content o e.file (read() puede ser async)
    for obj in (c, getattr(e, 'file', None)):
        if obj is None:
            continue
        read = getattr(obj, 'read', None)
        if callable(read):
            try:
                res = read()
                if asyncio.iscoroutine(res):
                    res = await res
                if res:
                    return bytes(res)
            except Exception:
                pass

    # 3) Lista de archivos (NiceGUI recientes)
    files = getattr(e, 'files', None)
    if files:
        for f in files:
            read = getattr(f, 'read', None)
            if callable(read):
                try:
                    res = read()
                    if asyncio.iscoroutine(res):
                        res = await res
                    if res:
                        return bytes(res)
                except Exception:
                    continue

    # 4) Fallback si se guardó a disco
    for attr in ('path', 'saved_path', 'tempfile'):
        p = getattr(e, attr, None)
        if p and isinstance(p, str) and os.path.exists(p):
            try:
                with open(p, 'rb') as fh:
                    return fh.read()
            except Exception:
                pass

    return b''

# ---------- PWA / static ----------
try:
    app.add_static_files('/muebles-app', 'static')
except Exception:
    pass

HEAD_HTML = """
<link rel="manifest" href="/manifest.webmanifest?v=20250906">
<link rel="icon" type="image/png" sizes="32x32" href="/muebles-app/images/icon-192.png?v=4">
<link rel="icon" href="/favicon.ico">
<link rel="apple-touch-icon" sizes="180x180" href="/muebles-app/images/apple-touch-icon.png">
<meta name="theme-color" content="#023e8a">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, user-scalable=no">

<!-- iOS PWA -->
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Inventario El Jueves">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="format-detection" content="telephone=no">

<style>
  /* ============================================================
     Inventario El Jueves — Sistema de diseño editorial
     Concepto: catálogo de subastas / cartela de museo
     ============================================================ */
  :root {
    --bg:        #E6F0F8;
    --ink:       #023e8a;
    --ink-deep:  #021f4d;
    --paper:    #FBF8F3;
    --paper-2:  #F5EFE3;
    --brass:    #A07A2E;
    --brass-2:  #C9A24A;
    --brass-soft:#D9C79B;
    --text:     #1A2438;
    --text-soft:#5A6478;
    --hairline: rgba(160,122,46,.28);
    --hairline-strong: rgba(160,122,46,.55);
    --shadow-card: 0 1px 0 rgba(160,122,46,.08), 0 8px 24px -12px rgba(2,31,77,.18), 0 2px 6px -3px rgba(2,31,77,.10);
    --shadow-card-hover: 0 1px 0 rgba(160,122,46,.16), 0 18px 40px -18px rgba(2,31,77,.28), 0 4px 12px -4px rgba(2,31,77,.14);
  }

  input, select, textarea { font-size: 16px !important; }

  /* Tipografía base */
  body, .nicegui-content, .q-page, .q-card {
    font-family: 'Cormorant Garamond', Georgia, 'Times New Roman', serif;
    color: var(--text);
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }
  body { background: var(--bg) !important; }
  ::selection { background: var(--ink); color: var(--paper); }

  /* Scrollbar refinada (webkit) */
  ::-webkit-scrollbar { width: 10px; height: 10px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: var(--hairline-strong); border-radius: 999px; }
  ::-webkit-scrollbar-thumb:hover { background: var(--brass); }

  /* iOS PWA (cuando hay clase pwa-standalone) */
  .pwa-standalone body {
    margin: 0;
    padding: env(safe-area-inset-top) env(safe-area-inset-right)
             env(safe-area-inset-bottom) env(safe-area-inset-left);
    overflow-x: hidden;
    overflow-y: auto;
  }
  .pwa-standalone header { padding-top: env(safe-area-inset-top); }

  /* Modo app (standalone) en iOS y Android */
  @media all and (display-mode: standalone) {
    html, body {
      position: static;
      width: 100%;
      height: auto;
      min-height: 100%;
      overflow-x: hidden;
      overflow-y: auto;
      -webkit-overflow-scrolling: touch;
      overscroll-behavior-y: contain;
    }
  }

  @media (max-width: 640px) {
    body { -webkit-user-select: none; user-select: none; -webkit-touch-callout: none; -webkit-tap-highlight-color: transparent; }
  }

  /* ============================================================
     HEADER editorial
     ============================================================ */
  .site-header {
    width: 100%;
    background: var(--paper);
    margin: 24px 0 28px;
    border-top: 1px solid var(--hairline-strong);
    border-bottom: 1px solid var(--hairline-strong);
    box-shadow: var(--shadow-card);
    position: relative;
  }
  .site-header::before, .site-header::after {
    content: "";
    position: absolute; left: 0; right: 0; height: 1px;
    background: var(--hairline);
  }
  .site-header::before { top: 4px; }
  .site-header::after  { bottom: 4px; }
  .site-header-inner {
    display: flex; align-items: center; justify-content: center;
    gap: 18px; padding: 22px 28px; text-align: center;
  }
  .site-header-logo {
    height: clamp(34px, 4.8vw, 54px);
    width: auto;
    filter: drop-shadow(0 1px 2px rgba(2,31,77,.18));
  }
  .site-header-ornament {
    color: var(--brass);
    font-family: 'Playfair Display', serif;
    font-size: 18px;
    line-height: 1;
    opacity: .85;
  }
  .site-header-title {
    font-family: 'Playfair Display', serif !important;
    font-weight: 700;
    color: var(--ink) !important;
    font-size: clamp(20px, 3.2vw, 32px) !important;
    letter-spacing: .01em;
    margin: 0 !important;
    line-height: 1.15;
  }

  /* ============================================================
     CARD de mueble (cartela de museo)
     ============================================================ */
  .mueble-card.q-card {
    width: 100%;
    background: var(--paper) !important;
    border: 1px solid var(--hairline);
    border-radius: 4px !important;
    box-shadow: var(--shadow-card);
    padding: 22px 24px !important;
    margin-bottom: 18px;
    transition: box-shadow .35s ease, transform .35s ease;
    position: relative;
    overflow: hidden;
  }
  .mueble-card.q-card::before {
    content: "";
    position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, transparent, var(--brass) 50%, transparent);
    opacity: .55;
  }
  .mueble-card.q-card:hover { box-shadow: var(--shadow-card-hover); }

  /* Cabecera de card: título + precio */
  .mueble-head {
    display: flex; align-items: baseline; justify-content: space-between;
    gap: 18px; flex-wrap: wrap;
    padding-bottom: 14px;
    margin-bottom: 14px;
    border-bottom: 1px solid var(--hairline);
  }
  .mueble-title.q-label, .mueble-title {
    font-family: 'Playfair Display', serif !important;
    font-weight: 700 !important;
    font-size: clamp(20px, 2.6vw, 26px) !important;
    color: var(--ink) !important;
    line-height: 1.2 !important;
    letter-spacing: .005em;
    text-transform: none !important;
  }
  .mueble-price {
    font-family: 'Playfair Display', serif !important;
    font-weight: 700 !important;
    font-size: clamp(22px, 3vw, 30px) !important;
    color: var(--brass) !important;
    letter-spacing: .01em;
    line-height: 1 !important;
    white-space: nowrap;
  }
  .mueble-badge-nuevo {
    display: inline-block;
    font-family: 'Inter Tight', system-ui, sans-serif !important;
    font-size: 10px !important;
    font-weight: 600 !important;
    letter-spacing: .18em;
    text-transform: uppercase;
    color: var(--paper) !important;
    background: var(--ink) !important;
    padding: 3px 10px;
    border-radius: 999px;
    margin-left: 10px;
    vertical-align: middle;
  }

  /* Pares etiqueta / valor */
  .kv-row {
    display: grid;
    grid-template-columns: 130px 1fr;
    gap: 14px;
    padding: 6px 0;
    align-items: baseline;
    border-bottom: 1px dotted var(--hairline);
  }
  .kv-row:last-of-type { border-bottom: none; }
  .kv-label.q-label, .kv-label {
    font-family: 'Inter Tight', system-ui, sans-serif !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    letter-spacing: .22em;
    text-transform: uppercase;
    color: var(--brass) !important;
    line-height: 1.4 !important;
  }
  .kv-value.q-label, .kv-value {
    font-family: 'Cormorant Garamond', Georgia, serif !important;
    font-size: 17px !important;
    color: var(--text) !important;
    line-height: 1.45 !important;
    font-weight: 500;
  }
  .kv-value-desc { font-style: italic; color: var(--text-soft) !important; }
  @media (max-width: 640px) {
    .kv-row { grid-template-columns: 100px 1fr; gap: 10px; }
    .kv-value.q-label, .kv-value { font-size: 16px !important; }
  }

  /* Acciones (WhatsApp, admin) */
  .mueble-actions {
    display: flex; flex-wrap: wrap; gap: 8px;
    margin-top: 16px;
    padding-top: 14px;
    border-top: 1px solid var(--hairline);
    align-items: center;
  }
  .mueble-actions-admin { margin-left: auto; display: flex; gap: 6px; flex-wrap: wrap; }

  /* WhatsApp pill */
  .btn-whatsapp {
    display: inline-flex; align-items: center; gap: 8px;
    font-family: 'Inter Tight', system-ui, sans-serif !important;
    font-size: 11px !important;
    font-weight: 600;
    letter-spacing: .18em;
    text-transform: uppercase;
    color: var(--brass) !important;
    background: transparent;
    border: 1px solid var(--hairline-strong);
    padding: 7px 14px;
    border-radius: 999px;
    text-decoration: none !important;
    transition: background .2s ease, color .2s ease, border-color .2s ease;
    cursor: pointer;
  }
  .btn-whatsapp:hover {
    background: var(--brass);
    color: var(--paper) !important;
    border-color: var(--brass);
  }
  .btn-whatsapp svg { width: 14px; height: 14px; flex: 0 0 auto; }

  /* Botones admin "ghost" — discretos, brass outline */
  .btn-ghost.q-btn {
    font-family: 'Inter Tight', system-ui, sans-serif !important;
    font-size: 10px !important;
    font-weight: 600 !important;
    letter-spacing: .2em;
    text-transform: uppercase;
    color: var(--brass) !important;
    background: transparent !important;
    border: 1px solid var(--hairline-strong) !important;
    border-radius: 999px !important;
    padding: 6px 14px !important;
    min-height: 0 !important;
    box-shadow: none !important;
    transition: background .2s ease, color .2s ease, border-color .2s ease;
  }
  .btn-ghost.q-btn .q-btn__content { padding: 0 !important; }
  .btn-ghost.q-btn:hover {
    background: var(--brass) !important;
    color: var(--paper) !important;
    border-color: var(--brass) !important;
  }
  .btn-ghost-danger.q-btn { color: #8a2e2e !important; border-color: rgba(138,46,46,.4) !important; }
  .btn-ghost-danger.q-btn:hover { background: #8a2e2e !important; color: var(--paper) !important; border-color: #8a2e2e !important; }

  /* Botón hamburguesa refinado */
  .hamburger-btn.q-btn {
    width: 44px; height: 44px;
    border-radius: 999px !important;
    border: 1px solid var(--hairline-strong) !important;
    background: var(--paper) !important;
    color: var(--ink) !important;
    box-shadow: 0 2px 8px rgba(2,31,77,.15) !important;
    transition: transform .2s ease, box-shadow .2s ease;
  }
  .hamburger-btn.q-btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(2,31,77,.22) !important;
  }

  /* Botón primario "Añadir nueva antigüedad" */
  .btn-primary-editorial.q-btn {
    font-family: 'Inter Tight', system-ui, sans-serif !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    letter-spacing: .22em;
    text-transform: uppercase;
    color: var(--paper) !important;
    background: var(--ink) !important;
    border: 1px solid var(--ink) !important;
    border-radius: 2px !important;
    padding: 10px 22px !important;
    box-shadow: 0 2px 6px rgba(2,31,77,.25) !important;
    transition: background .2s ease, box-shadow .2s ease;
  }
  .btn-primary-editorial.q-btn:hover {
    background: var(--ink-deep) !important;
    box-shadow: 0 4px 12px rgba(2,31,77,.35) !important;
  }

  /* ============================================================
     FILTROS — panel editorial
     ============================================================ */
  .filtros-panel {
    background: var(--paper);
    border: 1px solid var(--hairline);
    border-radius: 4px;
    padding: 18px 22px 14px;
    margin-bottom: 22px;
    box-shadow: var(--shadow-card);
    position: relative;
  }
  .filtros-panel::before {
    content: "Filtrar el inventario";
    position: absolute; top: -10px; left: 22px;
    background: var(--paper);
    padding: 0 10px;
    font-family: 'Inter Tight', system-ui, sans-serif;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: .25em;
    text-transform: uppercase;
    color: var(--brass);
  }
  .filtros-panel .q-field__control {
    background: transparent !important;
    border-bottom: 1px solid var(--hairline-strong) !important;
    border-radius: 0 !important;
    padding: 0 4px !important;
    min-height: 42px !important;
  }
  .filtros-panel .q-field__control::before,
  .filtros-panel .q-field__control::after { display: none !important; }
  .filtros-panel .q-field__label {
    font-family: 'Inter Tight', system-ui, sans-serif !important;
    font-size: 10px !important;
    font-weight: 600 !important;
    letter-spacing: .2em;
    text-transform: uppercase;
    color: var(--brass) !important;
  }
  .filtros-panel .q-field__native,
  .filtros-panel .q-field__input {
    font-family: 'Cormorant Garamond', Georgia, serif !important;
    font-size: 17px !important;
    color: var(--text) !important;
  }
  .filtros-panel .q-field--focused .q-field__control { border-bottom-color: var(--ink) !important; }
  .filtros-panel .q-field--focused .q-field__label { color: var(--ink) !important; }

  @media (max-width: 640px) {
    .filtros-panel::before { display: none; }
    .filtros-summary {
      display: block;
      padding: 4px 0;
      cursor: pointer;
      font-family: 'Inter Tight', system-ui, sans-serif;
      font-size: 10px;
      font-weight: 600;
      letter-spacing: .25em;
      text-transform: uppercase;
      color: var(--brass);
      list-style: none;
    }
    .filtros-summary::-webkit-details-marker { display: none; }
  }
  @media (min-width: 641px) {
    details.filtros-panel > summary { display: none !important; }
  }

  /* ============================================================
     EXPANSION — "Ver más imágenes" / "Ver más"
     ============================================================ */
  .editorial-expansion.q-expansion-item {
    margin-top: 14px;
    border-top: 1px solid var(--hairline);
  }
  .editorial-expansion .q-expansion-item__container > .q-item {
    background: transparent !important;
    padding: 12px 4px !important;
    min-height: 0 !important;
  }
  .editorial-expansion .q-item__label {
    font-family: 'Inter Tight', system-ui, sans-serif !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    letter-spacing: .22em;
    text-transform: uppercase;
    color: var(--brass) !important;
  }
  .editorial-expansion .q-expansion-item__toggle-icon { color: var(--brass) !important; }
  .editorial-expansion .q-expansion-item__content {
    background: transparent !important;
    padding: 8px 4px 4px !important;
  }

  /* ============================================================
     ANIMACIÓN DE ENTRADA — stagger sutil
     ============================================================ */
  @keyframes mueble-fade-in {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  .mueble-card.q-card {
    animation: mueble-fade-in .55s cubic-bezier(.2,.6,.2,1) both;
  }
  .mueble-card.q-card:nth-of-type(1) { animation-delay: .02s; }
  .mueble-card.q-card:nth-of-type(2) { animation-delay: .08s; }
  .mueble-card.q-card:nth-of-type(3) { animation-delay: .14s; }
  .mueble-card.q-card:nth-of-type(4) { animation-delay: .20s; }
  .mueble-card.q-card:nth-of-type(5) { animation-delay: .26s; }
  .mueble-card.q-card:nth-of-type(n+6) { animation-delay: .32s; }
  @media (prefers-reduced-motion: reduce) {
    .mueble-card.q-card { animation: none; }
  }

  /* ============================================================
     Layout responsive existente — preservado
     ============================================================ */
  .card-flex { display:flex; gap:24px; align-items:flex-start; flex-wrap:nowrap; }
  .card-main { flex:0 0 auto; width:clamp(280px, 36vw, 520px); }
  .card-details { flex:1 1 320px; min-width:300px; }
  .card-thumb {
    width:100%; height:240px; object-fit:cover;
    border-radius: 3px;
    cursor:zoom-in;
    box-shadow: 0 6px 18px -8px rgba(2,31,77,.35), 0 1px 0 var(--hairline);
    transition: transform .4s ease, box-shadow .4s ease;
  }
  .card-thumb:hover { transform: scale(1.015); box-shadow: 0 12px 28px -10px rgba(2,31,77,.45); }
  @media (max-width: 640px) {
    .card-flex { flex-wrap:wrap !important; }
    .card-main { width:100% !important; }
    .card-details { flex:1 1 100% !important; min-width:0 !important; }
    .card-thumb { height:auto !important; aspect-ratio: 4 / 3; }
  }

  /* ============================================================
     Skeleton shimmer para imágenes mientras cargan
     ============================================================ */
  @keyframes shimmer {
    0%   { background-position: -200% 0; }
    100% { background-position:  200% 0; }
  }
  .card-thumb,
  .thumb-skeleton {
    background-color: var(--brass-soft);
    background-image: linear-gradient(
      90deg,
      var(--brass-soft) 0%,
      var(--paper-2) 50%,
      var(--brass-soft) 100%
    );
    background-size: 200% 100%;
    animation: shimmer 1.6s ease-in-out infinite;
  }
  .card-thumb[data-loaded="true"],
  .thumb-skeleton[data-loaded="true"] {
    background: transparent;
    animation: none;
  }

  /* Compatibilidad clases antiguas (por si quedan referencias) */
  .kv{margin:0;}
  .kv .k, .kv b, .kv strong{font-weight:700 !important; margin-right:6px;}
  .kv-desc .v { font-size: 1.05rem; line-height: 1.5; }
  .kv-attr, .kv-line { padding-bottom: 0 !important; line-height: 1.5; }
</style>
<style>
  /* Botón flotante que respeta los safe areas en PWA */
  .safe-top-left {
    position: fixed;
    z-index: 2147483647;

    /* Fallback para navegadores sin safe-area */
    top: 12px; left: 12px;

    /* Soporte iOS antiguo y moderno */
    top: calc(constant(safe-area-inset-top) + 12px);
    top: calc(env(safe-area-inset-top) + 12px);
    left: calc(constant(safe-area-inset-left) + 12px);
    left: calc(env(safe-area-inset-left) + 12px);
  }
</style>
<style>
  @media (max-width: 640px) {
    .hide-on-mobile { display: none !important; }
  }
</style>

<style>
  .safe-top-right {
    position: absolute;             /* relativo al drawer */
    z-index: 2147483647;

    /* Fallback cómodo dentro del drawer */
    top: 10px; right: 10px;

    /* Solo compensamos notch por arriba; en el lado derecho NO aplicamos safe-area
       porque estamos dentro de un panel lateral, no en el borde de pantalla */
    top: calc(constant(safe-area-inset-top) + 10px);
    top: calc(env(safe-area-inset-top) + 10px);
  }
</style>



<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;800&family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400&family=Inter+Tight:wght@500;600;700&display=swap" rel="stylesheet">

<script>
if (window.navigator.standalone === true) {
  document.documentElement.classList.add('pwa-standalone');
}

function copiarEnlace(btn, url) {
  var copy = function() {
    var orig = btn.innerHTML;
    btn.innerHTML = '<span>✓ Copiado</span>';
    btn.style.background = 'var(--ink)';
    btn.style.color = 'var(--paper)';
    btn.style.borderColor = 'var(--ink)';
    setTimeout(function() {
      btn.innerHTML = orig;
      btn.style.background = '';
      btn.style.color = '';
      btn.style.borderColor = '';
    }, 2000);
  };
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(url).then(copy);
  } else {
    var ta = document.createElement('textarea');
    ta.value = url; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); } catch(e) {}
    document.body.removeChild(ta);
    copy();
  }
}

/* ¡Importante!: SIN registro de Service Worker aquí para evitar bucles de recarga */

var _paq = window._paq = window._paq || [];
_paq.push(['trackPageView']); _paq.push(['enableLinkTracking']);
// Matomo
(function() {
  var u="__MATOMO_URL__";
  _paq.push(['setTrackerUrl', u+'matomo.php']);
  _paq.push(['setSiteId', '1']);
  var d=document, g=d.createElement('script'), s=d.getElementsByTagName('script')[0];
  g.async=true; g.src='https://cdn.matomo.cloud/inventarioeljueves.matomo.cloud/matomo.js';
  s.parentNode.insertBefore(g,s);
})();

function syncFiltrosOpen() {
  var el = document.querySelector('details.filtros-panel');
  if (!el) return;
  if (window.matchMedia('(max-width: 640px)').matches) {
    el.removeAttribute('open');
  } else {
    el.setAttribute('open', '');
  }
}
addEventListener('DOMContentLoaded', function() {
  syncFiltrosOpen();
  setTimeout(syncFiltrosOpen, 200);
  setTimeout(syncFiltrosOpen, 800);
});
addEventListener('resize', function() {
  requestAnimationFrame(syncFiltrosOpen);
});
</script>
""".replace('__MATOMO_URL__', os.getenv('MATOMO_URL', 'https://inventarioeljueves.matomo.cloud/'))

# ---------- DB ----------
DB_DSN = (
    f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
    f"@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}?sslmode=require"
)

# ---------- Cloudflare R2 (storage de imágenes) ----------
import boto3
from botocore.config import Config

R2_ACCESS_KEY_ID     = os.getenv('R2_ACCESS_KEY_ID')
R2_SECRET_ACCESS_KEY = os.getenv('R2_SECRET_ACCESS_KEY')
R2_BUCKET_NAME       = os.getenv('R2_BUCKET_NAME')
R2_ENDPOINT_URL      = os.getenv('R2_ENDPOINT_URL')
R2_PUBLIC_URL        = (os.getenv('R2_PUBLIC_URL') or '').rstrip('/')
R2_ENABLED = all([R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME,
                  R2_ENDPOINT_URL, R2_PUBLIC_URL])

_r2_client_cache = None
def _r2_client():
    global _r2_client_cache
    if _r2_client_cache is None:
        _r2_client_cache = boto3.client(
            's3',
            endpoint_url=R2_ENDPOINT_URL,
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY,
            config=Config(signature_version='s3v4'),
            region_name='auto',
        )
    return _r2_client_cache

def _r2_put(key: str, data: bytes, mime: str = 'image/webp'):
    _r2_client().put_object(
        Bucket=R2_BUCKET_NAME, Key=key, Body=data, ContentType=mime,
        CacheControl='public, max-age=31536000, immutable',
    )

def _r2_delete(key: str):
    try:
        _r2_client().delete_object(Bucket=R2_BUCKET_NAME, Key=key)
    except Exception as e:
        print(f"[r2] delete fallo key={key}: {e}")

def _r2_key_from_url(url: str | None) -> str | None:
    if not url or not R2_PUBLIC_URL or not url.startswith(R2_PUBLIC_URL):
        return None
    return url[len(R2_PUBLIC_URL):].lstrip('/')

@app.on_startup
async def startup():
    app.state.pool = await asyncpg.create_pool(dsn=DB_DSN, min_size=1, max_size=5)
    async with app.state.pool.acquire() as conn:
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_muebles_vendido_tienda ON muebles (vendido, tienda)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_muebles_tipo ON muebles (tipo)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_muebles_lower_nombre ON muebles (LOWER(nombre))")

@app.on_shutdown
async def shutdown():
    await app.state.pool.close()

# ---------- Auth ----------
ADMIN_PASSWORD_HASH = os.getenv('ADMIN_PASSWORD_HASH', '')  # SHA256 hex

def _verify_admin(pwd: str) -> bool:
    return bool(ADMIN_PASSWORD_HASH) and hmac.compare_digest(
        hashlib.sha256(pwd.encode()).hexdigest(), ADMIN_PASSWORD_HASH
    )

def is_admin() -> bool:
    return bool(app.storage.user.get('is_admin', False))

# ---------- Utilidades ----------
TIPOS = ["Mesa","Consola","Buffet","Biblioteca","Armario","Cómoda","Columna","Espejo","Copa","Asiento","Otro artículo"]

async def analyze_image_with_gemini(image_bytes: bytes) -> dict:
    if not HAS_GEMINI:
        return {}
    prompt = (
        "Eres un experto en antigüedades y muebles. Analiza esta imagen y "
        "devuelve SOLO un JSON válido con estos campos exactos:\n"
        "{\n"
        '  "nombre": "nombre descriptivo del mueble en español, máximo 60 caracteres",\n'
        '  "tipo": "uno de estos valores exactos: Mesa, Consola, Buffet, Biblioteca, '
        'Armario, Cómoda, Columna, Espejo, Copa, Asiento, Otro artículo",\n'
        '  "descripcion": "descripción del estilo, época estimada, materiales y '
        'estado aparente. Máximo 300 caracteres."\n'
        "}\n"
        "Solo el JSON puro, sin texto adicional, sin backticks, sin markdown."
    )
    try:
        img = Image.open(BytesIO(image_bytes))
        img.thumbnail((1024, 1024))
        model = genai.GenerativeModel('gemini-2.5-flash')
        resp = await asyncio.to_thread(model.generate_content, [prompt, img])
        text = (resp.text or '').strip()
        if text.startswith('```'):
            text = text.strip('`').strip()
            if text.lower().startswith('json'):
                text = text[4:].strip()
        data = json.loads(text)
        if data.get('tipo') not in TIPOS:
            data['tipo'] = 'Otro artículo'
        return {
            'nombre': str(data.get('nombre', ''))[:60],
            'tipo': data.get('tipo', 'Otro artículo'),
            'descripcion': str(data.get('descripcion', ''))[:300],
        }
    except Exception as e:
        print(f'[gemini] error: {e}')
        return {}

def mostrar_medidas_extendido(m):
    etq = {'alto':"Alto",'largo':"Largo",'fondo':"Fondo",'diametro':"Diámetro",
           'diametro_base':"Ø Base",'diametro_boca':"Ø Boca",
           'alto_respaldo':"Alto respaldo",'alto_asiento':"Alto asiento",'ancho':"Ancho"}
    partes=[]
    for k,n in etq.items():
        v = m.get(k)
        if v not in [None,0]:
            try: partes.append(f"{n}: {float(v):.1f}cm")
            except: partes.append(f"{n}: {v}cm")
    return " · ".join(partes) if partes else "Sin medidas"

def _none_if_empty_or_zero(v):
    try:
        if v in (None, ''): return None
        f = float(v);  return None if f == 0 else f
    except Exception:
        return v or None

# --- NUEVO: conversor robusto para precio (admite "100,00" y valores None) ---
def _to_float_or_none(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(',', '.')
    try:
        return float(s)
    except Exception:
        return None

from PIL import Image, features  # ya importado arriba

def _encode_image_to_webp_or_jpeg(im: Image.Image, max_size=800, quality=85) -> tuple[bytes, str]:
    """Devuelve (bytes, mime) en WEBP si hay soporte; si no, en JPEG."""
    if im.mode not in ('RGB', 'RGBA'):
        im = im.convert('RGB')
    im = im.copy()
    im.thumbnail((max_size, max_size))
    buf = BytesIO()

    if features.check('webp'):
        im.save(buf, format='WEBP', quality=quality, method=6)
        return buf.getvalue(), 'image/webp'
    else:
        im = im.convert('RGB')
        im.save(buf, format='JPEG', quality=quality, optimize=True, progressive=True)
        return buf.getvalue(), 'image/jpeg'

def to_img_bytes(raw: bytes, max_size=800, quality=85) -> bytes:
    """Convierte bytes a WEBP o, si no hay soporte, a JPEG."""
    im = Image.open(BytesIO(raw))
    data, _mime = _encode_image_to_webp_or_jpeg(im, max_size=max_size, quality=quality)
    return data

def _thumb_bytes(src: bytes, px=720) -> tuple[bytes, str]:
    """Thumbnail: devuelve (bytes, mime) en WEBP o JPEG."""
    im = Image.open(BytesIO(src))
    data, mime = _encode_image_to_webp_or_jpeg(im, max_size=px, quality=92)
    return data, mime

def _detect_mime(data: bytes) -> str:
    """Detecta el Content-Type real de unos bytes de imagen."""
    try:
        fmt = Image.open(BytesIO(data)).format or ''
        fmt = fmt.upper()
        if fmt == 'WEBP':
            return 'image/webp'
        if fmt == 'PNG':
            return 'image/png'
        return 'image/jpeg'
    except Exception:
        return 'application/octet-stream'


def es_nuevo(fecha_val)->bool:
    if not fecha_val: return False
    if isinstance(fecha_val, datetime): fecha=fecha_val
    else:
        try: fecha=datetime.fromisoformat(str(fecha_val))
        except: return False
    delta=(datetime.now(fecha.tzinfo)-fecha) if fecha.tzinfo else (datetime.now()-fecha)
    return delta.days <= 1


def _cache_headers(data: bytes):
    etag = 'W/"%s"' % hashlib.md5(data).hexdigest()
    return {'Cache-Control':'public, max-age=2592000','ETag':etag}, etag

# ----- Formato ES (precio / fecha) -----
import math

import math

def _fmt_precio(p):
    # Vacíos: no muestres nada
    if p in (None, '', 'None'):
        return ''

    # Acepta coma decimal
    s = str(p).strip().replace(',', '.')
    try:
        n = float(s)
    except Exception:
        # Cualquier cosa no parseable: muéstralo tal cual + €
        return f"{p} €"

    # No asumir NaN/Inf como número válido
    if not math.isfinite(n):
        return ''

    # Entero exacto
    if math.isclose(n, round(n), rel_tol=0, abs_tol=1e-6):
        s_ent = f"{int(round(n)):,}".replace(",", ".")
        return f"{s_ent} €"

    # Con decimales (formato ES)
    entero = int(n)  # si n es negativo, int ya trunca hacia 0; es OK para mostrar
    dec = abs(n - entero)
    s_ent = f"{entero:,}".replace(",", ".")
    s_dec = f"{dec:.2f}"[1:].replace(".", ",")
    return f"{s_ent}{s_dec} €"


from datetime import datetime

def _parse_dt(dt):
    if isinstance(dt, datetime): return dt
    try: return datetime.fromisoformat(str(dt))
    except: return None

def _fmt_fecha(dt):
    d = _parse_dt(dt)
    return d.strftime("%d/%m/%Y %H:%M") if d else (str(dt) if dt else "")

@app.get('/img/{mueble_id}')
async def img(request: Request, mueble_id: int, i: int = 0, thumb: int = 0):
    try:
        async with app.state.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT imagen_base64, imagen_url FROM imagenes_muebles
                WHERE mueble_id=$1
                ORDER BY es_principal DESC, id ASC
                OFFSET $2 LIMIT 1
            """, mueble_id, i)

        if not row:
            print(f"[img] 404 mid={mueble_id} i={i}")
            return Response(status_code=404)

        if row['imagen_url']:
            return RedirectResponse(row['imagen_url'], status_code=307)

        data = base64.b64decode(row['imagen_base64'])

        if thumb == 1:
            # _thumb_bytes devuelve (bytes, mime)
            data, mime = _thumb_bytes(data, 720)
        else:
            # Detecta el tipo real por si guardaste JPEG/PNG
            mime = _detect_mime(data)

        headers, etag = _cache_headers(data)
        if request.headers.get('if-none-match') == etag:
            return Response(status_code=304, headers=headers)

        return Response(content=data, media_type=mime, headers=headers)

    except Exception as e:
        print(f"[img] ERROR mid={mueble_id} i={i}: {type(e).__name__}: {e}")
        return Response(status_code=500)


@app.get('/img_by_id/{img_id}')
async def img_by_id(request: Request, img_id: int, thumb: int = 0):
    async with app.state.pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT imagen_base64, imagen_url FROM imagenes_muebles WHERE id=$1', img_id
        )
    if not row:
        return Response(status_code=404)

    if row['imagen_url']:
        return RedirectResponse(row['imagen_url'], status_code=307)

    data = base64.b64decode(row['imagen_base64'])
    if thumb == 1:
        data, mime = _thumb_bytes(data, 720)
    else:
        mime = _detect_mime(data)

    headers, etag = _cache_headers(data)
    if request.headers.get('if-none-match') == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=data, media_type=mime, headers=headers)

# === JPEG 1200px para Open Graph (WhatsApp/Twitter/FB) ===
def _jpeg_from_b64(b64: str, max_w: int = 1200, quality: int = 86) -> bytes:
    raw = base64.b64decode(b64)
    im = Image.open(BytesIO(raw))
    if im.mode not in ('RGB', 'RGBA'): im = im.convert('RGB')
    else: im = im.convert('RGB')
    w, h = im.size
    if w > max_w:
        new_h = int(h * (max_w / w))
        im = im.resize((max_w, new_h), Image.LANCZOS)
    buf = BytesIO()
    im.save(buf, format='JPEG', quality=quality, optimize=True, progressive=True)
    return buf.getvalue()

def _jpeg_from_bytes(raw: bytes, max_w: int = 1200, quality: int = 86) -> bytes:
    im = Image.open(BytesIO(raw))
    im = im.convert('RGB')
    w, h = im.size
    if w > max_w:
        new_h = int(h * (max_w / w))
        im = im.resize((max_w, new_h), Image.LANCZOS)
    buf = BytesIO()
    im.save(buf, format='JPEG', quality=quality, optimize=True, progressive=True)
    return buf.getvalue()

@app.get('/og_img/{mueble_id}.jpg')
async def og_img(request: Request, mueble_id: int):
    async with app.state.pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT imagen_base64, imagen_url FROM imagenes_muebles
            WHERE mueble_id=$1
            ORDER BY es_principal DESC, id ASC
            LIMIT 1
        """, mueble_id)
    if not row:
        return Response(status_code=404)
    try:
        if row['imagen_url']:
            req = urllib.request.Request(
                row['imagen_url'],
                headers={'User-Agent': 'inventario-el-jueves/1.0'},
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                src = r.read()
            jpeg = _jpeg_from_bytes(src)
        else:
            jpeg = _jpeg_from_b64(row['imagen_base64'])
    except Exception as e:
        print(f"[og_img] ERROR mid={mueble_id}: {type(e).__name__}: {e}")
        return Response(status_code=500)
    headers = {'Cache-Control': 'public, max-age=2592000', 'Content-Type': 'image/jpeg'}
    return Response(content=jpeg, media_type='image/jpeg', headers=headers)

# === Service Worker en raíz ===
@app.get('/service-worker.js', include_in_schema=False)
def _root_sw():
    path = os.path.join('static', 'service-worker.js')
    if os.path.exists(path):
        return FileResponse(path, media_type='text/javascript; charset=utf-8')
    return Response('// no sw', media_type='text/javascript')

# === Iconos / manifest en raíz ===
@app.get('/apple-touch-icon.png', include_in_schema=False)
def _root_apple_icon():
    return FileResponse(os.path.join('static', 'images', 'apple-touch-icon.png'),
                        media_type='image/png')

@app.get('/favicon.ico', include_in_schema=False)
def _root_favicon():
    return FileResponse(os.path.join('static', 'images', 'icon-192.png'),
                        media_type='image/png')

@app.get('/manifest.webmanifest', include_in_schema=False)
def _root_manifest():
    return FileResponse(
        os.path.join('static', 'manifest.json'),
        media_type='application/manifest+json; charset=utf-8'
    )

@app.get('/health')
async def health():
    try:
        async with app.state.pool.acquire() as conn:
            await conn.execute('SELECT 1')
        return JSONResponse({'status': 'ok', 'db': 'ok'})
    except Exception:
        return JSONResponse({'status': 'error', 'db': 'error'}, status_code=503)

# === Página SSR con OG: /o/{id} ===
@app.get('/o/{mid}')
async def og_page(request: Request, mid: int):
    async with app.state.pool.acquire() as conn:
        m = await conn.fetchrow('SELECT * FROM muebles WHERE id=$1', mid)
    if not m:
        return Response('Not found', status_code=status.HTTP_404_NOT_FOUND, media_type='text/plain')

    origin = _origin_from(request)  # <- usa el mismo host de la petición
    title = f"{m['nombre']} · {_fmt_precio(m.get('precio'))}"
    desc = (m.get('descripcion') or '').strip()
    if len(desc) > 200: desc = desc[:200] + '…'

    img_url = f"{origin}/og_img/{mid}.jpg"
    human_url = f"{origin}/?id={mid}"
    full_url = str(request.url)

    ua = (request.headers.get('user-agent') or '').lower()
    is_bot = any(k in ua for k in (
        'whatsapp','facebookexternalhit','twitterbot','telegram','discordbot','slackbot','linkedinbot'
    ))
    if not is_bot:
        return RedirectResponse(url=human_url, status_code=302)

    html_doc = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>{_esc(title)}</title>

<link rel="manifest" href="/manifest.webmanifest?v=20250906">
<link rel="apple-touch-icon" sizes="180x180" href="/muebles-app/images/apple-touch-icon.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Inventario El Jueves">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#023e8a">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, user-scalable=no">

<meta property="og:title" content="{_esc(title)}">
<meta property="og:description" content="{_esc(desc)}">
<meta property="og:image" content="{img_url}">
<meta property="og:image:secure_url" content="{img_url}">
<meta property="og:image:type" content="image/jpeg">
<meta property="og:url" content="{_esc(full_url)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Inventario de Antigüedades El Jueves">

<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{_esc(title)}">
<meta name="twitter:description" content="{_esc(desc)}">
<meta name="twitter:image" content="{img_url}">
</head>
<body>
<p>Vista previa para compartir <a href="{human_url}">{_esc(title)}</a>.</p>
</body>
</html>"""
    return Response(html_doc, media_type='text/html; charset=utf-8')

# ---------- DB helpers ----------
async def query_tipos():
    async with app.state.pool.acquire() as conn:
        rows = await conn.fetch("SELECT DISTINCT tipo FROM muebles ORDER BY tipo")
    existentes = [r['tipo'] for r in rows if r['tipo']]
    return ['Todos'] + sorted(set(existentes + TIPOS))

async def query_muebles(vendidos:bool|None, tienda:str|None, tipo:str|None,
                        nombre_like:str|None, orden:str, limit:int|None=None, offset:int|None=None,
                        precio_min:float|None=None, precio_max:float|None=None):
    where, params = [], []
    if vendidos is not None:
        where.append(f'vendido = ${len(params)+1}'); params.append(vendidos)
    if tienda and tienda!='Todas':
        where.append(f'tienda = ${len(params)+1}'); params.append(tienda)
    if tipo and tipo != 'Todos':
        where.append(f'tipo = ${len(params)+1}'); params.append(tipo)
    if nombre_like:
        where.append(f'LOWER(nombre) LIKE ${len(params)+1}'); params.append(f'%{nombre_like.lower()}%')
    if precio_min is not None:
        where.append(f'precio >= ${len(params)+1}'); params.append(precio_min)
    if precio_max is not None:
        where.append(f'precio <= ${len(params)+1}'); params.append(precio_max)
    order_sql = {'Más reciente':'id DESC','Más antiguo':'id ASC','Precio ↑':'precio ASC NULLS LAST','Precio ↓':'precio DESC NULLS LAST'}.get(orden,'id DESC')
    where_sql = ' AND '.join(where) if where else 'TRUE'
    sql = f"SELECT * FROM muebles WHERE {where_sql} ORDER BY {order_sql}"
    if limit is not None:
        sql += f" LIMIT ${len(params)+1}"; params.append(limit)
    if offset is not None:
        sql += f" OFFSET ${len(params)+1}"; params.append(offset)
    async with app.state.pool.acquire() as conn:
        return await conn.fetch(sql, *params)

async def get_mueble(mueble_id: int):
    async with app.state.pool.acquire() as conn:
        m = await conn.fetchrow('SELECT * FROM muebles WHERE id=$1', mueble_id)
        imgs = await conn.fetch(
            'SELECT id, es_principal FROM imagenes_muebles WHERE mueble_id=$1 ORDER BY es_principal DESC, id ASC',
            mueble_id
        )
    return m, imgs

async def add_mueble(data: dict, images_bytes: list[bytes]) -> int:
    async with app.state.pool.acquire() as conn:
        async with conn.transaction():
            # Obtener un ID válido aunque la columna id no tenga DEFAULT
            seq = await conn.fetchval("SELECT pg_get_serial_sequence('muebles','id')")
            if seq:
                mid = await conn.fetchval("SELECT nextval($1::regclass)", seq)
            else:
                # Fallback seguro: bloquea la tabla y calcula MAX(id)+1
                await conn.execute("LOCK TABLE muebles IN SHARE ROW EXCLUSIVE MODE")
                mid = await conn.fetchval("SELECT COALESCE(MAX(id), 0) + 1 FROM muebles")

            # Insertar el mueble
            await conn.execute(
                """
                INSERT INTO muebles (id, nombre, precio, descripcion, tienda, tipo, fecha,
                    alto,largo,fondo,diametro,diametro_base,diametro_boca,alto_respaldo,alto_asiento,ancho,vendido)
                VALUES ($1,$2,$3,$4,$5,$6, NOW(),
                        $7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
                """,
                mid,
                data.get('nombre'), data.get('precio'), data.get('descripcion'),
                data.get('tienda'), data.get('tipo'),
                data.get('alto'), data.get('largo'), data.get('fondo'),
                data.get('diametro'), data.get('diametro_base'), data.get('diametro_boca'),
                data.get('alto_respaldo'), data.get('alto_asiento'), data.get('ancho'),
                False,
            )

            # Procesar imágenes con manejo de errores
            for i, b in enumerate(images_bytes):
                try:
                    b_webp = to_img_bytes(b)
                    if not R2_ENABLED:
                        b64 = base64.b64encode(b_webp).decode('utf-8')
                        await conn.execute(
                            'INSERT INTO imagenes_muebles (mueble_id, imagen_base64, es_principal) VALUES ($1,$2,$3)',
                            mid, b64, (i == 0)
                        )
                        continue
                    img_id = await conn.fetchval(
                        'INSERT INTO imagenes_muebles (mueble_id, imagen_base64, es_principal) '
                        'VALUES ($1, NULL, $2) RETURNING id',
                        mid, (i == 0)
                    )
                    key = f'{mid}_{img_id}.webp'
                    try:
                        _r2_put(key, b_webp, 'image/webp')
                    except Exception as r2err:
                        await conn.execute('DELETE FROM imagenes_muebles WHERE id=$1', img_id)
                        print(f"Error subiendo imagen {i} a R2: {r2err} — fila {img_id} eliminada")
                        continue
                    url = f'{R2_PUBLIC_URL}/{key}'
                    await conn.execute(
                        'UPDATE imagenes_muebles SET imagen_url=$1 WHERE id=$2', url, img_id
                    )
                except Exception as e:
                    print(f"Error procesando imagen {i}: {str(e)}")
                    continue
    return mid


async def update_mueble(mueble_id: int, data: dict):
    fields = ['nombre','precio','descripcion','tienda','tipo','vendido','alto','largo','fondo',
              'diametro','diametro_base','diametro_boca','alto_respaldo','alto_asiento','ancho']
    sets, params = [], []
    for f in fields:
        if f in data:
            sets.append(f'{f}=${len(params)+1}'); params.append(data[f])
    if not sets:
        return
    params.append(mueble_id)
    sql = f'UPDATE muebles SET {", ".join(sets)} WHERE id=${len(params)}'
    async with app.state.pool.acquire() as conn:
        await conn.execute(sql, *params)

async def set_vendido(mueble_id: int, vendido: bool):
    async with app.state.pool.acquire() as conn:
        await conn.execute('UPDATE muebles SET vendido=$1 WHERE id=$2', vendido, mueble_id)

async def delete_mueble(mueble_id: int):
    async with app.state.pool.acquire() as conn:
        urls = await conn.fetch(
            'SELECT imagen_url FROM imagenes_muebles '
            'WHERE mueble_id=$1 AND imagen_url IS NOT NULL',
            mueble_id
        )
        async with conn.transaction():
            await conn.execute('DELETE FROM imagenes_muebles WHERE mueble_id=$1', mueble_id)
            await conn.execute('DELETE FROM muebles WHERE id=$1', mueble_id)
    for r in urls:
        key = _r2_key_from_url(r['imagen_url'])
        if key:
            _r2_delete(key)

async def add_image(mueble_id: int, content_bytes: bytes, will_be_principal: bool = False):
    b_webp = to_img_bytes(content_bytes)
    async with app.state.pool.acquire() as conn:
        if not R2_ENABLED:
            b64 = base64.b64encode(b_webp).decode('utf-8')
            await conn.execute(
                'INSERT INTO imagenes_muebles (mueble_id, imagen_base64, es_principal) VALUES ($1,$2,$3)',
                mueble_id, b64, will_be_principal
            )
            return
        img_id = await conn.fetchval(
            'INSERT INTO imagenes_muebles (mueble_id, imagen_base64, es_principal) '
            'VALUES ($1, NULL, $2) RETURNING id',
            mueble_id, will_be_principal
        )
        key = f'{mueble_id}_{img_id}.webp'
        try:
            _r2_put(key, b_webp, 'image/webp')
        except Exception as e:
            await conn.execute('DELETE FROM imagenes_muebles WHERE id=$1', img_id)
            print(f"[add_image] R2 upload fallo, fila {img_id} borrada: {e}")
            raise
        url = f'{R2_PUBLIC_URL}/{key}'
        await conn.execute(
            'UPDATE imagenes_muebles SET imagen_url=$1 WHERE id=$2', url, img_id
        )

async def delete_image(img_id: int):
    async with app.state.pool.acquire() as conn:
        url = await conn.fetchval(
            'SELECT imagen_url FROM imagenes_muebles WHERE id=$1', img_id
        )
        await conn.execute('DELETE FROM imagenes_muebles WHERE id=$1', img_id)
    key = _r2_key_from_url(url)
    if key:
        _r2_delete(key)

async def set_principal_image(mueble_id: int, img_id: int):
    async with app.state.pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute('UPDATE imagenes_muebles SET es_principal=FALSE WHERE mueble_id=$1', mueble_id)
            await conn.execute('UPDATE imagenes_muebles SET es_principal=TRUE WHERE id=$1 AND mueble_id=$2',
                               img_id, mueble_id)

# ---------- Diálogos admin (completos, traídos del código antiguo) ----------

def dialog_add_mueble(on_saved=None):
    with ui.dialog() as d, ui.card().classes('w-[min(92vw,900px)] max-h-[92vh] overflow-auto p-4'):
        ui.label('Añadir nueva antigüedad').classes('text-xl font-bold')

        paso_label = ui.label('Paso 1 de 3 — Foto').style(
            'color:var(--brass-deep); font-family:"Inter Tight",sans-serif; '
            'font-size:.78rem; letter-spacing:.14em; text-transform:uppercase; '
            'margin:6px 0 14px 0;'
        )

        new_bytes: list[bytes] = []

        # ---------- PASO 1: Foto + IA ----------
        paso1 = ui.column().classes('w-full')
        with paso1:
            ui.label('Sube una o varias imágenes. La primera será la principal.').classes('mb-2')

            async def on_upload(e):
                content = await _read_upload_bytes(e)
                if not content:
                    ui.notify('No pude leer la imagen subida (vacía). Vuelve a intentarlo.', type='warning')
                    print('[upload] archivo vacío; event=',
                          {k: type(getattr(e, k)).__name__ for k in dir(e) if not k.startswith('_')})
                    return
                new_bytes.append(content)
                ui.notify(f'Imagen subida ({len(new_bytes)})')
                print(f'[upload] recibidos {len(content)} bytes; total acumuladas={len(new_bytes)}')
                if HAS_GEMINI:
                    btn_ai.set_visibility(True)

            with ui.row().classes('w-full gap-4 flex-wrap'):
                (ui.upload(multiple=True, on_upload=on_upload, auto_upload=True)
                   .props('accept="image/*" capture="environment" max-file-size="52428800" label="📷 Hacer foto"')
                   .classes('flex-1'))
                (ui.upload(multiple=True, on_upload=on_upload, auto_upload=True)
                   .props('accept="image/*" max-file-size="52428800" label="🖼 Elegir de galería"')
                   .classes('flex-1'))

            with ui.row().classes('items-center gap-3 mt-3'):
                btn_ai = ui.button('✨ Analizar con IA', on_click=lambda: analizar()).props('color=primary')
                spinner_ai = ui.spinner(size='lg')
            btn_ai.set_visibility(False)
            spinner_ai.set_visibility(False)
            if not HAS_GEMINI:
                ui.label('(IA no disponible: configurar GEMINI_API_KEY)') \
                    .classes('text-xs text-gray-500 mt-1')

        # ---------- PASO 2: Datos ----------
        paso2 = ui.column().classes('w-full')
        with paso2:
            with ui.grid(columns=2).classes('gap-3'):
                nombre = ui.input('Nombre*')
                precio = ui.number(label='Precio (€)*', format='%.2f', min=0)
                tienda = ui.select(['El Rastro', 'Regueros'], value='El Rastro', label='Tienda')
                tipo = ui.select(TIPOS, value='Otro artículo', label='Tipo de mueble')
            descripcion = ui.textarea('Descripción').classes('w-full mt-2')
        paso2.set_visibility(False)

        # ---------- PASO 3: Medidas ----------
        paso3 = ui.column().classes('w-full')
        with paso3:
            ui.label('Medidas (todas opcionales)').classes('mt-2 font-medium')
            with ui.grid(columns=3).classes('gap-2'):
                alto = ui.number(label='Alto (cm)', min=0)
                largo = ui.number(label='Largo (cm)', min=0)
                fondo = ui.number(label='Fondo (cm)', min=0)
                diametro = ui.number(label='Diámetro (cm)', min=0)
                diametro_base = ui.number(label='Ø Base (cm)', min=0)
                diametro_boca = ui.number(label='Ø Boca (cm)', min=0)
                alto_respaldo = ui.number(label='Alto respaldo (cm)', min=0)
                alto_asiento = ui.number(label='Alto asiento (cm)', min=0)
                ancho = ui.number(label='Ancho (cm)', min=0)
        paso3.set_visibility(False)

        # ======= Análisis con IA =======
        async def analizar():
            if not new_bytes:
                ui.notify('Primero sube una imagen', type='warning')
                return
            btn_ai.set_visibility(False)
            spinner_ai.set_visibility(True)
            ui.notify('Analizando imagen…')
            try:
                data = await analyze_image_with_gemini(new_bytes[0])
            finally:
                spinner_ai.set_visibility(False)
                btn_ai.set_visibility(True)
            if not data:
                ui.notify('No pude analizar la imagen', type='warning')
                return
            if data.get('nombre'):
                nombre.value = data['nombre']
            if data.get('tipo'):
                tipo.value = data['tipo']
            if data.get('descripcion'):
                descripcion.value = data['descripcion']
            ui.notify('Datos rellenados por IA', type='positive')
            mostrar(1)

        # ======= Guardar (lógica intacta) =======
        async def guardar(_=None):
            ui.run_javascript('document.activeElement && document.activeElement.blur()')
            await asyncio.sleep(0.05)

            nombre_val = (nombre.value or '').strip() or 'Sin nombre'

            precio_raw = precio.value
            if precio_raw in (None, ''):
                try:
                    precio_raw = (getattr(precio, '_props', {}) or {}).get('modelValue', precio_raw)
                except Exception:
                    pass
            precio_val = _to_float_or_none(precio_raw)
            if precio_val is None:
                precio_val = 0.0

            data = {
                'nombre': nombre_val, 'precio': float(precio_val),
                'descripcion': descripcion.value, 'tienda': tienda.value, 'tipo': tipo.value,
                'alto': _none_if_empty_or_zero(alto.value), 'largo': _none_if_empty_or_zero(largo.value),
                'fondo': _none_if_empty_or_zero(fondo.value), 'diametro': _none_if_empty_or_zero(diametro.value),
                'diametro_base': _none_if_empty_or_zero(diametro_base.value),
                'diametro_boca': _none_if_empty_or_zero(diametro_boca.value),
                'alto_respaldo': _none_if_empty_or_zero(alto_respaldo.value),
                'alto_asiento': _none_if_empty_or_zero(alto_asiento.value),
                'ancho': _none_if_empty_or_zero(ancho.value),
            }

            print(f"[upload debug] files={len(new_bytes)} "
                  f"sizes={[len(b) for b in new_bytes] if new_bytes else []}")

            await add_mueble(data, new_bytes)
            ui.notify('¡Mueble añadido!', type='positive')
            d.close()
            if on_saved:
                await on_saved()
            else:
                ui.run_javascript('location.reload()')

        # ---------- Navegación entre pasos ----------
        estado = {'n': 0}
        pasos = [paso1, paso2, paso3]
        titulos = ['Paso 1 de 3 — Foto', 'Paso 2 de 3 — Datos', 'Paso 3 de 3 — Medidas']

        def mostrar(n: int):
            n = max(0, min(2, n))
            estado['n'] = n
            for i, p in enumerate(pasos):
                p.set_visibility(i == n)
            paso_label.set_text(titulos[n])
            btn_prev.set_visibility(n > 0)
            btn_next.set_visibility(n < 2)
            btn_save.set_visibility(n == 2)

        with ui.row().classes('justify-between items-center mt-4 w-full'):
            ui.button('Cancelar', on_click=d.close).props('flat')
            with ui.row().classes('gap-2'):
                btn_prev = ui.button('Anterior', on_click=lambda: mostrar(estado['n']-1)).props('flat')
                btn_next = ui.button('Siguiente', on_click=lambda: mostrar(estado['n']+1), color='primary')
                btn_save = ui.button('Guardar', on_click=guardar, color='primary')

        btn_prev.set_visibility(False)
        btn_save.set_visibility(False)

    return d


def dialog_edit_mueble(mueble_id: int, on_saved=None):
    with ui.dialog() as d, ui.card().classes('w-[min(92vw,1000px)] max-h-[92vh] overflow-auto p-4'):
        ui.label('Editar mueble').classes('text-xl font-bold')
        cont = ui.column().classes('gap-3')
        async def cargar_datos():
            mueble, _ = await get_mueble(mueble_id)
            cont.clear()
            with cont:
                with ui.grid(columns=2).classes('gap-3'):
                    tienda = ui.select(['El Rastro', 'Regueros'], value=mueble['tienda'], label='Tienda')
                    tipo = ui.select(TIPOS, value=mueble['tipo'] or 'Otro artículo', label='Tipo de mueble')
                    nombre = ui.input('Nombre*', value=mueble['nombre'])
                    precio = ui.number(label='Precio (€)*', value=float(mueble['precio'] or 0), format='%.2f', min=0)
                descripcion = ui.textarea('Descripción', value=mueble.get('descripcion') or '').classes('w-full')
                vendido_sw = ui.switch('Marcar como vendido', value=bool(mueble['vendido']))
                with ui.grid(columns=3).classes('gap-2'):
                    alto = ui.number(label='Alto (cm)', value=mueble.get('alto') or 0)
                    largo = ui.number(label='Largo (cm)', value=mueble.get('largo') or 0)
                    fondo = ui.number(label='Fondo (cm)', value=mueble.get('fondo') or 0)
                    diametro = ui.number(label='Diámetro (cm)', value=mueble.get('diametro') or 0)
                    diametro_base = ui.number(label='Ø Base (cm)', value=mueble.get('diametro_base') or 0)
                    diametro_boca = ui.number(label='Ø Boca (cm)', value=mueble.get('diametro_boca') or 0)
                    alto_respaldo = ui.number(label='Alto respaldo (cm)', value=mueble.get('alto_respaldo') or 0)
                    alto_asiento = ui.number(label='Alto asiento (cm)', value=mueble.get('alto_asiento') or 0)
                    ancho = ui.number(label='Ancho (cm)', value=mueble.get('ancho') or 0)

                # Imágenes existentes
                imgs: list = []
                with ui.expansion('Imágenes', value=True) as img_expansion:
                    img_grid = ui.row().classes('gap-3 flex-wrap')

                async def reload_imgs():
                    nonlocal imgs
                    imgs = await app.state.pool.fetch(
                        'SELECT id, es_principal FROM imagenes_muebles WHERE mueble_id=$1 ORDER BY es_principal DESC, id ASC',
                        mueble_id
                    )
                    img_expansion.text = f'Imágenes ({len(imgs)})'
                    img_grid.clear()
                    with img_grid:
                        for img in imgs:
                            iid = int(img['id'])
                            with ui.column().classes('items-center'):
                                ui.image(f'/img_by_id/{iid}?thumb=1') \
                                    .props('onload="this.dataset.loaded=\'true\'"') \
                                    .classes('thumb-skeleton w-[140px] h-[140px] object-cover rounded')
                                with ui.row().classes('gap-1'):
                                    async def make_principal(_=None, _iid=iid):
                                        await set_principal_image(mueble_id, _iid)
                                        ui.notify('Principal actualizada', type='positive')
                                        await reload_imgs()
                                    ui.button('⭐ Principal', on_click=make_principal).props('flat')
                                    def ask_delete(_=None, _iid=iid):
                                        with ui.dialog() as dd:
                                            with ui.card():
                                                ui.label('¿Eliminar imagen?')
                                                with ui.row().classes('justify-end'):
                                                    ui.button('Cancelar', on_click=dd.close).props('flat')
                                                    async def do_del(_=None):
                                                        await delete_image(_iid)
                                                        dd.close()
                                                        await reload_imgs()
                                                    ui.button('Eliminar', color='negative', on_click=do_del)
                                        dd.open()
                                    ui.button('🗑 Eliminar', color='negative', on_click=ask_delete).props('flat')

                await reload_imgs()

                # Añadir nuevas
                ui.label('Añadir nuevas imágenes').classes('mt-2')
                new_bytes: list[bytes] = []
                async def on_upload(e):
                    content = await _read_upload_bytes(e)
                    new_bytes.append(content)
                    ui.notify(f'Imagen subida ({len(new_bytes)})')
                ui.upload(multiple=True, on_upload=on_upload)
                with ui.row().classes('justify-end mt-3'):
                    ui.button('Cancelar', on_click=d.close).props('flat')
                    async def guardar(_=None):
                        data = {
                            'nombre': nombre.value, 'precio': float(precio.value or 0),
                            'descripcion': descripcion.value, 'tienda': tienda.value, 'tipo': tipo.value,
                            'vendido': bool(vendido_sw.value),
                            'alto': _none_if_empty_or_zero(alto.value), 'largo': _none_if_empty_or_zero(largo.value),
                            'fondo': _none_if_empty_or_zero(fondo.value), 'diametro': _none_if_empty_or_zero(diametro.value),
                            'diametro_base': _none_if_empty_or_zero(diametro_base.value),
                            'diametro_boca': _none_if_empty_or_zero(diametro_boca.value),
                            'alto_respaldo': _none_if_empty_or_zero(alto_respaldo.value),
                            'alto_asiento': _none_if_empty_or_zero(alto_asiento.value),
                            'ancho': _none_if_empty_or_zero(ancho.value),
                        }
                        await update_mueble(mueble_id, data)
                        if new_bytes:
                            first_principal = (len(imgs) == 0)
                            for i, raw in enumerate(new_bytes):
                                await add_image(mueble_id, raw, will_be_principal=(first_principal and i == 0))
                        ui.notify('¡Cambios guardados!', type='positive')
                        d.close()
                        if on_saved:
                            await on_saved()
                        else:
                            ui.run_javascript('location.reload()')
                    ui.button('Guardar', on_click=guardar, color='primary')
        ui.timer(0.05, cargar_datos, once=True)
    return d

# ---------- Listado (diseño + admin) ----------

def _safe(s: str) -> str:
    return html.escape(s or "")

def _kv(label: str, value: str):
    ui.html(
        f'<div class="kv kv-line" style="margin-bottom:16px">'
        f'<strong class="k">{_safe(label)}:</strong>&nbsp;<span class="v">{_safe(value)}</span>'
        f'</div>'
    )

def _kv_attr(label: str, value: str):
    ui.html(
        f'<div class="kv kv-line" style="margin-bottom:16px">'
        f'<strong class="k">{_safe(label)}:</strong>&nbsp;<span class="v">{_safe(value)}</span>'
        f'</div>'
    )

def _kv_desc(value: str):
    ui.html(
        f'<div class="kv kv-desc kv-line" style="margin-bottom:16px">'
        f'<strong class="k">Descripción:</strong>&nbsp;<span class="v">{_safe(value)}</span>'
        f'</div>'
    )

async def pintar_listado(vendidos=False, nombre_like=None, tienda='Todas', tipo='Todos',
                         orden='Más reciente', only_id:int|None=None, limit:int|None=None, offset:int|None=None,
                         base_origin: str | None = None,
                         precio_min:float|None=None, precio_max:float|None=None,
                         on_change=None):
    rows = await query_muebles(vendidos, tienda, tipo, nombre_like, orden, limit, offset,
                               precio_min=precio_min, precio_max=precio_max)
    if only_id is not None:
        rows = [r for r in rows if int(r['id']) == int(only_id)]
    if not rows:
        ui.label('Sin resultados').style('color:#6b7280');  return

    origin = (base_origin or BASE_URL).rstrip('/')

    for m in rows:
        m = dict(m)  # ← importante para poder usar .get()
        mid = int(m['id'])

        card_container = ui.element('div')
        with card_container:
            with ui.card().classes('mueble-card'):
                # ---- Cabecera: título + precio + badge nuevo
                with ui.element('div').classes('mueble-head'):
                    with ui.element('div').style('flex:1 1 auto; min-width:0;'):
                        nombre_html = html.escape(str(m['nombre']))
                        nuevo_html = '<span class="mueble-badge-nuevo">Nuevo</span>' if es_nuevo(m.get('fecha')) else ''
                        ui.html(f'<div class="mueble-title">{nombre_html}{nuevo_html}</div>')
                    ui.html(f'<div class="mueble-price">{html.escape(_fmt_precio(m.get("precio")))}</div>')

                with ui.element('div').classes('card-flex'):
                    # ---- imagen principal + diálogo
                    with ui.element('div').classes('card-main'):
                        with ui.dialog() as dialog:
                            # MISMO comportamiento a pantalla completa, pero ahora el contenedor es relativo
                            with ui.column().style(
                                'align-items:center; justify-content:center; '
                                'width:100vw; height:100vh; position:relative;'
                            ):
                                big = ui.image(f'/img/{mid}?i=0').style(
                                    'max-width:90vw; max-height:90vh; object-fit:contain; '
                                    'border-radius:10px; box-shadow:0 0 20px rgba(0,0,0,.2);'
                                )

                                # Botón de cierre: absoluto dentro del contenedor, notch-safe y con z-index alto
                                ui.button('✕', on_click=dialog.close) \
                                  .props('flat round size=lg aria-label="Cerrar imagen"') \
                                  .classes('absolute') \
                                  .style(
                                      'top:12px; right:12px; '
                                      'top: calc(constant(safe-area-inset-top) + 12px); '
                                      'top: calc(env(safe-area-inset-top) + 12px); '
                                      'right: calc(constant(safe-area-inset-right) + 12px); '
                                      'right: calc(env(safe-area-inset-right) + 12px); '
                                      'z-index:2147483647; background:rgba(255,255,255,.92);'
                                  )

                        def open_with(index:int, big_img=big, mid_val=mid, dlg=dialog):
                            big_img.set_source(f'/img/{mid_val}?i={index}')
                            dlg.open()

                        ui.image(f'/img/{mid}?i=0&thumb=1&v={THUMB_VER}') \
                            .props('loading=lazy alt="Imagen principal" onload="this.dataset.loaded=\'true\'"') \
                            .classes('card-thumb') \
                            .on('click', lambda *_h, h=partial(open_with, 0, big, mid, dialog): h())

                    # ---- DETALLES (sin HTML raw — pares etiqueta/valor seguros)
                    try:
                        with ui.column().classes('card-details').style('gap:0;'):
                            def kv(label: str, value: str):
                                with ui.element('div').classes('kv-row'):
                                    ui.label(label).classes('kv-label')
                                    ui.label(value).classes('kv-value')

                            kv('Tipo', m.get('tipo') or '—')
                            kv('Tienda', m.get('tienda') or '—')
                            kv('Medidas', mostrar_medidas_extendido(m))
                            if m.get('fecha'):
                                kv('Registro', _fmt_fecha(m.get('fecha')))

                            desc = (m.get('descripcion') or '').strip()
                            if desc:
                                if len(desc) > 220:
                                    with ui.element('div').classes('kv-row'):
                                        ui.label('Descripción').classes('kv-label')
                                        ui.label(desc[:220] + '…').classes('kv-value kv-value-desc')
                                    with ui.expansion('Leer descripción completa').classes('editorial-expansion'):
                                        ui.label(desc).classes('kv-value kv-value-desc') \
                                            .style('font-size:17px; line-height:1.55;')
                                else:
                                    with ui.element('div').classes('kv-row'):
                                        ui.label('Descripción').classes('kv-label')
                                        ui.label(desc).classes('kv-value kv-value-desc')

                            # ---- Acciones (WhatsApp + Copiar enlace + admin)
                            share_url = f"{origin}/o/{mid}?v={int(datetime.now().timestamp())}"
                            copy_url = html.escape(f"{origin}/o/{mid}")
                            wa_url = f"https://wa.me/?text={urllib.parse.quote('Mira este mueble: ' + share_url)}"
                            copy_onclick = f"copiarEnlace(this,'{copy_url}')"
                            with ui.element('div').classes('mueble-actions'):
                                ui.html(
                                    f'<a class="btn-whatsapp" href="{html.escape(wa_url)}" '
                                    f'target="_blank" rel="noopener" aria-label="Compartir por WhatsApp">'
                                    f'<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">'
                                    f'<path d="M19.05 4.91A10 10 0 0 0 12.04 2C6.6 2 2.17 6.43 2.17 11.87c0 1.74.46 3.45 1.34 4.95L2.1 22l5.31-1.39a9.85 9.85 0 0 0 4.63 1.18h.01c5.44 0 9.86-4.43 9.86-9.87a9.82 9.82 0 0 0-2.86-7.01zM12.05 20.13h-.01a8.2 8.2 0 0 1-4.18-1.14l-.3-.18-3.15.82.84-3.07-.2-.32a8.18 8.18 0 0 1-1.26-4.37c0-4.53 3.68-8.2 8.21-8.2 2.19 0 4.25.86 5.81 2.41a8.17 8.17 0 0 1 2.4 5.81c0 4.53-3.68 8.2-8.16 8.24zm4.5-6.16c-.25-.13-1.46-.72-1.69-.8-.23-.08-.39-.13-.56.13-.16.25-.64.8-.78.96-.14.16-.29.18-.54.06-.25-.13-1.04-.38-1.98-1.22-.73-.65-1.23-1.46-1.37-1.71-.14-.25-.01-.39.11-.51.11-.11.25-.29.37-.43.13-.14.16-.25.25-.41.08-.16.04-.31-.02-.43-.06-.13-.56-1.35-.77-1.84-.2-.49-.41-.42-.56-.43h-.48c-.16 0-.43.06-.65.31-.23.25-.85.83-.85 2.03 0 1.2.87 2.36.99 2.52.13.16 1.72 2.62 4.16 3.67.58.25 1.04.4 1.39.51.59.19 1.12.16 1.55.1.47-.07 1.46-.6 1.66-1.18.21-.58.21-1.07.14-1.18-.06-.11-.22-.16-.46-.29z"/>'
                                    f'</svg><span>Compartir por WhatsApp</span></a>'
                                    f'<button class="btn-whatsapp" aria-label="Copiar enlace" onclick="{html.escape(copy_onclick)}">'
                                    f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="width:14px;height:14px;flex:0 0 auto">'
                                    f'<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>'
                                    f'<path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>'
                                    f'</svg><span>Copiar enlace</span></button>'
                                )

                                if is_admin():
                                    with ui.element('div').classes('mueble-actions-admin'):
                                        ui.button('Editar', on_click=lambda _mid=mid: dialog_edit_mueble(_mid, on_saved=on_change).open()) \
                                            .classes('btn-ghost')

                                        def ask_delete_mueble(_=None, _mid=mid, _card=card_container):
                                            with ui.dialog() as dd:
                                                with ui.card():
                                                    ui.label('¿Eliminar este mueble?')
                                                    with ui.row().classes('justify-end'):
                                                        ui.button('Cancelar', on_click=dd.close).props('flat')
                                                        async def do_delete(_=None):
                                                            await delete_mueble(_mid)
                                                            dd.close()
                                                            _card.delete()
                                                        ui.button('Eliminar', color='negative', on_click=do_delete)
                                            dd.open()

                                        ui.button('Vendido', on_click=ask_delete_mueble).classes('btn-ghost')
                                        ui.button('Eliminar', on_click=ask_delete_mueble).classes('btn-ghost btn-ghost-danger')
                    except Exception as e:
                        print(f"[details err id={mid}]: {e}")

            # ---- MÁS IMÁGENES
            try:
                async with app.state.pool.acquire() as conn:
                    total_imgs = await conn.fetchval('SELECT COUNT(*) FROM imagenes_muebles WHERE mueble_id=$1', mid)
            except Exception as e:
                print(f"[imgcount err id={mid}]: {e}")
                total_imgs = 0

            if total_imgs and total_imgs > 1:
                with ui.expansion(f"Ver más imágenes ({total_imgs-1})").classes('editorial-expansion'):
                    with ui.row().style('gap:12px; flex-wrap:wrap;'):
                        for i in range(1, total_imgs):
                            ui.image(f'/img/{mid}?i={i}&thumb=1&v={THUMB_VER}') \
                              .props('loading=lazy alt="Miniatura" onload="this.dataset.loaded=\'true\'"') \
                              .classes('thumb-skeleton') \
                              .style('width:120px; height:120px; object-fit:cover; border-radius:3px; cursor:zoom-in; box-shadow:0 4px 12px -6px rgba(2,31,77,.35);') \
                              .on('click', lambda *_h, h=partial(open_with, i, big, mid, dialog): h())



# ---------- Página ----------
LOGO_URL = "/muebles-app/images/icon-192.png"

@ui.page('/')
async def index(request: Request):
    ui.add_head_html(HEAD_HTML)
    # IMPORTANTE: desregistrar cualquier SW previo y limpiar cachés para cortar bucles de recarga
    ui.run_javascript("""
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.getRegistrations().then(rs => rs.forEach(r => r.unregister()));
      if (window.caches) { caches.keys().then(keys => keys.forEach(k => caches.delete(k))); }
    }
    """)

    base_origin = _origin_from(request)  # <- mismo host

    # Si llega con ?id=... renderiza ese mueble
    item_id = request.query_params.get('id')
    if item_id:
        try: mid = int(item_id)
        except: mid = None
        cont = ui.column()
        list_unsold = ui.column(); list_sold = ui.column()
        with cont:
            await pintar_listado(vendidos=None, nombre_like=None, tienda=None, tipo=None,
                                 orden='Más reciente', only_id=mid if item_id else None,
                                 base_origin=base_origin)
        return

    # Drawer admin
    with ui.left_drawer(value=False) as drawer:
        drawer.props('overlay')
        ui.button(on_click=lambda: drawer.set_value(False)) \
            .props('icon=close flat round size=md aria-label="Cerrar panel"') \
            .classes('safe-top-right bg-white')

        ui.label('Panel').classes('text-h6 q-pa-md')

        if not is_admin():
            pwd = ui.input('Contraseña admin', password=True, password_toggle_button=True)
            def do_login():
                if _verify_admin(pwd.value):
                    app.storage.user['is_admin'] = True
                    ui.notify('Acceso concedido', type='positive')
                    drawer.set_value(False); ui.run_javascript('location.reload()')
                else:
                    ui.notify('Contraseña incorrecta', type='negative')
            ui.button('Entrar', on_click=do_login)
            ui.label('Inicia sesión como admin para ver estadísticas').classes('text-caption text-grey-7 q-mt-md')
        else:
            ui.label('Modo administrador').classes('text-green-700')
            def do_logout():
                app.storage.user.pop('is_admin', None)
                ui.notify('Sesión cerrada', type='info')
                drawer.set_value(False); ui.run_javascript('location.reload()')
            ui.button('Salir', on_click=do_logout).props('flat')

            # Stats + CSV + Alta
            stats_box = ui.column().classes('q-mt-md')
            async def cargar_stats():
                stats_box.clear()
                async with app.state.pool.acquire() as conn:
                    en_rastro = await conn.fetchval("SELECT COUNT(*) FROM muebles WHERE vendido=FALSE AND tienda='El Rastro'")
                    en_regueros = await conn.fetchval("SELECT COUNT(*) FROM muebles WHERE vendido=FALSE AND tienda='Regueros'")
                    vendidos = await conn.fetchval("SELECT COUNT(*) FROM muebles WHERE vendido=TRUE")
                with stats_box:
                    ui.label('📊 Estadísticas').classes('text-subtitle1 q-mb-sm')
                    ui.label(f"🔵 En El Rastro: {en_rastro}")
                    ui.label(f"🔴 En Regueros: {en_regueros}")
                    ui.label(f"💰 Vendidos: {vendidos}")

                    async def export_csv(_=None):
                        rows = await query_muebles(
                            vendidos=None,
                            tienda=filtro_tienda.value,
                            tipo=filtro_tipo.value,
                            nombre_like=filtro_nombre.value,
                            orden=orden.value,
                        )
                        if not rows:
                            ui.notify('No hay datos', type='warning'); return
                        df = pd.DataFrame([dict(r) for r in rows])
                        csv = df.to_csv(index=False)
                        ui.download(bytes(csv, 'utf-8'), filename='muebles.csv')
                    ui.button('⬇️ Exportar inventario CSV', on_click=export_csv).classes('q-mt-sm')

                    ui.button('➕ Añadir nueva antigüedad', on_click=lambda: dialog_add_mueble(on_saved=refrescar).open()).classes('q-mt-sm')

            ui.timer(0.1, lambda: asyncio.create_task(cargar_stats()), once=True)

    ui.button(on_click=drawer.toggle) \
        .props('icon=menu flat round size=md dense aria-label="Abrir panel"') \
        .classes('safe-top-left hamburger-btn')



    with ui.element('div').style('min-height:100vh; width:100%; background:#E6F0F8; display:flex; flex-direction:column; align-items:center;'):
        with ui.element('div').style('width:100%; max-width:1200px; padding:0 16px;'):
            with ui.element('div').classes('site-header'):
                with ui.element('div').classes('site-header-inner'):
                    ui.image(LOGO_URL).classes('site-header-logo')
                    ui.html('<span class="site-header-ornament">❦</span>')
                    ui.label('Inventario de Antigüedades El Jueves').classes('site-header-title')

            if is_admin():
                ui.button('Añadir nueva antigüedad', on_click=lambda: dialog_add_mueble(on_saved=refrescar).open()) \
                    .classes('btn-primary-editorial q-mb-md')

            with ui.element('details').classes('filtros-panel').props('open'):
                with ui.element('summary').classes('filtros-summary'):
                    ui.label('🔍 Filtrar el inventario')
                with ui.row().style('gap:18px; flex-wrap:wrap;'):
                    filtro_nombre = ui.input('Buscar por nombre').props('clearable').style('min-width:200px;')
                    filtro_tienda = ui.select(['Todas','El Rastro','Regueros'], value='Todas', label='Filtrar por tienda').style('min-width:180px;')
                    filtro_tipo = ui.select(['Todos'], value='Todos', label='Filtrar por tipo').style('min-width:180px;')
                    orden = ui.select(['Más reciente','Más antiguo','Precio ↑','Precio ↓'], value='Más reciente', label='Ordenar por').style('min-width:180px;')
                    filtro_precio_min = ui.number(label='Precio mín (€)', min=0, format='%.2f').props('clearable').style('min-width:140px;')
                    filtro_precio_max = ui.number(label='Precio máx (€)', min=0, format='%.2f').props('clearable').style('min-width:140px;')

            # --- cargar opciones de tipo sin timer y forzar update ---
            try:
                filtro_tipo.options = await query_tipos()
                filtro_tipo.update()
            except Exception as e:
                ui.notify(f'No se pudieron cargar los tipos: {e}', type='warning')

            cont = ui.column()
            list_unsold = ui.column()
            list_sold = ui.column()

            def reset_offsets():
                app.storage.user['off_unsold'] = 0
                app.storage.user['off_sold'] = 0

            def _f(v):
                return float(v) if v not in (None, '') else None

            async def cargar_tanda(vendidos_flag: bool, container: ui.element, off_key: str):
                offset = int(app.storage.user.get(off_key, 0))
                pmin, pmax = _f(filtro_precio_min.value), _f(filtro_precio_max.value)
                rows = await query_muebles(vendidos=vendidos_flag, tienda=filtro_tienda.value,
                                           tipo=filtro_tipo.value, nombre_like=filtro_nombre.value,
                                           orden=orden.value, limit=PAGE_SIZE+1, offset=offset,
                                           precio_min=pmin, precio_max=pmax)
                has_more = len(rows) > PAGE_SIZE
                with container:
                    await pintar_listado(vendidos=vendidos_flag, nombre_like=filtro_nombre.value,
                                         tienda=filtro_tienda.value, tipo=filtro_tipo.value, orden=orden.value,
                                         limit=PAGE_SIZE, offset=offset, base_origin=base_origin,
                                         precio_min=pmin, precio_max=pmax,
                                         on_change=refrescar)
                app.storage.user[off_key] = offset + PAGE_SIZE
                return has_more

            async def refrescar(*_):
                reset_offsets()
                cont.clear(); list_unsold.clear(); list_sold.clear()
                with cont:
                    with list_unsold:
                        has_more_unsold = await cargar_tanda(False, list_unsold, 'off_unsold')
                        if has_more_unsold:
                            row_more = ui.row().style('justify-content:center; margin:12px 0;')
                            def more_unsold():
                                async def go():
                                    row_more.clear()
                                    hm = await cargar_tanda(False, list_unsold, 'off_unsold')
                                    if hm:
                                        with row_more: ui.button('Cargar más', on_click=more_unsold)
                                asyncio.create_task(go())
                            with row_more: ui.button('Cargar más', on_click=more_unsold)

                    if is_admin():
                        ui.separator()
                        with list_sold:
                            has_more_sold = await cargar_tanda(True, list_sold, 'off_sold')
                            if has_more_sold:
                                row_more_s = ui.row().style('justify-content:center; margin:12px 0;')
                                def more_sold():
                                    async def go():
                                        row_more_s.clear()
                                        hm = await cargar_tanda(True, list_sold, 'off_sold')
                                        if hm:
                                            with row_more_s: ui.button('Cargar más', on_click=more_sold)
                                    asyncio.create_task(go())
                                with row_more_s: ui.button('Cargar más', on_click=more_sold)

            filtro_nombre.on('blur', lambda e: asyncio.create_task(refrescar()))
            filtro_tienda.on('blur', lambda e: asyncio.create_task(refrescar()))
            filtro_tipo.on('blur', lambda e: asyncio.create_task(refrescar()))
            orden.on('blur', lambda e: asyncio.create_task(refrescar()))
            filtro_precio_min.on('blur', lambda e: asyncio.create_task(refrescar()))
            filtro_precio_max.on('blur', lambda e: asyncio.create_task(refrescar()))
            ui.timer(0.05, lambda: asyncio.create_task(refrescar()), once=True)

# ---------- Run ----------
if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title="Inventario El Jueves",
        storage_secret=os.getenv('STORAGE_SECRET', 'cambia_esto'),
        host='0.0.0.0',
        port=int(os.getenv('PORT', '8080')),
        reload=os.getenv('RELOAD', '0') == '1',
    )





































































