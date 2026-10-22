#!/usr/bin/env python3
"""Buscar, bajar y preparar ilustraciones de colecciones abiertas.

Capa 1 del sistema de láminas (ilustración principal). Todo es gratuito:
APIs públicas sin clave y procesamiento local.

    python3 herramientas/imagenes.py buscar "cow lithograph" [--fuentes commons,openverse,archive,met] [-n 10]
    python3 herramientas/imagenes.py bajar archive bigglecowbook00bigg/n73 --slug vaca-ayrshire-1898
    python3 herramientas/imagenes.py bajar commons "File:Cow female black white.jpg" --slug vaca-holando
    python3 herramientas/imagenes.py bajar met 12345 --slug ...
    python3 herramientas/imagenes.py bajar openverse <uuid> --slug ...
    python3 herramientas/imagenes.py preparar vaca-ayrshire-1898 --rotar -90 --recorte 380,0,3200,1950 --fondo birefnet-general --niveles
    python3 herramientas/imagenes.py ficha vaca-ayrshire-1898
    python3 herramientas/imagenes.py grilla vaca-ayrshire-1898 [--zona 2000,0,2820,800]

Cada imagen vive en imagenes/<slug>/:
    ficha.json     de dónde salió, autor, fecha, licencia, atribución y qué se le hizo
    maestra.jpg    la ilustración preparada (fondo blanco, niveles corregidos)
    mascara.png    la silueta (si se quitó el fondo)
    silueta.svg    la silueta vectorizada, para esquemas
El original sin tocar queda en cache/imagenes/<slug>/ (no se versiona).

Licencias: `bajar` solo acepta dominio público, CC0, CC BY y CC BY-SA. Las
licencias NC o ND, o una licencia desconocida, se rechazan salvo con
--aceptar-licencia (y entonces quedan marcadas en la ficha).

Quitar el fondo usa rembg (pip install "rembg[cpu]"), que baja el modelo de
los releases de GitHub del proyecto la primera vez. birefnet-general (MIT,
~1 GB) da el mejor recorte; isnet-general-use (~180 MB) es la opción liviana.
No usar el modelo por defecto de rembg (bria-rmbg): su licencia no es libre.
"""

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIR_IMAGENES = RAIZ / 'imagenes'
DIR_CACHE = RAIZ / 'cache' / 'imagenes'
UA = 'para-imprimir/0.2 (https://github.com/bruneskycoder/para-imprimir)'
HOY = dt.date.today().isoformat()

LIBRES = [
    (r'public ?domain|dominio p[uú]blico|pdm|no restrictions|no known (copyright )?restrictions|unaware of any copyright', 'Dominio público'),
    (r'cc0', 'CC0'),
    (r'cc[ -]?by[ -]?sa', 'CC BY-SA'),
    (r'cc[ -]?by(?![ -]?(nc|nd|sa))', 'CC BY'),
]
NO_LIBRES = r'\b(nc|nd)\b|non-?commercial|no ?deriv|all rights reserved'


# ---------------------------------------------------------------- red

def pedir(url, params=None, json_=True, intentos=5):
    if params:
        url += ('&' if '?' in url else '?') + urllib.parse.urlencode(params, doseq=True)
    for i in range(intentos):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                datos = r.read()
            return json.loads(datos) if json_ else datos
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and i < intentos - 1:
                espera = int(e.headers.get('Retry-After') or 0) or 15 * (i + 1)
                print(f'  (límite de la API, espero {espera} s)', file=sys.stderr)
                time.sleep(espera)
                continue
            raise
    raise RuntimeError(f'sin respuesta: {url}')


def limpiar(html):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', str(html or ''))).strip()


def clasificar(texto):
    """Devuelve (licencia normalizada, es_libre)."""
    t = (texto or '').lower()
    if re.search(NO_LIBRES, t):
        return texto, False
    for patron, nombre in LIBRES:
        if re.search(patron, t):
            return nombre, True
    return texto or 'desconocida', False


# ---------------------------------------------------------------- fuentes

def buscar_commons(q, n):
    d = pedir('https://commons.wikimedia.org/w/api.php', {
        'action': 'query', 'generator': 'search', 'gsrsearch': f'{q} filetype:bitmap', 'gsrnamespace': 6,
        'gsrlimit': n, 'prop': 'imageinfo', 'iiprop': 'size|extmetadata',
        'iiextmetadatafilter': 'LicenseShortName|Artist|DateTimeOriginal', 'format': 'json', 'formatversion': 2})
    for p in sorted(d.get('query', {}).get('pages', []), key=lambda p: p.get('index', 0)):
        ii = p['imageinfo'][0]
        m = ii.get('extmetadata', {})
        yield {'id': p['title'], 'titulo': p['title'][5:], 'ancho': ii['width'], 'alto': ii['height'],
               'licencia': m.get('LicenseShortName', {}).get('value', '?'),
               'autor': limpiar(m.get('Artist', {}).get('value', ''))}


# Wikimedia frena la descarga de originales desde servidores en la nube y pide
# usar miniaturas de tamaño estándar. 1920 px alcanzan para ~20 cm a 250 ppp.
ANCHOS_COMMONS = (3840, 1920, 1280, 960)


def bajar_commons(titulo):
    base = {'action': 'query', 'titles': titulo, 'prop': 'imageinfo', 'iiprop': 'url|size|extmetadata',
            'format': 'json', 'formatversion': 2}
    ii = pedir('https://commons.wikimedia.org/w/api.php', base)['query']['pages'][0]['imageinfo'][0]
    ancho = next((a for a in ANCHOS_COMMONS if a < ii['width']), None)
    # Si el original es chico, la miniatura estándar perdería resolución (1277 px → 960):
    # se intenta el original y solo si Commons lo niega se usa la miniatura
    if ancho and ii['width'] <= 2500:
        try:
            pedir(ii['url'], json_=False, intentos=1)
            ancho = None
        except Exception:
            pass
    if ancho:
        mini = pedir('https://commons.wikimedia.org/w/api.php', {**base, 'iiurlwidth': ancho})
        ii['url_bajada'] = mini['query']['pages'][0]['imageinfo'][0]['thumburl']
    m = {k: limpiar(v.get('value')) for k, v in ii.get('extmetadata', {}).items()}
    return {
        'titulo': m.get('ObjectName') or titulo[5:], 'autor': m.get('Artist', ''),
        'fecha': m.get('DateTimeOriginal', ''), 'fuente': 'Wikimedia Commons',
        'pagina': ii.get('descriptionurl', ''), 'archivo': ii.get('url_bajada', ii['url']),
        'original_px': [ii['width'], ii['height']],
        'licencia_texto': m.get('LicenseShortName', ''), 'licencia_url': m.get('LicenseUrl', ''),
        'credito': m.get('Credit', ''), 'descripcion': m.get('ImageDescription', '')[:500],
    }


def buscar_openverse(q, n):
    d = pedir('https://api.openverse.org/v1/images/', {'q': q, 'page_size': min(n, 20), 'license': 'cc0,pdm,by,by-sa'})
    for r in d.get('results', []):
        yield {'id': r['id'], 'titulo': r.get('title', ''), 'ancho': r.get('width'), 'alto': r.get('height'),
               'licencia': f"cc {r['license']} {r.get('license_version') or ''}".strip(),
               'autor': r.get('creator') or '', 'origen': r.get('source')}


def bajar_openverse(uid):
    r = pedir(f'https://api.openverse.org/v1/images/{uid}/')
    return {
        'titulo': r.get('title', ''), 'autor': r.get('creator') or '', 'fecha': '',
        'fuente': f"Openverse ({r.get('source')})", 'pagina': r.get('foreign_landing_url', ''),
        'archivo': r['url'], 'licencia_texto': f"cc {r['license']} {r.get('license_version') or ''}",
        'licencia_url': r.get('license_url', ''), 'credito': r.get('attribution', ''), 'descripcion': '',
    }


def buscar_archive(q, n):
    # Libros escaneados anteriores a 1931: dominio público en EE. UU.
    d = pedir('https://archive.org/advancedsearch.php', {
        'q': f'(title:({q}) OR subject:({q})) AND mediatype:texts AND year:[1500 TO 1930]',
        'fl[]': ['identifier', 'title', 'year'], 'rows': n, 'output': 'json'})
    for doc in d['response']['docs']:
        anio = str(doc.get('year', ''))
        yield {'id': doc['identifier'], 'titulo': doc.get('title', ''), 'ancho': '', 'alto': '',
               'licencia': f'dominio público (EE. UU., {anio})', 'autor': anio}


def bajar_archive(ref):
    ident, _, pagina = ref.partition('/')
    m = pedir(f'https://archive.org/metadata/{ident}')['metadata']
    anio = int(re.findall(r'\d{4}', str(m.get('date', '9999')))[0])
    estado = m.get('possible-copyright-status', '') or m.get('rights', '')
    if anio < 1931:
        estado = f'Dominio público en EE. UU. (publicado en {anio}). {estado}'.strip()
    return {
        'titulo': m.get('title', ident), 'autor': m.get('creator', ''), 'fecha': str(m.get('date', '')),
        'fuente': f"Internet Archive ({m.get('contributor', '')})".replace(' ()', ''),
        'pagina': f'https://archive.org/details/{ident}/page/{pagina}' if pagina else f'https://archive.org/details/{ident}',
        'archivo': f'https://archive.org/download/{ident}/page/{pagina}.jpg' if pagina else '',
        'licencia_texto': estado, 'licencia_url': '', 'credito': m.get('contributor', ''), 'descripcion': '',
    }


def buscar_met(q, n):
    d = pedir('https://collectionapi.metmuseum.org/public/collection/v1.1/search',
              {'q': q, 'hasImages': 'true', 'isPublicDomain': 'true', 'limit': n})
    for oid in (d.get('objectIDs') or [])[:n]:
        o = pedir(f'https://collectionapi.metmuseum.org/public/collection/v1/objects/{oid}')
        yield {'id': oid, 'titulo': o.get('title', ''), 'ancho': '', 'alto': '',
               'licencia': 'CC0' if o.get('isPublicDomain') else 'no libre',
               'autor': f"{o.get('artistDisplayName', '')} {o.get('objectDate', '')}".strip()}


def bajar_met(oid):
    o = pedir(f'https://collectionapi.metmuseum.org/public/collection/v1/objects/{oid}')
    return {
        'titulo': o.get('title', ''), 'autor': o.get('artistDisplayName', ''), 'fecha': o.get('objectDate', ''),
        'fuente': 'The Metropolitan Museum of Art', 'pagina': o.get('objectURL', ''), 'archivo': o.get('primaryImage', ''),
        'licencia_texto': 'CC0' if o.get('isPublicDomain') else 'no es de dominio público',
        'licencia_url': 'https://creativecommons.org/publicdomain/zero/1.0/', 'credito': o.get('creditLine', ''),
        'descripcion': o.get('medium', ''),
    }


FUENTES = {
    'commons': (buscar_commons, bajar_commons),
    'openverse': (buscar_openverse, bajar_openverse),
    'archive': (buscar_archive, bajar_archive),
    'met': (buscar_met, bajar_met),
}


# ---------------------------------------------------------------- comandos

def cmd_buscar(a):
    for nombre in a.fuentes.split(','):
        print(f'\n== {nombre}')
        try:
            for r in FUENTES[nombre][0](a.consulta, a.n):
                lic, libre = clasificar(str(r['licencia']))
                marca = '·' if libre else '✗'
                tam = f"{r['ancho']}×{r['alto']}" if r['ancho'] else ''
                print(f"  {marca} {lic[:18]:18} {tam:>11}  {str(r['titulo'])[:70]}")
                print(f"      id: {r['id']}   {str(r.get('autor', ''))[:60]}")
        except Exception as e:  # una fuente caída no frena las demás
            print(f'  (falló: {e})')
    print('\n· licencia libre   ✗ licencia no libre o desconocida (revisar antes de usar)')


def ficha_de(slug):
    return DIR_IMAGENES / slug / 'ficha.json'


def cmd_bajar(a):
    datos = FUENTES[a.fuente][1](a.ref)
    lic, libre = clasificar(datos['licencia_texto'])
    if not libre and not a.aceptar_licencia:
        sys.exit(f"Licencia no libre o desconocida: «{datos['licencia_texto']}». "
                 'Revisala en la página de la obra y, si corresponde, repetí con --aceptar-licencia.')
    if not datos['archivo']:
        sys.exit('La fuente no devolvió un archivo descargable (¿falta el número de página?).')
    crudo = pedir(datos['archivo'], json_=False)
    ext = Path(urllib.parse.urlparse(datos['archivo']).path).suffix.lower() or '.jpg'
    cache = DIR_CACHE / a.slug
    cache.mkdir(parents=True, exist_ok=True)
    original = cache / f'original{ext}'
    original.write_bytes(crudo)
    ficha = {
        'slug': a.slug, **datos, 'licencia': lic, 'licencia_libre': libre,
        'referencia': f'{a.fuente}:{a.ref}', 'consultado': HOY,
        'original': str(original.relative_to(RAIZ)), 'sha256_original': hashlib.sha256(crudo).hexdigest(),
        'preparado': None,
    }
    # Al volver a bajar la misma obra, el crédito escrito a mano para la lámina se conserva
    if ficha_de(a.slug).exists():
        anterior = json.loads(ficha_de(a.slug).read_text())
        if anterior.get('referencia') == ficha['referencia'] and 'credito_lamina' in anterior:
            ficha['credito_lamina'] = anterior['credito_lamina']
    ficha_de(a.slug).parent.mkdir(parents=True, exist_ok=True)
    ficha_de(a.slug).write_text(json.dumps(ficha, ensure_ascii=False, indent=2))
    print(f'Bajado: {original.relative_to(RAIZ)} ({len(crudo) // 1024} KB) · licencia: {lic}')
    print(f'Ficha: {ficha_de(a.slug).relative_to(RAIZ)}')


def cmd_preparar(a):
    import numpy as np
    from PIL import Image

    ficha = json.loads(ficha_de(a.slug).read_text())
    im = Image.open(RAIZ / ficha['original']).convert('RGB')
    if a.rotar:
        im = im.rotate(a.rotar, expand=True)
    if a.recorte:
        im = im.crop(tuple(int(v) for v in a.recorte.split(',')))
    dir_ = DIR_IMAGENES / a.slug

    if a.fondo == 'ninguno':
        mascara = Image.new('L', im.size, 255)
    else:
        from rembg import new_session, remove
        print(f'Quitando el fondo con {a.fondo} (local, puede tardar un par de minutos)…')
        mascara = remove(im, session=new_session(a.fondo), only_mask=True)
        mascara.save(dir_ / 'mascara.png', optimize=True)

    px = np.asarray(im).astype(np.float32)
    if a.niveles:
        # El blanco del sujeto (sus píxeles más claros) pasa a blanco papel; el negro queda.
        sujeto = px[np.asarray(mascara) > 230]
        lum = sujeto.mean(1)
        blanco = sujeto[lum >= np.percentile(lum, 97)].mean(0)
        negro = np.percentile(sujeto, 0.3, axis=0)
        destino = np.array([246, 243, 234], np.float32)
        px = np.clip((px - negro) / (blanco - negro), 0, 1) ** a.gamma * destino
    maestra = Image.new('RGB', im.size, 'white')
    maestra.paste(Image.fromarray(px.astype(np.uint8)), mask=mascara)
    maestra.save(dir_ / 'maestra.jpg', quality=92)

    if a.fondo != 'ninguno':
        (dir_ / 'silueta.svg').write_text(silueta_svg(mascara))

    ficha['preparado'] = {
        'fecha': HOY, 'rotar': a.rotar, 'recorte': a.recorte, 'fondo': a.fondo,
        'niveles': a.niveles, 'gamma': a.gamma, 'tamanio': list(im.size),
    }
    ficha_de(a.slug).write_text(json.dumps(ficha, ensure_ascii=False, indent=2))
    print(f'Listo: {(dir_ / "maestra.jpg").relative_to(RAIZ)} ({im.width}×{im.height} px)')


def silueta_svg(mascara, paso=4):
    """Contorno de la máscara como path SVG, en píxeles de la imagen."""
    import cv2
    import numpy as np
    chica = np.asarray(mascara.resize((mascara.width // paso, mascara.height // paso)))
    _, bn = cv2.threshold(chica, 128, 255, cv2.THRESH_BINARY)
    contornos, _ = cv2.findContours(bn, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    partes = []
    for c in contornos:
        if cv2.contourArea(c) < 20:
            continue
        c = cv2.approxPolyDP(c, 0.8, True)[:, 0, :] * paso
        partes.append('M' + ' L'.join(f'{x} {y}' for x, y in c) + ' Z')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {mascara.width} {mascara.height}">'
            f'<path d="{" ".join(partes)}"/></svg>\n')


def cmd_grilla(a):
    """Zoom de la maestra con una grilla en píxeles, para leer las coordenadas de cada punto."""
    from PIL import Image, ImageDraw
    im = Image.open(DIR_IMAGENES / a.slug / 'maestra.jpg').convert('RGB')
    x0, y0, x1, y1 = (int(v) for v in a.zona.split(',')) if a.zona else (0, 0, im.width, im.height)
    c = im.crop((x0, y0, x1, y1))
    k = 1200 / max(c.size)
    c = c.resize((round(c.width * k), round(c.height * k)))
    d = ImageDraw.Draw(c)
    paso = a.paso or max(25, round(max(x1 - x0, y1 - y0) / 20 / 25) * 25)
    for x in range((x0 // paso + 1) * paso, x1, paso):
        fuerte = x % (paso * 2) == 0
        d.line([((x - x0) * k, 0), ((x - x0) * k, c.height)], fill=(0, 110, 255) if fuerte else (170, 210, 255))
        if fuerte:
            d.text(((x - x0) * k + 2, 2), str(x), fill=(0, 0, 190))
    for y in range((y0 // paso + 1) * paso, y1, paso):
        fuerte = y % (paso * 2) == 0
        d.line([(0, (y - y0) * k), (c.width, (y - y0) * k)], fill=(0, 150, 0) if fuerte else (180, 235, 180))
        if fuerte:
            d.text((2, (y - y0) * k + 2), str(y), fill=(0, 100, 0))
    salida = RAIZ / 'salida' / 'pruebas' / f'{a.slug}-grilla-{x0}-{y0}.png'
    salida.parent.mkdir(parents=True, exist_ok=True)
    c.save(salida)
    print(f'Grilla: {salida.relative_to(RAIZ)} (líneas cada {paso} px; los números son píxeles de la maestra)')


def cmd_ficha(a):
    f = json.loads(ficha_de(a.slug).read_text())
    for k in ('titulo', 'autor', 'fecha', 'fuente', 'pagina', 'licencia', 'licencia_texto', 'consultado'):
        print(f'{k:15} {f.get(k, "")}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('buscar')
    b.add_argument('consulta')
    b.add_argument('--fuentes', default='commons,openverse,archive,met')
    b.add_argument('-n', type=int, default=10)
    d = sub.add_parser('bajar')
    d.add_argument('fuente', choices=FUENTES)
    d.add_argument('ref', help='commons: "File:…"; archive: <identificador>/n<página>; met: id; openverse: uuid')
    d.add_argument('--slug', required=True)
    d.add_argument('--aceptar-licencia', action='store_true')
    p = sub.add_parser('preparar')
    p.add_argument('slug')
    p.add_argument('--rotar', type=float, default=0, help='grados, antihorario (las láminas de libros suelen venir a -90)')
    p.add_argument('--recorte', help='x0,y0,x1,y1 en píxeles, después de rotar')
    p.add_argument('--fondo', default='ninguno', help='ninguno, birefnet-general o isnet-general-use')
    p.add_argument('--niveles', action='store_true', help='blanco del sujeto a blanco papel')
    p.add_argument('--gamma', type=float, default=0.85)
    f = sub.add_parser('ficha')
    f.add_argument('slug')
    g = sub.add_parser('grilla')
    g.add_argument('slug')
    g.add_argument('--zona', help='x0,y0,x1,y1 en píxeles de la maestra (por defecto, toda)')
    g.add_argument('--paso', type=int, help='separación de la grilla en píxeles')
    a = ap.parse_args()
    {'buscar': cmd_buscar, 'bajar': cmd_bajar, 'preparar': cmd_preparar, 'ficha': cmd_ficha,
     'grilla': cmd_grilla}[a.cmd](a)


if __name__ == '__main__':
    main()
