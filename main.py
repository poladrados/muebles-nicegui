# main.py — Inventario El Jueves (NiceGUI + asyncpg) 
# PWA fixed: manifest en raíz, origen auto, sin saltos, test /pwa-min, SW sin cachear '/'

from nicegui import ui, app
from fastapi import Response, Request, status
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse, RedirectResponse, HTMLResponse
import asyncpg
import os, base64, urllib.parse, hashlib, hmac, asyncio, html, math
from functools import partial
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime
from PIL import Image
from io import BytesIO

load_dotenv()
PAGE_SIZE = 30
THUMB_VER = "3"  # cache-buster miniaturas
BASE_URL = os.getenv('BASE_URL', 'https://inventarioeljueves.app')

# ---------- helpers ----------
def _esc(s: str) -> str:
    return html.escape(s or '')

def _origin_from(request: Request) -> str:
    """Origen absoluto fiable del host que ha hecho la petición."""
    # request.base_url == "https://host/"  -> quitamos la barra final
    return str(request.base_url).rstrip('/')

# ---------- PWA / static ----------
try:
    app.add_static_files('/muebles-app', 'static')
except Exception:
    pass

ui.add_head_html("""
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
  /* Evitar zoom en inputs iOS */
  input, select, textarea { font-size: 16px !important; }

  /* Modo PWA standalone: respeta safe areas */
  .pwa-standalone body {
    margin: 0;
    padding: env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left);
    overflow: hidden;
  }
  .pwa-standalone header { padding-top: env(safe-area-inset-top); }

  /* iOS: evitar bounce scroll cuando es standalone */
  @media all and (display-mode: standalone) {
    body { -webkit-overflow-scrolling: touch; }
    html, body { overscroll-behavior: none; position: fixed; width: 100%; height: 100%; }
  }

  @media (max-width: 640px) {
    body { -webkit-user-select: none; user-select: none; -webkit-touch-callout: none; -webkit-tap-highlight-color: transparent; }
  }

  /* ====== estilos UI ====== */
  .kv{margin:0;}
  .kv .k, .kv b, .kv strong{font-weight:700 !important; margin-right:6px;}
  .kv-desc .v { font-size: 1.05rem; line-height: 1.5; }
  .kv-attr, .kv-line { padding-bottom: 0 !important; line-height: 1.5; }

  .card-flex { display:flex; gap:24px; align-items:flex-start; flex-wrap:nowrap; }
  .card-main { flex:0 0 auto; width:clamp(280px, 36vw, 520px); }
  .card-details { flex:1 1 320px; min-width:300px; }
  .card-thumb { width:100%; height:240px; object-fit:cover; border-radius:8px; cursor:zoom-in; }

  @media (max-width: 640px) {
    .card-flex { flex-wrap:wrap !important; }
    .card-main { width:100% !important; }
    .card-details { flex:1 1 100% !important; min-width:0 !important; }
    .card-thumb { height:auto !important; aspect-ratio: 4 / 3; }
  }
</style>

<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&display=swap" rel="stylesheet">

<script>
if (window.navigator.standalone === true) {
  document.documentElement.classList.add('pwa-standalone');
}
if ('serviceWorker' in navigator) {
  window.addEventListener('load', function() {
    navigator.serviceWorker.register('/service-worker.js', {
      scope: '/',
      updateViaCache: 'none'
    }).then(function(registration) {
      console.log('SW registered:', registration);
    }).catch(function(err) {
      console.log('SW registration failed:', err);
    });
  });
}
var _paq = window._paq = window._paq || [];
_paq.push(['setCookieDomain', '*.web-production-a1a43.up.railway.app']);
_paq.push(['setDomains', ['*.web-production-a1a43.up.railway.app','*.inventarioeljueves.app']]);
_paq.push(['trackPageView']);
_paq.push(['enableLinkTracking']);
(function() {
  var u='https://webproductiona1a43uprailwayapp.matomo.cloud/';
  _paq.push(['setTrackerUrl', u+'matomo.php']);
  _paq.push(['setSiteId','1']);
  var d=document, g=d.createElement('script'), s=d.getElementsByTagName('script')[0];
  g.async=true; g.src='https://cdn.matomo.cloud/webproductiona1a43uprailwayapp.matomo.cloud/matomo.js';
  s.parentNode.insertBefore(g,s);
})();
window.addEventListener('load', function () {
  var standalone = (window.matchMedia && matchMedia('(display-mode: standalone)').matches) || !!navigator.standalone;
  _paq.push(['trackEvent','PWA','display-mode', standalone ? 'standalone' : 'browser']);
});
(function () {
  var mk = function() {
    var standalone = (window.matchMedia && matchMedia('(display-mode: standalone)').matches) || !!window.navigator.standalone;
    var badge = document.createElement('div');
    badge.textContent = 'standalone: ' + standalone;
    badge.style.cssText = 'position:fixed;bottom:8px;left:8px;background:#111;color:#0f0;padding:6px 8px;font:12px/1.2 monospace;border-radius:6px;z-index:99999';
    document.body.appendChild(badge);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mk); else mk();
})();
</script>
""")

# ---------- DB ----------
DB_DSN = (
    f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
    f"@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}?sslmode=require"
)

@app.on_startup
async def startup():
    app.state.pool = await asyncpg.create_pool(dsn=DB_DSN, min_size=1, max_size=5)
    async with app.state.pool.acquire() as conn:
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_muebles_vendido_tienda ON muebles (vendido, tienda)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_muebles_tipo ON muebles (tipo)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_muebles_lower_nombre ON muebles (LOWER(nombre))")
        # Índice funcional para filtro por tipo case-insensitive + trim
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_muebles_tipo_norm ON muebles ((LOWER(TRIM(tipo))))")

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

def to_webp_bytes(raw: bytes, max_size=800, quality=85) -> bytes:
    im = Image.open(BytesIO(raw))
    if im.mode not in ('RGB','RGBA'):
        im = im.convert('RGB')
    im.thumbnail((max_size,max_size))
    buf=BytesIO(); im.save(buf, format='WEBP', quality=quality, method=6)
    return buf.getvalue()

def es_nuevo(fecha_val)->bool:
    if not fecha_val: return False
    if isinstance(fecha_val, datetime): fecha=fecha_val
    else:
        try: fecha=datetime.fromisoformat(str(fecha_val))
        except: return False
    delta=(datetime.now(fecha.tzinfo)-fecha) if fecha.tzinfo else (datetime.now()-fecha)
    return delta.days <= 1

def _thumb_bytes(src: bytes, px=720)->bytes:
    im = Image.open(BytesIO(src))
    if im.mode not in ('RGB','RGBA'):
        im = im.convert('RGB')
    im.thumbnail((px,px))
    buf=BytesIO(); im.save(buf,'WEBP',quality=92,method=6)
    return buf.getvalue()

def _cache_headers(data: bytes):
    etag = 'W/"%s"' % hashlib.md5(data).hexdigest()
    return {'Cache-Control':'public, max-age=2592000','ETag':etag}, etag

# ----- Formato ES (precio / fecha) -----
import math
def _fmt_precio(p):
    try:
        n = float(p)
    except:
        return f"{p} €"
    if math.isclose(n, round(n), rel_tol=0, abs_tol=1e-6):
        s = f"{int(round(n)):,}".replace(",", ".")
        return f"{s} €"
    else:
        entero = int(n); dec = abs(n - entero)
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

# ---------- Endpoints de imágenes ----------
@app.get('/img/{mueble_id}')
async def img(request: Request, mueble_id:int, i:int=0, thumb:int=0):
    async with app.state.pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT imagen_base64 FROM imagenes_muebles
             WHERE mueble_id=$1
             ORDER BY es_principal DESC, id ASC
             OFFSET $2 LIMIT 1
        """, mueble_id, i)
    if not row: return Response(status_code=404)
    data = base64.b64decode(row['imagen_base64'])
    if thumb==1: data=_thumb_bytes(data,720)
    headers, etag = _cache_headers(data)
    if request.headers.get('if-none-match')==etag:
        return Response(status_code=304, headers=headers)
    return Response(content=data, media_type='image/webp', headers=headers)

@app.get('/img_by_id/{img_id}')
async def img_by_id(request: Request, img_id:int, thumb:int=0):
    async with app.state.pool.acquire() as conn:
        row = await conn.fetchrow('SELECT imagen_base64 FROM imagenes_muebles WHERE id=$1', img_id)
    if not row: return Response(status_code=404)
    data = base64.b64decode(row['imagen_base64'])
    if thumb==1: data=_thumb_bytes(data,720)
    headers, etag = _cache_headers(data)
    if request.headers.get('if-none-match')==etag:
        return Response(status_code=304, headers=headers)
    return Response(content=data, media_type='image/webp', headers=headers)

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

@app.get('/og_img/{mueble_id}.jpg')
async def og_img(request: Request, mueble_id: int):
    async with app.state.pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT imagen_base64 FROM imagenes_muebles
            WHERE mueble_id=$1
            ORDER BY es_principal DESC, id ASC
            LIMIT 1
        """, mueble_id)
    if not row:
        return Response(status_code=404)
    try:
        jpeg = _jpeg_from_b64(row['imagen_base64'])
    except Exception:
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
# === HEAD para raíz y /o/{id} (evita 405 con HEAD) ===
@app.head('/', include_in_schema=False)
def _head_root():
    return Response(status_code=200)

@app.head('/o/{mid}', include_in_schema=False)
def _head_og(mid: int):
    return Response(status_code=200)

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
    """Devuelve SOLO los tipos existentes en DB, sin duplicados ni vacíos."""
    async with app.state.pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT DISTINCT TRIM(tipo) AS tipo
            FROM muebles
            WHERE tipo IS NOT NULL AND TRIM(tipo) <> ''
            ORDER BY 1
        """)
    vistos = []
    seen = set()
    for r in rows:
        t = (r['tipo'] or '').strip()
        k = t.casefold()
        if t and k not in seen:
            vistos.append(t)
            seen.add(k)
    return vistos  # p.ej. ['Armario', 'Mesa', 'Espejo']

async def query_muebles(vendidos:bool|None, tienda:str|None, tipo:str|None,
                        nombre_like:str|None, orden:str, limit:int|None=None, offset:int|None=None):
    where, params = [], []
    if vendidos is not None:
        where.append(f'vendido = ${len(params)+1}'); params.append(vendidos)
    if tienda and tienda!='Todas':
        where.append(f'tienda = ${len(params)+1}'); params.append(tienda)
    # --- Filtro tipo: case-insensitive + TRIM ---
    if tipo and tipo != 'Todos':
        where.append(f'LOWER(TRIM(tipo)) = ${len(params)+1}'); params.append(tipo.strip().lower())
    if nombre_like:
        where.append(f'LOWER(nombre) LIKE ${len(params)+1}'); params.append(f'%{nombre_like.lower()}%')
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
            mid = await conn.fetchval("""
                INSERT INTO muebles (nombre, precio, descripcion, tienda, tipo, fecha,
                    alto,largo,fondo,diametro,diametro_base,diametro_boca,alto_respaldo,alto_asiento,ancho,vendido)
                VALUES ($1,$2,$3,$4,$5, NOW(),
                        $6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
                RETURNING id
            """, data.get('nombre'), data.get('precio'), data.get('descripcion'),
                 data.get('tienda'), data.get('tipo'),
                 data.get('alto'), data.get('largo'), data.get('fondo'),
                 data.get('diametro'), data.get('diametro_base'), data.get('diametro_boca'),
                 data.get('alto_respaldo'), data.get('alto_asiento'), data.get('ancho'),
                 False)
            for i, b in enumerate(images_bytes):
                b_webp = to_webp_bytes(b)
                b64 = base64.b64encode(b_webp).decode('utf-8')
                await conn.execute(
                    'INSERT INTO imagenes_muebles (mueble_id, imagen_base64, es_principal) VALUES ($1,$2,$3)',
                    mid, b64, (i == 0)
                )
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
        async with conn.transaction():
            await conn.execute('DELETE FROM imagenes_muebles WHERE mueble_id=$1', mueble_id)
            await conn.execute('DELETE FROM muebles WHERE id=$1', mueble_id)

async def add_image(mueble_id: int, content_bytes: bytes, will_be_principal: bool = False):
    b_webp = to_webp_bytes(content_bytes)
    b64 = base64.b64encode(b_webp).decode('utf-8')
    async with app.state.pool.acquire() as conn:
        await conn.execute(
            'INSERT INTO imagenes_muebles (mueble_id, imagen_base64, es_principal) VALUES ($1,$2,$3)',
            mueble_id, b64, will_be_principal
        )

async def delete_image(img_id: int):
    async with app.state.pool.acquire() as conn:
        await conn.execute('DELETE FROM imagenes_muebles WHERE id=$1', img_id)

async def set_principal_image(mueble_id: int, img_id: int):
    async with app.state.pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute('UPDATE imagenes_muebles SET es_principal=FALSE WHERE mueble_id=$1', mueble_id)
            await conn.execute('UPDATE imagenes_muebles SET es_principal=TRUE WHERE id=$1 AND mueble_id=$2',
                               img_id, mueble_id)

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
                         base_origin: str | None = None):
    rows = await query_muebles(vendidos, tienda, tipo, nombre_like, orden, limit, offset)
    if only_id is not None:
        rows = [r for r in rows if int(r['id']) == int(only_id)]
    if not rows:
        ui.label('Sin resultados').style('color:#6b7280');  return

    origin = (base_origin or BASE_URL).rstrip('/')

    for m in rows:
        mid = int(m['id'])
        with ui.card().style('width:100%; padding:16px;'):
            with ui.row().style('align-items:center; gap:8px; margin-bottom:8px;'):
                ui.label(str(m['nombre']).upper()).style('font-weight:700; font-size:20px;')
                if es_nuevo(m.get('fecha')):
                    ui.label('🆕 Nuevo').style('color:#16a34a; font-weight:700;')

            with ui.element('div').classes('card-flex'):
                with ui.element('div').classes('card-main'):
                    with ui.dialog() as dialog:
                        with ui.column().style('align-items:center; justify-content:center; width:100vw; height:100vh;'):
                            big = ui.image(f'/img/{mid}?i=0').style('max-width:90vw; max-height:90vh; object-fit:contain; border-radius:10px; box-shadow:0 0 20px rgba(0,0,0,.2);')
                        ui.button('✕', on_click=dialog.close).props('flat round').classes('fixed top-3 right-3').style('background:rgba(255,255,255,.85);')
                    def open_with(index:int, big_img=big, mid_val=mid, dlg=dialog):
                        big_img.set_source(f'/img/{mid_val}?i={index}');  dlg.open()

                    ui.image(f'/img/{mid}?i=0&thumb=1&v={THUMB_VER}')\
                        .props('loading=lazy alt="Imagen principal"')\
                        .classes('card-thumb')\
                        .on('click', lambda *_h, h=partial(open_with, 0, big, mid, dialog): h())

                with ui.element('div').classes('card-details'):
                    _kv_attr('Tipo', _safe(m.get('tipo','')))
                    _kv_attr('Precio', _fmt_precio(m.get('precio')))
                    _kv_attr('Tienda', _safe(m.get('tienda','')))
                    _kv('Medidas', mostrar_medidas_extendido(m))
                    if m.get('fecha'):
                        _kv('Fecha registro', _fmt_fecha(m.get('fecha')))
                    desc = (m.get('descripcion') or '').strip()
                    if desc:
                        if len(desc) > 220:
                            _kv_desc(desc[:220] + '…')
                            with ui.expansion('🔎 Ver más'):
                                ui.label(desc).style('font-size:15px; line-height:1.5;')
                        else:
                            _kv_desc(desc)

                    share_url = f"{origin}/o/{mid}?v={int(datetime.now().timestamp())}"
                    with ui.element('div').classes('kv kv-line').style('margin-bottom:16px;'):
                        ui.link('📱 WhatsApp', f"https://wa.me/?text={urllib.parse.quote('Mira este mueble: ' + share_url)}")

                    if is_admin():
                        with ui.row().style('gap:8px; justify-content:flex-end; margin-top:8px;'):
                            ui.button('✏️ Editar', on_click=lambda _mid=mid: dialog_edit_mueble(_mid).open())

                            async def mark_sold_delete(_=None, _mid=mid):
                                await delete_mueble(_mid); ui.run_javascript('location.reload()')
                            ui.button('✓ Vendido', on_click=mark_sold_delete)

                            def ask_delete_mueble(_=None, _mid=mid):
                                with ui.dialog() as dd:
                                    with ui.card():
                                        ui.label('¿Eliminar este mueble?')
                                        with ui.row().classes('justify-end'):
                                            ui.button('Cancelar', on_click=dd.close).props('flat')
                                            async def do_delete(_=None):
                                                await delete_mueble(_mid); dd.close(); ui.run_javascript('location.reload()')
                                            ui.button('🗑 Eliminar', color='negative', on_click=do_delete)
                                dd.open()
                            ui.button('🗑 Eliminar', color='negative', on_click=ask_delete_mueble)

        async with app.state.pool.acquire() as conn:
            total_imgs = await conn.fetchval('SELECT COUNT(*) FROM imagenes_muebles WHERE mueble_id=$1', mid)
        if total_imgs and total_imgs > 1:
            with ui.expansion(f"📸 Ver más imágenes ({total_imgs-1})"):
                with ui.row().style('gap:12px; flex-wrap:wrap;'):
                    for i in range(1, total_imgs):
                        ui.image(f'/img/{mid}?i={i}&thumb=1&v={THUMB_VER}')\
                          .props('loading=lazy alt="Miniatura"')\
                          .style('width:120px; height:120px; object-fit:cover; border-radius:8px; cursor:zoom-in;')\
                          .on('click', lambda *_h, h=partial(open_with, i, big, mid, dialog): h())

# ---------- Página ----------
LOGO_URL = "/muebles-app/images/icon-192.png"

@ui.page('/')
async def index(request: Request):
    if os.path.exists(os.path.join('static', 'service-worker.js')):
        ui.run_javascript("""
        if ('serviceWorker' in navigator) {
          navigator.serviceWorker.register('/service-worker.js', {scope:'/'}).catch(()=>{});
        }
        """)

    base_origin = _origin_from(request)

    item_id = request.query_params.get('id')
    if item_id:
        try: mid = int(item_id)
        except: mid = None
        cont = ui.column()
        with cont:
            await pintar_listado(vendidos=None, nombre_like=None, tienda=None, tipo=None,
                                 orden='Más reciente', only_id=mid if item_id else None,
                                 base_origin=base_origin)
        return

    with ui.left_drawer(value=False) as drawer:
        drawer.props('overlay')
        ui.button(on_click=lambda: drawer.set_value(False)).props('icon=close flat round').classes('absolute right-2 top-2')
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

            stats_box = ui.column().classes('q-mt-md')
            async def cargar_stats():
                stats_box.clear()
                async with app.state.pool.acquire() as conn:
                    en_rastro = await conn.fetchval("SELECT COUNT(*) FROM muebles WHERE vendido=FALSE AND tienda='El Rastro'")
                    en_regueros = await conn.fetchval("SELECT COUNT(*) FROM muebles WHERE vendido=FALSE AND tienda='Regueros'")
                with stats_box:
                    ui.label('📊 Estadísticas').classes('text-subtitle1 q-mb-sm')
                    ui.label(f"🔵 En El Rastro: {en_rastro}")
                    ui.label(f"🔴 En Regueros: {en_regueros}")

                    async def export_csv(_=None):
                        async with app.state.pool.acquire() as conn:
                            rows = await conn.fetch('SELECT * FROM muebles ORDER BY id')
                        if not rows:
                            ui.notify('No hay datos', type='warning'); return
                        df = pd.DataFrame([dict(r) for r in rows])
                        csv = df.to_csv(index=False)
                        ui.download(bytes(csv, 'utf-8'), filename='muebles.csv')
                    ui.button('⬇️ Exportar inventario CSV', on_click=export_csv).classes('q-mt-sm')

                    ui.button('➕ Añadir nueva antigüedad', on_click=lambda: dialog_add_mueble().open()).classes('q-mt-sm')

            ui.timer(0.1, lambda: asyncio.create_task(cargar_stats()), once=True)

    ui.button(on_click=drawer.toggle).props('icon=menu flat round')\
        .classes('fixed top-2 left-2 z-50 bg-white')

    with ui.element('div').style('min-height:100vh; width:100%; background:#E6F0F8; display:flex; flex-direction:column; align-items:center;'):
        with ui.element('div').style('width:100%; max-width:1200px; padding:0 16px;'):
            with ui.element('div').style('width:100%; background:#fff; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,.1); margin:20px 0;'):
                with ui.element('div').style('display:flex; align-items:center; justify-content:center; gap:12px; text-align:center; padding:10px 24px;'):
                    ui.image(LOGO_URL).style('height:clamp(32px, 4.8vw, 54px); width:auto;')
                    ui.label('Inventario de Antigüedades El Jueves').style(
                        'font-family:"Playfair Display",serif; font-weight:700; letter-spacing:1px; '
                        'color:#023e8a; font-size:clamp(1.4rem, 2.2vw, 2.1rem); line-height:1; margin:0;'
                    )

            if is_admin():
                ui.button('➕ Añadir nueva antigüedad', on_click=lambda: dialog_add_mueble().open()).classes('q-mb-md')

            with ui.row().style('gap:12px; margin-bottom:16px;'):
                filtro_nombre = ui.input('Buscar por nombre').props('clearable')
                filtro_tienda = ui.select(['Todas','El Rastro','Regueros'], value='Todas', label='Filtrar por tienda')
                # SIEMPRE visible con opción 'Todos'
                filtro_tipo = ui.select(['Todos'], value='Todos', label='Filtrar por tipo')
                orden = ui.select(['Más reciente','Más antiguo','Precio ↑','Precio ↓'], value='Más reciente', label='Ordenar por')

            async def init_tipos():
                # Obtener tipos actuales de la DB
                tipos_actuales = await query_tipos()  # p.ej. ['Armario','Mesa','Espejo']
                options = ['Todos'] + [t for t in tipos_actuales if t != 'Todos']
                # Asignar opciones (sin set_options para máxima compatibilidad)
                filtro_tipo.options = options
                try:
                    filtro_tipo.update()
                except Exception:
                    pass
                # Asegurar un valor válido
                if filtro_tipo.value not in options:
                    filtro_tipo.value = 'Todos'
                # Refrescar listado tras cargar los tipos
                await refrescar()

            cont = ui.column()
            list_unsold = ui.column()

            def reset_offsets():
                app.storage.user['off_unsold'] = 0

            # -------- Token de refresco: último gana --------
            def _new_rt():
                """Genera y guarda un 'refresh token' para invalidar renders antiguos."""
                rt = int(app.storage.user.get('rt', 0)) + 1
                app.storage.user['rt'] = rt
                return rt

            def _is_current_rt(rt: int) -> bool:
                return app.storage.user.get('rt') == rt

            async def cargar_tanda(vendidos_flag: bool, container: ui.element, off_key: str, rt: int):
                # Si ya hay un refresco más nuevo, abortamos
                if not _is_current_rt(rt):
                    return False

                offset = int(app.storage.user.get(off_key, 0))
                rows = await query_muebles(vendidos=vendidos_flag, tienda=filtro_tienda.value,
                                           tipo=filtro_tipo.value, nombre_like=filtro_nombre.value,
                                           orden=orden.value, limit=PAGE_SIZE+1, offset=offset)

                # Revalidar token antes de pintar
                if not _is_current_rt(rt):
                    return False

                has_more = len(rows) > PAGE_SIZE
                with container:
                    await pintar_listado(vendidos=vendidos_flag, nombre_like=filtro_nombre.value,
                                         tienda=filtro_tienda.value, tipo=filtro_tipo.value, orden=orden.value,
                                         limit=PAGE_SIZE, offset=offset, base_origin=base_origin)
                app.storage.user[off_key] = offset + PAGE_SIZE
                return has_more

            async def refrescar(*_):
                reset_offsets()
                rt = _new_rt()
                cont.clear(); list_unsold.clear()
                with cont:
                    with list_unsold:
                        has_more_unsold = await cargar_tanda(False, list_unsold, 'off_unsold', rt)
                        if has_more_unsold:
                            row_more = ui.row().style('justify-content:center; margin:12px 0;')
                            def more_unsold():
                                async def go():
                                    row_more.clear()
                                    hm = await cargar_tanda(False, list_unsold, 'off_unsold', rt)
                                    if hm:
                                        with row_more: ui.button('Cargar más', on_click=more_unsold)
                                asyncio.create_task(go())
                            with row_more: ui.button('Cargar más', on_click=more_unsold)

            for comp in (filtro_nombre, filtro_tienda, filtro_tipo, orden):
                comp.on_value_change(lambda e: asyncio.create_task(refrescar()))

            # 1) Pinta listado inicial
            ui.timer(0.05, lambda: asyncio.create_task(refrescar()), once=True)
            # 2) Carga los tipos desde DB y actualiza el select (mantiene visible el control)
            ui.timer(0.1, lambda: asyncio.create_task(init_tipos()), once=True)

# ---------- Run ----------
if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title="Inventario El Jueves",
        storage_secret=os.getenv('STORAGE_SECRET', 'cambia_esto'),
        host='0.0.0.0',
        port=int(os.getenv('PORT', '8080')),
        reload=os.getenv('RELOAD', '0') == '1',
    )

















































































