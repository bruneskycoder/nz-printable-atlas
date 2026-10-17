#!/usr/bin/env python3
"""Base cartográfica de Nueva Zelanda para el atlas (lote 6).

    python3 herramientas/geo-nz.py            # baja lo que falte y procesa todo
    python3 herramientas/geo-nz.py --relieve  # solo rehace el relieve

Fuentes (se bajan a cache/, que no se sube al repositorio):
  - Regiones: geoBoundaries gbOpen NZL ADM1 (Stats NZ, límites 2017), CC BY 4.0.
  - Lagos, ríos y rutas: Natural Earth 1:10 millones, dominio público.
  - Relieve: Terrain Tiles de AWS (Mapzen/Tilezen), formato terrarium, zoom 9.
    En Nueva Zelanda usan el modelo de LINZ (CC BY 4.0), SRTM y ETOPO1.

Salida en datos/nz/ (sí se sube):
  - regiones.json, regiones-chico.json, chatham.json, lagos.json, rios.json,
    rutas.json: GeoJSON en NZTM2000 (EPSG:2193), en metros.
  - relieve.png: sombreado del relieve sobre la grilla del mural
    (0,125 mm por píxel a escala 1:2.100.000, o sea 262,5 m).

Requiere: Node con mapshaper (npm install), Python con numpy, pyproj y Pillow.
"""
import json
import math
import subprocess
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CACHE = RAIZ / 'cache'
DATOS = RAIZ / 'datos' / 'nz'
MAPSHAPER = RAIZ / 'node_modules' / '.bin' / 'mapshaper'

NZTM = '+proj=tmerc +lat_0=0 +lon_0=173 +k=0.9996 +x_0=1600000 +y_0=10000000 +ellps=GRS80 +units=m +no_defs'
CITM = '+proj=tmerc +lat_0=-44 +lon_0=-176.5 +k=1 +x_0=3500000 +y_0=10000000 +ellps=GRS80 +units=m +no_defs'

GEOB = 'https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/main/releaseData/gbOpen/NZL/ADM1/geoBoundaries-NZL-ADM1.geojson'
NE = 'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/{}.geojson'
TERRENO = 'https://elevation-tiles-prod.s3.amazonaws.com/terrarium/9/{x}/{y}.png'

# Grilla del mural (ver herramientas/atlas.py): origen arriba a la izquierda en NZTM
ESCALA = 2_100_000
X0, Y0 = 1_018_300, 6_238_000
MURAL_MM = (544, 730)
PX_MM = 0.125


def bajar(url, destino):
    if destino.exists() and destino.stat().st_size > 0:
        return
    destino.parent.mkdir(parents=True, exist_ok=True)
    print('  bajando', url)
    with urllib.request.urlopen(url, timeout=300) as r:
        destino.write_bytes(r.read())


def mapshaper(*args):
    subprocess.run([str(MAPSHAPER), '-i', *args, '-quiet'], check=True)


def vectores():
    DATOS.mkdir(parents=True, exist_ok=True)
    adm1 = CACHE / 'geo' / 'adm1.geojson'
    bajar(GEOB, adm1)
    for capa in ('ne_10m_lakes', 'ne_10m_rivers_lake_centerlines', 'ne_10m_roads'):
        bajar(NE.format(capa), CACHE / 'geo' / f'{capa}.geojson')

    renombrar = ("iso = shapeISO.slice(3); nombre = shapeName.replace(' Region', '')"
                 ".replace('Manawatu-Wanganui', 'Manawatū-Whanganui')")
    comunes = ['-each', renombrar, '-filter-fields', 'iso,nombre']
    # Mural y mapas regionales: 200 m entre vértices (0,1 mm a 1:2.100.000)
    mapshaper(str(adm1), '-filter', 'shapeISO != "NZ-CIT"', *comunes, '-proj', NZTM,
              '-simplify', 'interval=200', 'keep-shapes', '-filter-islands', 'min-area=1000000',
              '-o', str(DATOS / 'regiones.json'), 'precision=10', 'format=geojson')
    # Mapas de ubicación: 1,5 km entre vértices, sin islas chicas
    mapshaper(str(adm1), '-filter', 'shapeISO != "NZ-CIT"', *comunes, '-proj', NZTM,
              '-simplify', 'interval=1500', 'keep-shapes', '-filter-islands', 'min-area=40000000',
              '-o', str(DATOS / 'regiones-chico.json'), 'precision=100', 'format=geojson')
    # Límites entre regiones y tierra firme (para la costa y las líneas de agua)
    mapshaper(str(DATOS / 'regiones.json'), '-innerlines',
              '-o', str(DATOS / 'limites.json'), 'precision=10', 'format=geojson')
    mapshaper(str(DATOS / 'regiones.json'), '-dissolve',
              '-o', str(DATOS / 'tierra.json'), 'precision=10', 'format=geojson')
    mapshaper(str(adm1), '-filter', 'shapeISO == "NZ-CIT"', *comunes, '-proj', CITM,
              '-simplify', 'interval=150', '-filter-islands', 'min-area=500000',
              '-o', str(DATOS / 'chatham.json'), 'precision=10', 'format=geojson')
    caja = 'bbox=166,-48,179,-34'
    mapshaper(str(CACHE / 'geo' / 'ne_10m_lakes.geojson'), '-clip', caja, '-filter-fields', 'name',
              '-proj', NZTM, '-o', str(DATOS / 'lagos.json'), 'precision=10', 'format=geojson')
    mapshaper(str(CACHE / 'geo' / 'ne_10m_rivers_lake_centerlines.geojson'), '-clip', caja,
              '-filter-fields', 'name,scalerank', '-proj', NZTM,
              '-o', str(DATOS / 'rios.json'), 'precision=10', 'format=geojson')
    mapshaper(str(CACHE / 'geo' / 'ne_10m_roads.geojson'), '-clip', caja,
              '-filter-fields', 'type,scalerank', '-proj', NZTM,
              '-o', str(DATOS / 'rutas.json'), 'precision=10', 'format=geojson')
    for f in sorted(DATOS.glob('*.json')):
        print(f'  {f.relative_to(RAIZ)}: {f.stat().st_size // 1024} KB')


def relieve():
    import numpy as np
    from PIL import Image, ImageDraw
    from pyproj import Transformer

    # 1. Mosaico de alturas (terrarium: altura = R*256 + G + B/256 - 32768)
    xs, ys = range(492, 511), range(307, 333)
    carpeta = CACHE / 'terreno'
    with ThreadPoolExecutor(16) as ex:
        list(ex.map(lambda t: bajar(TERRENO.format(x=t[0], y=t[1]), carpeta / f'9-{t[0]}-{t[1]}.png'),
                    [(x, y) for x in xs for y in ys]))
    mosaico = np.zeros((len(ys) * 256, len(xs) * 256), dtype=np.float32)
    for i, x in enumerate(xs):
        for j, y in enumerate(ys):
            a = np.asarray(Image.open(carpeta / f'9-{x}-{y}.png').convert('RGB'), dtype=np.float32)
            mosaico[j * 256:(j + 1) * 256, i * 256:(i + 1) * 256] = a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768

    # 2. Remuestreo a la grilla del mural, en NZTM
    ancho, alto = round(MURAL_MM[0] / PX_MM), round(MURAL_MM[1] / PX_MM)
    paso = PX_MM * ESCALA / 1000  # metros por píxel
    gx = X0 + (np.arange(ancho) + 0.5) * paso
    gy = Y0 - (np.arange(alto) + 0.5) * paso
    mx, my = np.meshgrid(gx, gy)
    lon, lat = Transformer.from_crs(NZTM, 'EPSG:4326', always_xy=True).transform(mx, my)
    n = 2 ** 9
    tx = (lon + 180) / 360 * n * 256 - xs[0] * 256
    ty = (1 - np.log(np.tan(np.radians(lat)) + 1 / np.cos(np.radians(lat))) / math.pi) / 2 * n * 256 - ys[0] * 256
    x0 = np.clip(np.floor(tx).astype(int), 0, mosaico.shape[1] - 2)
    y0 = np.clip(np.floor(ty).astype(int), 0, mosaico.shape[0] - 2)
    fx, fy = tx - x0, ty - y0
    z = (mosaico[y0, x0] * (1 - fx) * (1 - fy) + mosaico[y0, x0 + 1] * fx * (1 - fy)
         + mosaico[y0 + 1, x0] * (1 - fx) * fy + mosaico[y0 + 1, x0 + 1] * fx * fy)

    # 3. Máscara de tierra con los polígonos de las regiones
    mascara = Image.new('L', (ancho, alto), 0)
    dib = ImageDraw.Draw(mascara)
    a_px = lambda x, y: ((x - X0) / paso, (Y0 - y) / paso)
    for f in json.load(open(DATOS / 'regiones.json'))['features']:
        g = f['geometry']
        polis = g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]
        for p in polis:
            dib.polygon([a_px(*c) for c in p[0]], fill=255)
            for hueco in p[1:]:
                dib.polygon([a_px(*c) for c in hueco], fill=0)
    tierra = np.asarray(mascara) > 0
    z = np.where(tierra, np.maximum(z, 0), 0)

    # 4. Sombreado (luz del noroeste, 45°), con exageración vertical leve
    dzdy, dzdx = np.gradient(z * 1.6, paso)
    pend = np.arctan(np.hypot(dzdx, dzdy))
    asp = np.arctan2(-dzdx, dzdy)
    azi, alt = math.radians(315), math.radians(45)
    luz = np.sin(alt) * np.cos(pend) + np.cos(alt) * np.sin(pend) * np.cos(azi - asp)
    plano = math.sin(alt)
    sombra = np.clip((plano - luz) / plano, 0, 1) ** 0.85
    # Canal 0: sombra (0–255); canal 1: altura en clases para tintas; se guardan en un PNG RGB
    clases = np.digitize(z, [500, 1000, 1500, 2000]).astype(np.uint8)
    rgb = np.dstack([
        (sombra * 255 * tierra).astype(np.uint8),
        np.where(tierra, clases * 50, 0).astype(np.uint8),
        np.asarray(mascara),
    ])
    Image.fromarray(rgb, 'RGB').save(DATOS / 'relieve.png', optimize=True)
    print(f'  datos/nz/relieve.png: {ancho}×{alto} px, altura máxima {z.max():.0f} m, '
          f'{(DATOS / "relieve.png").stat().st_size // 1024} KB')


if __name__ == '__main__':
    if '--relieve' not in sys.argv:
        vectores()
    relieve()
