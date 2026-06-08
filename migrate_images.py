"""
Migra imágenes desde imagenes_muebles.imagen_base64 a Cloudflare R2.

Uso:
    python migrate_images.py --dry-run     # solo lista, no sube nada
    python migrate_images.py               # sube a R2 (no toca la BD)

Por seguridad este script JAMÁS modifica la BD. Solo lee y sube a R2.
La columna imagen_url se añadirá y se rellenará en la Fase 2.
"""

import os
import sys
import base64
import asyncio
from io import BytesIO

import asyncpg
import boto3
from botocore.config import Config
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

# ---- Config ----
DB_DSN = (
    f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
    f"@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    f"?sslmode=require"
)
R2_ACCESS_KEY_ID     = os.getenv('R2_ACCESS_KEY_ID')
R2_SECRET_ACCESS_KEY = os.getenv('R2_SECRET_ACCESS_KEY')
R2_BUCKET_NAME       = os.getenv('R2_BUCKET_NAME')
R2_ENDPOINT_URL      = os.getenv('R2_ENDPOINT_URL')
R2_PUBLIC_URL        = os.getenv('R2_PUBLIC_URL', '').rstrip('/')

DRY_RUN = '--dry-run' in sys.argv


def detect_mime(data: bytes) -> tuple[str, str]:
    """Devuelve (extension, mime) leyendo los primeros bytes con PIL."""
    try:
        fmt = (Image.open(BytesIO(data)).format or '').upper()
    except Exception:
        fmt = ''
    if fmt == 'WEBP':
        return 'webp', 'image/webp'
    if fmt == 'JPEG':
        return 'jpg', 'image/jpeg'
    if fmt == 'PNG':
        return 'png', 'image/png'
    return 'bin', 'application/octet-stream'


def make_r2_client():
    return boto3.client(
        's3',
        endpoint_url=R2_ENDPOINT_URL,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        config=Config(signature_version='s3v4'),
        region_name='auto',
    )


async def main():
    mode = 'DRY-RUN (sin subir)' if DRY_RUN else 'REAL (subiendo a R2)'
    print(f"[migrate] modo: {mode}")
    print(f"[migrate] bucket: {R2_BUCKET_NAME}")
    print(f"[migrate] endpoint: {R2_ENDPOINT_URL}")

    missing = [k for k in (
        'POSTGRES_USER','POSTGRES_PASSWORD','POSTGRES_HOST','POSTGRES_PORT','POSTGRES_DB',
        'R2_ACCESS_KEY_ID','R2_SECRET_ACCESS_KEY','R2_BUCKET_NAME','R2_ENDPOINT_URL',
    ) if not os.getenv(k)]
    if missing:
        print(f"[migrate] ERROR: faltan variables de entorno: {missing}")
        sys.exit(1)

    s3 = None if DRY_RUN else make_r2_client()

    conn = await asyncpg.connect(dsn=DB_DSN)
    try:
        rows = await conn.fetch(
            'SELECT id, mueble_id, LENGTH(imagen_base64) AS b64_len '
            'FROM imagenes_muebles ORDER BY mueble_id, id'
        )
        print(f"[migrate] total imágenes en BD: {len(rows)}")

        ok, skipped, failed = 0, 0, 0
        for i, r in enumerate(rows, 1):
            img_id   = int(r['id'])
            mueble_id = int(r['mueble_id'])
            b64_len  = int(r['b64_len'] or 0)
            if b64_len == 0:
                print(f"  [{i}/{len(rows)}] img_id={img_id} mueble={mueble_id} VACÍA — skip")
                skipped += 1
                continue

            # Leer y decodificar solo el contenido necesario
            b64 = await conn.fetchval(
                'SELECT imagen_base64 FROM imagenes_muebles WHERE id=$1', img_id
            )
            try:
                data = base64.b64decode(b64)
            except Exception as ex:
                print(f"  [{i}/{len(rows)}] img_id={img_id} ERROR decode base64: {ex}")
                failed += 1
                continue

            ext, mime = detect_mime(data)
            key = f"{mueble_id}_{img_id}.{ext}"
            size_kb = len(data) / 1024
            url = f"{R2_PUBLIC_URL}/{key}" if R2_PUBLIC_URL else f"(bucket://{R2_BUCKET_NAME}/{key})"

            if DRY_RUN:
                print(f"  [{i}/{len(rows)}] would upload key={key} mime={mime} {size_kb:.1f} KB → {url}")
                ok += 1
                continue

            try:
                s3.put_object(
                    Bucket=R2_BUCKET_NAME,
                    Key=key,
                    Body=data,
                    ContentType=mime,
                    CacheControl='public, max-age=31536000, immutable',
                )
                print(f"  [{i}/{len(rows)}] uploaded {key} ({size_kb:.1f} KB) → {url}")
                ok += 1
            except Exception as ex:
                print(f"  [{i}/{len(rows)}] FAIL {key}: {ex}")
                failed += 1

        print(f"\n[migrate] resumen: ok={ok} skipped={skipped} failed={failed} total={len(rows)}")
        print("[migrate] LA BD NO HA SIDO MODIFICADA.")
    finally:
        await conn.close()


if __name__ == '__main__':
    asyncio.run(main())
