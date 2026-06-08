Eres un ingeniero senior revisando y mejorando una aplicación Python en producción.

## Contexto del proyecto
App de inventario de antigüedades ("Inventario El Jueves") construida con NiceGUI + FastAPI + asyncpg + PostgreSQL, desplegada en Railway. Un solo archivo `main.py` de ~900 líneas hace todo: rutas FastAPI, lógica de BD, procesamiento de imágenes, componentes UI, autenticación y PWA.

## Problemas identificados (en orden de prioridad)

### 🔴 CRÍTICO — Hacer primero
1. **Endpoint `/_diag` expuesto sin autenticación** — expone host, nombre de BD, usuario y estructura a cualquiera que conozca la ruta. Eliminarlo o protegerlo con la misma auth de admin que ya existe.
2. **Debug badge hardcodeado en HEAD_HTML** — el badge verde "standalone: true/false" está visible para todos los usuarios en producción. Eliminarlo.

### 🟠 IMPORTANTE — Hacer después
3. **Imágenes almacenadas en base64 en PostgreSQL** — cada imagen ocupa ~33% más espacio, los backups son enormes, y el pool de conexiones se satura. Migrar a almacenamiento en disco local (Railway volume) o Cloudflare R2/S3. Guardar solo la ruta/URL en la BD. Mantener compatibilidad con las imágenes ya existentes en BD durante la transición.
4. **IDs sin SERIAL/IDENTITY en la tabla `muebles`** — el código actual hace LOCK TABLE + MAX(id)+1 para generar IDs, lo que es frágil bajo concurrencia. Generar un script de migración SQL para añadir GENERATED ALWAYS AS IDENTITY a la columna id.

### 🟡 DEUDA TÉCNICA — Hacer al final
5. **Separar `main.py`** en módulos: `db.py`, `auth.py`, `images.py`, `routes.py`, `pages/index.py`
6. **Estado de paginación en `app.storage.user`** — reemplazar por variables locales de la función de página
7. **`ui.run_javascript('location.reload()')` × 10** — reemplazar por actualizaciones reactivas de componentes NiceGUI donde sea posible
8. **Imports duplicados** — `from PIL import Image, features`, `import math`, `from datetime import datetime` aparecen dos veces
9. **`_kv` y `_kv_attr`** son idénticas — eliminar la redundante
10. **Cientos de líneas vacías al final del fichero** — limpiar

## Instrucciones de trabajo
- Empieza SOLO por los puntos 🔴 CRÍTICOS (1 y 2). No toques nada más hasta que yo confirme.
- Antes de cada cambio, muéstrame exactamente qué vas a modificar y espera mi confirmación.
- No rompas la funcionalidad existente. La app está en producción.
- Cuando termines los críticos, para y dime qué hiciste para que yo pueda revisar y confirmar antes de continuar.
- No hagas `git push` en ningún momento. Yo controlo cuándo se despliega.