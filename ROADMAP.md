# Roadmap — Inventario El Jueves

## ✅ Fase 1 — MVP y seguridad (completado)
- Endpoint `/_diag` eliminado
- Debug badges eliminados
- Imágenes migradas a Cloudflare R2 (399 imágenes)
- Schema BD: columna `imagen_url` añadida

## ✅ Fase 2 — Diseño editorial (completado)
- Sistema CSS con variables brass/paper/ink
- Tipografías: Playfair Display, Cormorant Garamond, Inter Tight
- Cards, filtros, botones rediseñados

## ✅ Fase 3 — Funcionalidades (completado)
- Filtro por rango de precio
- Botón copiar enlace
- Wizard añadir mueble (3 pasos)
- Análisis IA con Gemini (foto → rellena campos)
- Chatbot Asesor de Estilo
- Banner instalación PWA iOS
- Eliminar mueble sin recargar página
- Categorías actualizadas (13 categorías nuevas)
- Filtros colapsables en móvil

## ✅ Fase 4 — Deuda técnica (completado)
- Columna `imagen_base64` eliminada del código y de la BD
- Código R2 limpiado: sin ramas fallback base64
- Schema BD: `id` con `GENERATED ALWAYS AS IDENTITY (START WITH 166)`
- `add_mueble` simplificado: `INSERT ... RETURNING id`, sin LOCK TABLE

## ✅ Fase 5A/5B/5C — Frontend Next.js (completado)
- [x] Endpoints API REST en FastAPI
- [x] Columna destacado + toggle admin
- [x] Proyecto Next.js en Vercel — repo `el-jueves-web`, https://el-jueves-web.vercel.app
- [x] Design system Ethereal Dwelling — primary navy #5b708b, Libre Caslon Text + Manrope
- [x] Página de categorías `/catalogo` con imágenes R2 (revalida 1h)
- [x] Listado `/catalogo/[categoria]` — grid 2 cols, paginación numérica, validación de página fuera de rango
- [x] Ficha `/catalogo/[categoria]/[id]` — hero, precio, WhatsApp, compartir, galería
- [x] Home `/` — hero, editorial, destacados API, atmósfera, catálogo editorial 6 categorías
- [x] Error boundaries editoriales (`error.tsx` global + catálogo)
- [x] Loading skeletons con animate-pulse (listado + ficha)
- [x] `getDestacados()` en api.ts, revalidate 60s en getMuebles/getMueble
- [x] `NEXT_PUBLIC_BASE_URL` para URL de compartir
- [x] Navbar navy en home, blanco en el resto

## 🔄 Fase 5D — Pendiente
- [ ] Buscador + asesor IA
- [ ] PWA + dominio personalizado
