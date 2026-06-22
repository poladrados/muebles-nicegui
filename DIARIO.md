# Diario de Desarrollo

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
- Resolver problema 'State' object has no attribute 'pool' detectado en producción (causa pendiente de confirmar por logs de Railway)

---

## 10 junio 2026
### Sesión de trabajo — Documentación y optimización de almacenamiento

**Completado:**
- `FUNCIONALIDADES.md` y `DISEÑO_TECNICO.md` creados
- Auditoría de almacenamiento Cloudflare R2 confirmada
- Script `cleanup_local_images.py` — 420 archivos locales eliminados, 26.72 MB liberados
- Módulo `asesor_estilo.py` integrado con Gemini 2.5 Flash, ruta `/asesor` añadida
