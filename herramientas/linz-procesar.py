#!/usr/bin/env python3
"""Procesa las capas de LINZ para el mapa mural v2 (datos/nz/linz/).

    git fetch origin datos-linz
    python3 herramientas/linz-procesar.py

Las capas las baja la tarea de GitHub «Datos de LINZ» (ver linz-bajar.py) y
quedan en la rama datos-linz. Este script las lee de ahí con git, sin cambiar
de rama, y escribe en NZTM2000:
  - rutas.json: State Highways (1:250k), con su número (hway_num).
  - lagos.json: lagos de más de 2 km², con su nombre oficial.
  - nombres-informe.txt: cada rótulo del mural comparado con el Gazetteer (NZGB):
    grafía oficial y distancia. Las correcciones van en datos/nz/mural.json.

Los ríos siguen siendo los de Natural Earth: en la red 1:250k de LINZ los ríos
anchos (Clutha, Rakaia, Waikato) son polígonos y los tramos no están unidos, así
que no da cursos completos; a 1:1.900.000 la diferencia es de un milímetro.

Requiere: Python con shapely.
"""
import gzip
import json
import subprocess
import unicodedata
from pathlib import Path

from shapely.geometry import mapping, shape
from shapely.ops import linemerge, unary_union

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / 'datos' / 'nz' / 'linz'
RAMA = 'origin/datos-linz'


def leer(nombre):
    """FeatureCollection de la rama datos-linz."""
    crudo = subprocess.run(['git', '-C', str(RAIZ), 'show', f'{RAMA}:{nombre}'], check=True, capture_output=True).stdout
    return json.loads(gzip.decompress(crudo)) if nombre.endswith('.gz') else json.loads(crudo)


def escribir(nombre, feats):
    SALIDA.mkdir(parents=True, exist_ok=True)
    (SALIDA / nombre).write_text(json.dumps({'type': 'FeatureCollection', 'features': feats},
                                            ensure_ascii=False, separators=(',', ':')))
    print(f'  datos/nz/linz/{nombre}: {len(feats)} elementos, {(SALIDA / nombre).stat().st_size // 1024} KB')


def redondear(g):
    """GeoJSON con coordenadas al metro."""
    def r(c):
        return [round(c[0]), round(c[1])] if isinstance(c[0], (int, float)) else [r(x) for x in c]
    m = mapping(g)
    return {'type': m['type'], 'coordinates': r(m['coordinates'])}


def fusionar(lineas):
    """Une los tramos que se tocan (linemerge no acepta una línea sola)."""
    g = unary_union(lineas)
    return linemerge(g) if g.geom_type == 'MultiLineString' else g


def rutas():
    por_numero = {}
    for f in leer('rutas.geojson.gz')['features']:
        n = str(f['properties'].get('hway_num') or '').strip()
        if n and f['geometry']:
            por_numero.setdefault(n, []).append(shape(f['geometry']))
    feats = []
    for n, gs in sorted(por_numero.items(), key=lambda t: (len(t[0]), t[0])):
        g = fusionar(gs).simplify(100)
        feats.append({'type': 'Feature', 'properties': {'hway_num': n}, 'geometry': redondear(g)})
    escribir('rutas.json', feats)


def lagos():
    feats = []
    for f in leer('lagos.geojson.gz')['features']:
        if not f['geometry']:
            continue
        g = shape(f['geometry'])
        if g.area < 2_000_000:
            continue
        p = f['properties']
        feats.append({'type': 'Feature', 'properties': {'nombre': p.get('name')},
                      'geometry': redondear(g.simplify(60))})
    escribir('lagos.json', feats)


def sin_macrones(t):
    return ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn').lower().strip()


def nombres():
    """Gazetteer reducido: nombres oficiales con su tipo y posición."""
    feats = []
    for f in leer('nombres.geojson.gz')['features']:
        p = f['properties']
        if not p.get('name') or p.get('crd_latitude') is None or 'Discontinued' in (p.get('status') or ''):
            continue
        feats.append({'n': p['name'], 'tipo': p.get('feat_type'), 'estado': p.get('status'),
                      'lat': round(float(p['crd_latitude']), 5), 'lon': round(float(p['crd_longitude']), 5)})
    print(f'  Gazetteer: {len(feats)} nombres vigentes')
    return feats


def informe(gaz):
    """Compara cada rótulo del mural con el Gazetteer: grafía oficial (macrones, nombre doble) y posición."""
    import math
    indice = {}
    for g in gaz:
        for parte in [g['n']] + [x.strip() for x in g['n'].split('/')]:
            indice.setdefault(sin_macrones(parte), []).append(g)
    nz = RAIZ / 'datos' / 'nz'
    rotulos = []
    for c in json.loads((nz / 'lugares.json').read_text())['lugares']:
        rotulos.append(('lugar', c['n'], c['lon'], c['lat']))
    r = json.loads((nz / 'rotulos.json').read_text())
    for p in r['picos']:
        rotulos.append(('pico', p['n'], p['lon'], p['lat']))
    for x in r['rotulos']:
        rotulos.append(('rótulo', x['t'], x['lon'], x['lat']))
    # Como queda en el mural: con las correcciones y los rasgos nuevos de mural.json
    mural = json.loads((nz / 'mural.json').read_text())
    def como_queda(t):
        d = mural['nombres'].get(t, {})
        return d.get('t', t) + (' / ' + d['t2'] if d.get('t2') else '')
    rotulos = [(c, como_queda(t), lon, lat) for c, t, lon, lat in rotulos]
    rotulos += [('pico', p['n'], p['lon'], p['lat']) for p in mural.get('picos_nuevos', [])]
    rotulos += [('rótulo', x['t'], x['lon'], x['lat']) for x in mural.get('rotulos_nuevos', []) if 'lon' in x]
    lineas = []
    for clase, texto, lon, lat in rotulos:
        claves = [sin_macrones(texto)] + [sin_macrones(x) for x in texto.split('/')]
        cands = [g for k in claves for g in indice.get(k, [])]
        if not cands:
            lineas.append(f'SIN DATO   {clase:7s} {texto}')
            continue
        dist = lambda g: 111.2 * math.hypot((g['lon'] - lon) * math.cos(math.radians(lat)), g['lat'] - lat)
        # Primero los nombres oficiales; entre ellos, el más cercano al rótulo
        mejor = min(cands, key=lambda g: (not (g['estado'] or '').startswith('Official'), dist(g)))
        d = dist(mejor)
        # Mayúsculas y espacios alrededor de «/» son estilo del mapa, no otra grafía
        def forma(n):
            return ' '.join(n.replace('/', ' / ').split()).lower()
        marca = 'IGUAL' if forma(mejor['n']) == forma(texto) else 'DISTINTO'
        if d > 5:
            marca += ' LEJOS'
        lineas.append(f'{marca:10s} {clase:7s} {texto} -> {mejor["n"]} ({mejor["tipo"]}, {mejor["estado"]}) a {d:.1f} km')
    (SALIDA / 'nombres-informe.txt').write_text('\n'.join(lineas) + '\n')
    print(f'  datos/nz/linz/nombres-informe.txt: {len(lineas)} rótulos, '
          f'{sum(not l.startswith("IGUAL ") for l in lineas)} para revisar')


def main():
    manifiesto = leer('manifiesto.json')
    SALIDA.mkdir(parents=True, exist_ok=True)
    (SALIDA / 'manifiesto.json').write_text(json.dumps(manifiesto, ensure_ascii=False, indent=1) + '\n')
    rutas()
    lagos()
    informe(nombres())


if __name__ == '__main__':
    main()
