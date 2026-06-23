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

## Próximo trabajo — Fase 5B: Frontend Next.js

La API REST ya está lista. Siguiente paso: crear el proyecto Next.js en Vercel
que la consuma.

- Crear proyecto Next.js en Vercel
- Home con diseño Stitch
- Catálogo: categorías → listado → ficha (5C)
- Buscador + asesor IA (5D)
- PWA + dominio personalizado (5D)

## Reglas de trabajo OBLIGATORIAS

- Nunca hacer commit ni push sin aprobación explícita del usuario
- Mostrar diff antes de aplicar cualquier cambio en el código
- Nunca hardcodear credenciales en comandos — usar siempre variables del `.env`:
  `source .env && python3 -c "..."` o `source .env && psql "postgresql://..."`
- Cambios incrementales, uno a uno, con verificación entre cada uno
- No actuar en producción (BD, Railway, R2) sin confirmación explícita
