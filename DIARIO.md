# Diario de Desarrollo

## 23 junio 2026 (continuación)
### Sesión de trabajo — Fase 5B home + pulido general

**Completado:**

- **Home page `app/page.tsx`** — 5 secciones: hero full-bleed (`ui/hero/image00001.png`), editorial "Piezas Maestras" (`ui/hero/image00002.jpeg`, aspect 4/5), destacados desde API (grid 2/4 cols, cards cuadradas), atmósfera (fondo navy, cita), catálogo editorial (6 categorías con thumbnails R2 en grid 1/2/3 cols con overlay).
- **`getDestacados()`** añadida a `lib/api.ts` — `GET /api/muebles/destacados`, revalida 60s.
- **Color primario cambiado** — `--color-primary: #5b708b` (navy) en lugar de `#000000`. Afecta titulares, botones, paginación activa, bordes en todo el sitio.
- **Navbar adaptativa** — navy con texto blanco en `/`, blanco con texto oscuro en el resto (usa `usePathname`).
- **Error boundaries** — `app/error.tsx` y `app/catalogo/error.tsx`: mensaje editorial en español + botón Reintentar, `min-h-[60vh]`.
- **Loading skeletons** — `app/catalogo/[categoria]/loading.tsx` (grid 6 placeholders aspect 4/5) y `app/catalogo/[categoria]/[id]/loading.tsx` (hero + detalles), ambos con `animate-pulse`.
- **Validación paginación** — `notFound()` si `pagina > totalPaginas && data.total > 0` en listado de categoría.
- **`NEXT_PUBLIC_BASE_URL`** — botón Compartir en ficha usa variable de entorno en vez de URL hardcodeada.
- **`revalidate` reducido** — `getMuebles` y `getMueble` de 300s a 60s (piezas únicas que se venden).

**Decisiones tomadas:**
- Solo 2 de las 7 fotos de hero se usan (las más ligeras/adecuadas); las 5 restantes disponibles en R2 para uso futuro.
- La home no tiene botón "Explorar Colección" (eliminado — el hero es suficiente llamada a la acción visual).
- `global-error.tsx` no implementado — `error.tsx` cubre errores de rutas; errores de layout raíz son edge case.

---

## 23 junio 2026
### Sesión de trabajo — Fase 5B: Proyecto Next.js + página de categorías

**Completado:**

- **Repo `el-jueves-web`** clonado desde GitHub, proyecto Next.js inicializado con `create-next-app` (Next.js 16.2.9, React 19, Tailwind 4, TypeScript, App Router, `bun` como gestor de paquetes).
- **Conectado a Vercel** — proyecto `poladrados-projects/el-jueves-web`, URL de producción https://el-jueves-web.vercel.app, GitHub conectado (push a `main` = deploy automático).
- **Variables de entorno en Vercel** — `NEXT_PUBLIC_API_URL` y `NEXT_PUBLIC_R2_PUBLIC_URL` configuradas en production/preview/development.
- **Design system Ethereal Dwelling** portado desde Stitch (proyecto "Remix of Modern Home Decor Catalog", ID: `15823448740352260755`) a `globals.css` con `@theme inline` de Tailwind 4. Fuentes: Libre Caslon Text (serif, titulares) + Manrope (sans, cuerpo).
- **Imágenes de categorías** subidas a R2 en `ui/categorias/{nombre}/image000XX.jpeg` — 14 carpetas. Mapa estático en `lib/categorias.ts` resuelve discrepancias de nombres (arquitectura→arquitecturas, URL-encoding de cómodas y mesas auxiliares).
- **Página `/catalogo`** — server component, lista vertical de categorías con thumbnail de R2, hover con flecha, enlaza a `/catalogo/{slug}`. Revalidación 1h.
- **Componentes compartidos**: `Navbar` (fijo, shadow on scroll) y `BottomNav` (móvil, estado activo por pathname).
- **`next.config.ts`**: `images.remotePatterns` para R2.
- Build limpio sin errores ni warnings.

**Decisiones tomadas:**
- Mapa de categorías→imágenes estático (no derivado algorítmicamente) para manejar limpiamente las inconsistencias entre nombres de API y carpetas de R2.
- Material Symbols vía Google Fonts CDN en el `<head>` del layout raíz.
- `bun` como gestor de paquetes (npm tenía caché con permisos de root rotos).

**Pendiente:**
- Commit y push del proyecto (pendiente aprobación)
- Home page (hero + destacados + categorías preview) — sin fotos de hero todavía

---

### Sesión de trabajo — Fase 5C: Listado y ficha de mueble

**Completado:**

- **`src/lib/api.ts`** ampliado con tipos TypeScript y funciones:
  - `getMuebles(categoria, pagina, limite)` → `GET /api/muebles?categoria=X&pagina=N&limite=12`
  - `getMueble(id)` → `GET /api/mueble/{id}`
  - `formatPrecio(precio)` → `"1.200 €"` con `toLocaleString('es-ES')`
  - `formatMedidas(ancho, alto, fondo)` → `"210 cm alt. · 130 cm anch. · 55 cm fond."`
  - Tipos: `MuebleResumen`, `MuebleDetalle`, `ListadoResponse`
- **`src/lib/categorias.ts`** ampliado con `nombreDesdeSlug(slug)` — reverse map de slug URL a nombre de API, construido automáticamente desde `CATEGORIA_IMAGE`.
- **`/catalogo/[categoria]/page.tsx`** — listado de muebles:
  - Server component, fetchea `/api/muebles?categoria={nombre}`
  - Grid 2 columnas, imagen aspect-[4/5], nombre serif, precio
  - Paginación numérica (12 ítems/página)
  - Breadcrumb ← Catálogo
  - Footer CTA con WhatsApp
- **`/catalogo/[categoria]/[id]/page.tsx`** — ficha de mueble:
  - Server component, fetchea `/api/mueble/{id}`
  - Hero a ancho completo (3/4 móvil, 16/9 desktop)
  - Badge "Pieza única", nombre, precio en grande
  - Botón WhatsApp verde (wa.me/34699975202) con mensaje preformateado
  - Botón Compartir (Web Share API, fallback copia al portapapeles vía script inline)
  - Descripción (si existe)
  - Panel detalles: medidas, categoría, tienda
  - Galería secundaria: resto de imágenes en grid 2 columnas

**Estructura de la API confirmada en esta sesión:**
```
GET /api/muebles → { total, pagina, limite, items: [{id, nombre, categoria, tienda, precio, imagen_url}] }
GET /api/mueble/{id} → { id, nombre, descripcion, categoria, tienda, precio, ancho, alto, fondo, destacado, imagenes[] }
```

**Decisiones tomadas:**
- No hay "Consultar precio" — se muestra el precio real; si es null, se muestra "—"
- Paginación numérica (no "cargar más")
- WhatsApp: número 699975202 (prefijo +34 en la URL)
- Botón Compartir implementado con script vanilla en server component (evita convertir la página entera en client component)
- `imagen_url` en el listado es la primera imagen del mueble (JOIN en la API)
- Las medidas vienen como campos separados `ancho/alto/fondo` (floats, nullable), no como string

**Pendiente:**
- Commit y push de todo (pendiente aprobación)
- Home page

---

### Sesión de trabajo — Fase 5A: API REST + infraestructura destacados

**Completado:**

- **Columna `destacado`** — `ALTER TABLE muebles ADD COLUMN destacado BOOLEAN NOT NULL DEFAULT FALSE` ejecutado en producción. Todos los muebles existentes quedan en FALSE automáticamente.
- **4 endpoints REST públicos** añadidos en `main.py` antes de `ui.run()`:
  - `GET /api/categorias` — lista estática de 13 categorías
  - `GET /api/muebles` — listado con filtros (categoria, precio_min, precio_max, pagina, limite), JOIN con imagenes_muebles para imagen principal
  - `GET /api/mueble/{id}` — ficha completa con array de todas las imágenes y campo `destacado`
  - `GET /api/muebles/destacados` — máximo 4 resultados con `destacado=TRUE AND vendido=FALSE`
  - Todos verificados con curl en local: respuestas correctas, paginación funcional, URLs de R2 en imagen_url
- **Toggle Destacado en admin** — switch en cada card del listado (`pintar_listado`), visible solo para admins. Consulta COUNT en BD al activar; si ya hay 4 destacados muestra notificación de error y revierte el switch sin tocar la BD. Actualización reactiva sin `location.reload()`.

**Decisiones tomadas:**
- `/api/muebles/destacados` definido antes de `/api/mueble/{id}` en el código para evitar que FastAPI interprete "destacados" como un entero en el path param
- `e.sender` en el handler del switch para evitar problemas de closure en el loop de cards
- Límite de 4 destacados consultado siempre en BD, nunca en estado local

**Pendiente (Fase 5B):**
- Commit de toda la Fase 5A (pendiente aprobación)
- Crear proyecto Next.js en Vercel
- Home con diseño Stitch

---

## 22 junio 2026
### Sesión de trabajo — Deuda técnica (Fase 4)

**Completado:**

- **Fix bug editar mueble en móvil** — backdrops huérfanos bloqueaban el botón Editar, overflow hidden en el dialog
- **Filtros colapsables en móvil** — MutationObserver + CSS media query, colapsados por defecto en pantallas pequeñas
- **Migración categorías** — 13 categorías nuevas, SQL ejecutado en producción
- **Limpieza tipos corruptos en BD** — C¢moda, Otro art¡culo normalizados
- **Eliminación columna `imagen_base64`** — verificado 0 filas no nulas, código limpiado en 5 puntos (SELECTs, INSERTs, ramas fallback), `ALTER TABLE imagenes_muebles DROP COLUMN imagen_base64` ejecutado en producción
- **Schema BD: `id` con `GENERATED ALWAYS AS IDENTITY`** — MAX(id)=165, secuencia arranca en 166, `ALTER TABLE muebles ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (START WITH 166)` ejecutado en producción
- **Código `add_mueble` simplificado** — eliminado LOCK TABLE + MAX(id)+1 + nextval manual; ahora usa `INSERT ... RETURNING id` en una sola sentencia

**Decisiones tomadas:**
- Frontend público migrará a Next.js en Vercel (HTML/JS puro descartado)
- Admin NiceGUI se mantiene sin cambios
- `GENERATED ALWAYS AS IDENTITY` elegido sobre `BY DEFAULT` para mayor seguridad (rechaza IDs explícitos)
- El ALTER TABLE en BD se ejecutó antes del deploy del código nuevo — ventana segura porque la secuencia no se usa hasta que el nuevo código llega

**Commits de esta sesión:**
- `7295fa7` fix: prevent orphan dialog backdrops blocking Editar button on mobile
- `9a41113` refactor: remove imagen_base64 fallback - R2 is now the only image store
- `a7567f7` refactor: use GENERATED ALWAYS AS IDENTITY for muebles.id + clean up manual ID generation

**Pendiente para próxima sesión:**
- Fase 5: endpoints API REST en FastAPI para el frontend Next.js
- Crear proyecto Next.js en Vercel
- Resuelto: error 'State' object has no attribute 'pool' causado por contraseña de BD incorrecta en Railway tras el reset de credenciales. Corregido actualizando POSTGRES_PASSWORD en variables de entorno de Railway.

---

## 10 junio 2026
### Sesión de trabajo — Documentación y optimización de almacenamiento

**Completado:**
- `FUNCIONALIDADES.md` y `DISEÑO_TECNICO.md` creados
- Auditoría de almacenamiento Cloudflare R2 confirmada
- Script `cleanup_local_images.py` — 420 archivos locales eliminados, 26.72 MB liberados
- Módulo `asesor_estilo.py` integrado con Gemini 2.5 Flash, ruta `/asesor` añadida
