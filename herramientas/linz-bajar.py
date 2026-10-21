#!/usr/bin/env python3
"""Baja capas del LINZ Data Service (WFS) para el mapa mural.

    LINZ_API_KEY=... python3 herramientas/linz-bajar.py datos/nz/linz-pedido.json salida-linz/

Qué capas y con qué filtro se piden está en el pedido (JSON), no en el código.
Lo corre la tarea de GitHub .github/workflows/linz.yml con el secreto
LINZ_API_KEY y publica el resultado en la rama datos-linz. La clave solo viaja
en la dirección del pedido: no se escribe en disco ni se imprime.

Salida: un .geojson.gz por capa (solo los campos pedidos, coordenadas
redondeadas) y manifiesto.json con título, versión, licencia y fecha de cada capa.
"""
import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

WFS = 'https://data.linz.govt.nz/services;key={clave}/wfs'
CATALOGO = 'https://data.linz.govt.nz/services/api/v1/layers/{capa}/'
PAGINA = 100_000
AGENTE = {'User-Agent': 'para-imprimir/atlas-nz (GitHub Actions)'}


def pedir(url, intentos=4):
    for i in range(intentos):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=AGENTE), timeout=600) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                # No se muestra la dirección: lleva la clave
                sys.exit(f'LINZ rechazó la clave (HTTP {e.code}). Revisá que el secreto LINZ_API_KEY '
                         'sea la clave completa y que tenga permiso para consultar capas.')
            if i == intentos - 1:
                sys.exit(f'LINZ respondió HTTP {e.code} después de {intentos} intentos.')
        except (urllib.error.URLError, TimeoutError) as e:
            if i == intentos - 1:
                sys.exit(f'No se pudo conectar con LINZ: {e.__class__.__name__}.')
        time.sleep(2 ** (i + 1))


def redondear(c, dec):
    if isinstance(c[0], (int, float)):
        return [round(v, dec) for v in c]
    return [redondear(x, dec) for x in c]


def bajar_capa(clave, p):
    base = {'service': 'WFS', 'version': '2.0.0', 'request': 'GetFeature',
            'typeNames': f'layer-{p["capa"]}', 'outputFormat': 'json', 'srsName': p['srs'], 'count': PAGINA}
    if p.get('filtro'):
        base['cql_filter'] = p['filtro']
    feats, inicio, primero = [], 0, None
    while True:
        q = dict(base, startIndex=inicio) if inicio else base
        lote = json.loads(pedir(WFS.format(clave=clave) + '?' + urllib.parse.urlencode(q)))['features']
        if not lote or (inicio and lote[0].get('id') == primero):
            break  # sin más páginas, o el servidor ignora startIndex
        primero = primero or lote[0].get('id')
        feats += lote
        if len(lote) < PAGINA:
            break
        inicio += PAGINA
    # Metros en NZTM; grados con 6 decimales (unos 10 cm)
    dec = 0 if p['srs'] == 'EPSG:2193' else 6
    campos = p.get('campos')
    for f in feats:
        if f.get('geometry'):
            f['geometry']['coordinates'] = redondear(f['geometry']['coordinates'], dec)
        if campos is not None:
            f['properties'] = {k: f['properties'].get(k) for k in campos}
        f.pop('id', None)
    return feats


def main(pedido, destino):
    clave = os.environ.get('LINZ_API_KEY', '').strip()
    if not clave:
        sys.exit('Falta el secreto LINZ_API_KEY: cargalo en GitHub, en Settings > Secrets and variables > Actions.')
    destino.mkdir(parents=True, exist_ok=True)
    manifiesto = {'bajado': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
                  'fuente': 'LINZ Data Service (data.linz.govt.nz), WFS', 'capas': []}
    for p in json.loads(pedido.read_text())['capas']:
        meta = json.loads(pedir(CATALOGO.format(capa=p['capa'])))
        feats = bajar_capa(clave, p)
        archivo = destino / f'{p["archivo"]}.geojson.gz'
        with gzip.open(archivo, 'wt', encoding='utf-8') as f:
            json.dump({'type': 'FeatureCollection', 'features': feats}, f, ensure_ascii=False, separators=(',', ':'))
        manifiesto['capas'].append({
            'archivo': archivo.name, 'capa': p['capa'], 'titulo': meta.get('title'),
            'version_publicada': meta.get('published_at'), 'licencia': (meta.get('license') or {}).get('title'),
            'srs': p['srs'], 'filtro': p.get('filtro'), 'elementos': len(feats),
            'url': f'https://data.linz.govt.nz/layer/{p["capa"]}/'})
        print(f'  {p["archivo"]}: capa {p["capa"]} ({meta.get("title")}), {len(feats)} elementos, '
              f'{archivo.stat().st_size // 1024} KB')
    (destino / 'manifiesto.json').write_text(json.dumps(manifiesto, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(Path(sys.argv[1]), Path(sys.argv[2]))
