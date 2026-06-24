Eres un ingeniero senior trabajando en una aplicación Python en producción.

## Qué es la app

Inventario de antigüedades "El Jueves". Stack: NiceGUI + FastAPI + asyncpg +
PostgreSQL, desplegada en Railway. Un solo archivo `main.py` concentra toda la
lógica: rutas FastAPI, componentes NiceGUI, procesamiento de imágenes,
autenticación y PWA. El frontend público (actualmente el mismo NiceGUI) migrará
próximamente a Next.js en Vercel.

## Estado actual — todo esto ya está hecho y funcionando

### Imágenes
- Almacenadas en Cloudflare R2, bucket `inventario-el-jueves`
- URL pública base: `pub-322ccea60cbc4785b3a59681ebaaa14e.r2.dev`
- Rutas de servicio: `/img/{mueble_id}` e `/img_by_id/{img_id}` hacen redirect
  307 a R2
- La columna `imagen_base64` fue eliminada de código y BD

### Base de datos
- Tabla `muebles`: columna `id` con `GENERATED ALWAYS AS IDENTITY`
- Tabla `imagenes_muebles`: columna `imagen_url TEXT`, sin `imagen_base64`
- 13 categorías: Aparadores, Arquitectura, Armarios, Asientos, Bibliotecas,
  Cómodas, Consolas, Deco, Escritorios, Espejos, Mesas, Mesas auxiliares,
  Vajillas
- 2 tiendas: El Rastro, Regueros

### IA
- Gemini 2.5 Flash integrado en dos sitios:
  - Wizard de añadir mueble: analiza foto y rellena campos automáticamente
  - Chatbot Asesor de Estilo en `/asesor` (módulo `asesor_estilo.py`)

### PWA
- Banner de instalación iOS (`ios_installer.py`)
- Manifest y Service Worker en `static/`
- `start_url=/`

### API REST pública
- `GET /api/categorias` — lista las 13 categorías
- `GET /api/muebles` — listado con filtros categoria, precio, paginación
- `GET /api/mueble/{id}` — ficha completa con array de imágenes
- `GET /api/muebles/destacados` — máximo 4 muebles con destacado=TRUE

### Destacados
- Columna `destacado BOOLEAN NOT NULL DEFAULT FALSE` en tabla `muebles`
- Toggle en admin NiceGUI con límite de 4 y mensaje de error explicativo

## Arquitectura de ficheros relevantes

- `main.py` — toda la app (NiceGUI + FastAPI, ~900 líneas)
- `asesor_estilo.py` — chatbot Asesor de Estilo con Gemini
- `ios_installer.py` — banner PWA iOS
- `migrate_images.py` — script de migración a R2 (ya ejecutado, no tocar)
- `static/` — assets PWA (iconos, manifest, service worker)
- `requirements.txt` — dependencias (sin versiones fijadas)

## Variables de entorno

- `POSTGRES_*` — conexión a BD
- `R2_*` — Cloudflare R2 (access key, secret, bucket, public URL)
- `GEMINI_API_KEY`
- `STORAGE_SECRET`
- `ADMIN_PASSWORD_HASH`
- `BASE_URL`

## Frontend Next.js — Fase 5 en curso

Repo separado: `github.com/poladrados/el-jueves-web`
Path local: `/Users/pabloadrados/Documents/Proyectos/el-jueves-web`
Stack: Next.js 16.2.9 · React 19 · Tailwind 4 · TypeScript · bun · Vercel
URL producción: https://el-jueves-web.vercel.app

### Ya construido
- Design system Ethereal Dwelling en `globals.css` — `--color-primary: #5b708b` (navy), Libre Caslon Text + Manrope
- `lib/api.ts` — `getCategorias` (1h), `getMuebles` (60s), `getMueble` (60s), `getDestacados` (60s), `formatPrecio`, `formatMedidas`
- `lib/categorias.ts` — mapa `CATEGORIA_IMAGE` (nombre→URL R2), `slugCategoria()`, `nombreDesdeSlug()` (reverse)
- `components/Navbar.tsx` — navy en `/`, blanco en el resto; shadow on scroll
- `components/BottomNav.tsx` — nav inferior móvil con estado activo por pathname
- `app/page.tsx` — home: hero full-bleed, editorial "Piezas Maestras", destacados API, atmósfera, catálogo editorial 6 categorías
- `app/catalogo/page.tsx` — lista vertical de 13 categorías con thumbnails R2, revalida 1h
- `app/catalogo/[categoria]/page.tsx` — grid 2 cols, paginación numérica (12/pág), validación pagina>totalPaginas → notFound()
- `app/catalogo/[categoria]/[id]/page.tsx` — ficha: hero full-width, precio, WhatsApp, compartir, descripción, medidas/tienda, galería
- `app/error.tsx` y `app/catalogo/error.tsx` — error boundaries editoriales con botón Reintentar
- `app/catalogo/[categoria]/loading.tsx` y `app/catalogo/[categoria]/[id]/loading.tsx` — skeletons con animate-pulse

### Estructura de rutas
```
/                                → home (revalida 60s)
/catalogo                        → lista de 13 categorías (revalida 1h)
/catalogo/[categoria]            → listado de muebles por categoría (dinámico)
/catalogo/[categoria]/[id]       → ficha de mueble (dinámico)
```

### Slugs de categorías (URL → nombre API)
`aparadores`, `arquitectura`, `armarios`, `asientos`, `bibliotecas`, `comodas`,
`consolas`, `deco`, `escritorios`, `espejos`, `mesas`, `mesas-auxiliares`, `vajillas`

### Variables de entorno del frontend (en Vercel y `.env.local`)
- `NEXT_PUBLIC_API_URL` = `https://web-production-a1a43.up.railway.app`
- `NEXT_PUBLIC_R2_PUBLIC_URL` = `https://pub-322ccea60cbc4785b3a59681ebaaa14e.r2.dev`
- `NEXT_PUBLIC_BASE_URL` = `https://el-jueves-web.vercel.app`

### Imágenes UI en R2
- `ui/categorias/{nombre}/image000XX.jpeg` — 14 carpetas (una por categoría)
- `ui/hero/image00001.png` — hero home (sala con espejo)
- `ui/hero/image00002.jpeg` — editorial "Piezas Maestras" (armario tallado)
- `ui/hero/image00003.png` a `image00007.png/jpeg` — disponibles, no usadas aún

### WhatsApp de contacto
`+34 699 975 202` → `https://wa.me/34699975202`

### Pendiente
- Buscador + asesor IA (5D)
- PWA + dominio personalizado (5D)

## Reglas de trabajo OBLIGATORIAS

- Nunca hacer commit ni push sin aprobación explícita del usuario
- Mostrar diff antes de aplicar cualquier cambio en el código
- Nunca hardcodear credenciales en comandos — usar siempre variables del `.env`:
  `source .env && python3 -c "..."` o `source .env && psql "postgresql://..."`
- Cambios incrementales, uno a uno, con verificación entre cada uno
- No actuar en producción (BD, Railway, R2) sin confirmación explícita
