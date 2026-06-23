# Diario de Desarrollo

## 23 junio 2026
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
