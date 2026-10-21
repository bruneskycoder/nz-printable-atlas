#!/usr/bin/env python3
"""Base cartográfica de Nueva Zelanda para el atlas (lote 6).

    python3 herramientas/geo-nz.py            # baja lo que falte y procesa todo
    python3 herramientas/geo-nz.py --relieve  # solo rehace los dos relieves
    python3 herramientas/geo-nz.py --parques  # solo baja los parques nacionales del DOC

Fuentes (se bajan a cache/, que no se sube al repositorio):
  - Regiones: geoBoundaries gbOpen NZL ADM1 (Stats NZ, límites 2017), CC BY 4.0.
  - Lagos, ríos y rutas: Natural Earth 1:10 millones, dominio público.
  - Relieve: Terrain Tiles de AWS (Mapzen/Tilezen), formato terrarium, zoom 9.
    En Nueva Zelanda usan el modelo de LINZ (CC BY 4.0), SRTM y ETOPO1.
  - Parques nacionales: DOC, «DOC Public Conservation Land» (NaPALIS), CC BY 4.0.

Salida en datos/nz/ (sí se sube):
  - regiones.json, regiones-chico.json, chatham.json, lagos.json, rios.json,
    rutas.json: GeoJSON en NZTM2000 (EPSG:2193), en metros.
  - relieve.png: sombreado del relieve sobre la grilla del mural v1
    (0,125 mm por píxel a escala 1:2.100.000, o sea 262,5 m). Lo usan las fichas.
  - relieve-mural.png: lo mismo sobre la grilla del mural v2 (1:1.900.000,
    237,5 m por píxel), con la altura continua para las tintas hipsométricas.

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

# Parques nacionales: capa vigente de tierras de conservación del DOC (NaPALIS), en NZTM
DOC = ('https://services1.arcgis.com/3JjYDyG3oajxU6HO/arcgis/rest/services/DOC_Public_Conservation_Land_FHV/'
       'FeatureServer/0/query?where=Type%3D%27NATIONAL_PARK%27&outFields=Name,Legislation,Start_Date'
       '&outSR=2193&maxAllowableOffset=60&geometryPrecision=0&f=geojson')
GEOB = 'https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/main/releaseData/gbOpen/NZL/ADM1/geoBoundaries-NZL-ADM1.geojson'
NE = 'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/{}.geojson'
TERRENO = 'https://elevation-tiles-prod.s3.amazonaws.com/terrarium/9/{x}/{y}.png'

# Grillas de los relieves maestros: origen arriba a la izquierda en NZTM.
# (escala, x0, y0, ancho y alto en mm, archivo). La v2 es la de atlas_nz.MURAL_*.
PX_MM = 0.125
GRILLAS = {
    'v1': (2_100_000, 1_018_300, 6_238_000, (544, 730), 'relieve.png'),
    'mural': (1_900_000, 1_067_180, 6_241_810, (550, 811), 'relieve-mural.png'),
}


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


def parques():
    """Los 13 parques nacionales del DOC, simplificados para el mural (datos/nz/parques.json)."""
    crudo = CACHE / 'geo' / 'doc-parques.geojson'
    bajar(DOC, crudo)
    d = json.loads(crudo.read_text())
    # «Land held for National Park Purposes» es tierra reservada, no un parque nacional
    d['features'] = [f for f in d['features'] if f['properties']['Name'].endswith(('National Park', 'Park)'))]
    salida = CACHE / 'geo' / 'doc-parques-filtrado.geojson'
    salida.write_text(json.dumps(d))
    mapshaper(str(salida), '-each', 'nombre = Name', '-filter-fields', 'nombre',
              '-simplify', 'interval=150', 'keep-shapes', '-filter-islands', 'min-area=2000000',
              '-o', str(DATOS / 'parques.json'), 'precision=10', 'format=geojson')
    n = len(json.loads((DATOS / 'parques.json').read_text())['features'])
    print(f'  datos/nz/parques.json: {n} parques, {(DATOS / "parques.json").stat().st_size // 1024} KB')


def relieve(grilla):
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

    # 2. Remuestreo a la grilla, en NZTM
    ESCALA, X0, Y0, MURAL_MM, ARCHIVO = GRILLAS[grilla]
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
    if grilla != 'v1':
        # Los Terrain Tiles traen algunos píxeles sueltos de 4000–5000 m (en Kahurangi o
        # Banks Peninsula, donde no hay nada de esa altura): se bajan al máximo de sus vecinos
        # (también grupitos de 2 × 2: se compara con el anillo a 2 píxeles, unos 475 m)
        anillo = [(dy, dx) for dy in range(-2, 3) for dx in range(-2, 3) if max(abs(dy), abs(dx)) == 2]
        vecinos = np.max([np.roll(z, d, axis=(0, 1)) for d in anillo], axis=0)
        z = np.where(z > vecinos + 900, vecinos, z)

    # 4. Sombreado (luz del noroeste, 45°), con exageración vertical leve
    dzdy, dzdx = np.gradient(z * 1.6, paso)
    pend = np.arctan(np.hypot(dzdx, dzdy))
    asp = np.arctan2(-dzdx, dzdy)
    azi, alt = math.radians(315), math.radians(45)
    luz = np.sin(alt) * np.cos(pend) + np.cos(alt) * np.sin(pend) * np.cos(azi - asp)
    plano = math.sin(alt)
    sombra = np.clip((plano - luz) / plano, 0, 1) ** 0.85
    # Canal 0: sombra (0–255); canal 2: tierra. Canal 1: en la v1, la altura en
    # clases (×50) para las tintas ocre; en el mural v2, la altura continua en
    # pasos de 15 m (hasta 3825 m) para las tintas hipsométricas.
    if grilla == 'v1':
        altura = np.where(tierra, np.digitize(z, [500, 1000, 1500, 2000]) * 50, 0)
    else:
        altura = np.where(tierra, np.clip(np.round(z / 15), 0, 255), 0)
    rgb = np.dstack([
        (sombra * 255 * tierra).astype(np.uint8),
        altura.astype(np.uint8),
        np.asarray(mascara),
    ])
    Image.fromarray(rgb, 'RGB').save(DATOS / ARCHIVO, optimize=True)
    print(f'  datos/nz/{ARCHIVO}: {ancho}×{alto} px, altura máxima {z.max():.0f} m, '
          f'{(DATOS / ARCHIVO).stat().st_size // 1024} KB')


if __name__ == '__main__':
    if '--parques' in sys.argv:
        parques()
        sys.exit()
    if '--relieve' not in sys.argv:
        vectores()
        parques()
    for g in GRILLAS:
        relieve(g)
