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

## 🔄 Fase 5 — Frontend Next.js (en curso)
- [x] Endpoints API REST en FastAPI
- [x] Columna destacado + toggle admin
- [ ] Proyecto Next.js en Vercel
- [ ] Home (5B)
- [ ] Catálogo: categorías → listado → ficha (5C)
- [ ] Buscador + asesor IA (5D)
- [ ] PWA + dominio personalizado (5D)
