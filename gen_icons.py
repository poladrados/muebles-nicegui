import os
from PIL import Image, UnidentifiedImageError

OUT = 'static/images'
os.makedirs(OUT, exist_ok=True)

# Probamos varias fuentes (primero el logo, luego tu 192)
CANDIDATES = [
    'logo-tienda.png',
    os.path.join(OUT, 'icon-192.png'),
    '/c/Users/Pol/muebles-app/images/web-app-manifest-192x192.png',
]

def open_first_ok(paths):
    for p in paths:
        try:
            im = Image.open(p).convert('RGBA')
            print(f'Usando como fuente: {p} ({im.width}x{im.height})')
            return im
        except (FileNotFoundError, UnidentifiedImageError, OSError):
            continue
    return None

def center_square(im, size, inner_ratio=1.0):
    bg = Image.new('RGBA', (size, size), (0,0,0,0))
    inner = int(size * inner_ratio)
    r = min(inner / im.width, inner / im.height)
    new = im.resize((int(im.width*r), int(im.height*r)), Image.LANCZOS)
    x = (size - new.width)//2
    y = (size - new.height)//2
    bg.paste(new, (x, y), new)
    return bg

def main():
    im = open_first_ok(CANDIDATES)
    if not im:
        raise SystemExit('ERROR: No he podido abrir ninguna imagen fuente (logo-tienda.png ni icon-192).')

    # normales
    center_square(im, 192, 1.0).save(os.path.join(OUT, 'icon-192.png'), 'PNG')
    center_square(im, 512, 1.0).save(os.path.join(OUT, 'icon-512.png'), 'PNG')

    # maskable (con aire para Android)
    center_square(im, 192, 0.78).save(os.path.join(OUT, 'maskable-192.png'), 'PNG')
    center_square(im, 512, 0.78).save(os.path.join(OUT, 'maskable-512.png'), 'PNG')

    # iOS apple-touch
    center_square(im, 180, 1.0).save(os.path.join(OUT, 'apple-touch-icon.png'), 'PNG')

    print('OK -> static/images/: icon-192.png, icon-512.png, maskable-192.png, maskable-512.png, apple-touch-icon.png')

if __name__ == '__main__':
    main()
