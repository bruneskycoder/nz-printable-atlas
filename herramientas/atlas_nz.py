"""Herramientas compartidas del atlas de Nueva Zelanda (lote 6).

Todo se dibuja en milímetros de la lámina: un Encuadre pasa de NZTM2000
(metros) a mm con una escala y un origen. Las capas vienen de datos/nz/
(ver herramientas/geo-nz.py).
"""
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import shapely
from PIL import Image
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform as transformar

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / 'datos' / 'nz'
NZTM = '+proj=tmerc +lat_0=0 +lon_0=173 +k=0.9996 +x_0=1600000 +y_0=10000000 +ellps=GRS80 +units=m +no_defs'
_A_NZTM = Transformer.from_crs('EPSG:4326', NZTM, always_xy=True)

PT = 25.4 / 72  # mm por punto tipográfico

# Grilla del relieve maestro (herramientas/geo-nz.py): mural v1 a 1:2.100.000.
# Lo usan las fichas, que remuestrean a su escala.
RELIEVE_ESCALA = 2_100_000
RELIEVE_X0, RELIEVE_Y0 = 1_018_300, 6_238_000
RELIEVE_PX_MM = 0.125

# Mural v2: 9 A4 verticales (3 × 3) a 1:1.900.000. El relieve maestro del mural
# (relieve-mural.png) usa exactamente esta grilla.
MURAL_ESCALA = 1_900_000
MURAL_X0, MURAL_Y0 = 1_067_180, 6_241_810

OCRE = np.array([154, 92, 22], dtype=np.float32)
# Tinta ocre por clase de altura: <500, 500–1000, 1000–1500, 1500–2000, >2000 m
TINTA_ALTURA = np.array([0.0, 0.0, 0.17, 0.27, 0.38], dtype=np.float32)


ORDEN_REGIONES = ['NTL', 'AUK', 'WKO', 'BOP', 'GIS', 'HKB', 'TKI', 'MWT', 'WGN',
                  'TAS', 'NLS', 'MBH', 'WTC', 'CAN', 'OTA', 'STL']


def nombre_region(iso):
    for p, _ in capa('regiones'):
        if p['iso'] == iso:
            return p['nombre']
    raise KeyError(iso)


def proyectar(lon, lat):
    return _A_NZTM.transform(lon, lat)


class Encuadre:
    """Pasa de NZTM (metros) a mm de la lámina. (x0, y0) es el NZTM del punto (0, 0)."""

    def __init__(self, escala, x0, y0):
        self.escala, self.x0, self.y0 = escala, x0, y0
        self.k = 1000 / escala

    def mm(self, x, y):
        return (x - self.x0) * self.k, (self.y0 - y) * self.k

    def lonlat(self, lon, lat):
        return self.mm(*proyectar(lon, lat))

    def geom(self, g):
        return transformar(lambda x, y, z=None: ((x - self.x0) * self.k, (self.y0 - y) * self.k), g)


@lru_cache(maxsize=None)
def capa(nombre):
    """Lista de (propiedades, geometría shapely en NZTM)."""
    d = json.loads((DATOS / f'{nombre}.json').read_text())
    if d['type'] == 'GeometryCollection':  # mapshaper sin atributos
        return [({}, shape(g)) for g in d['geometries']]
    return [(f['properties'] or {}, shape(f['geometry'])) for f in d['features'] if f['geometry']]


@lru_cache(maxsize=None)
def tabla(nombre):
    return json.loads((DATOS / f'{nombre}.json').read_text())


def recortar(g, x0, y0, x1, y1):
    if g.is_empty:
        return g
    return shapely.clip_by_rect(g, x0, y0, x1, y1)


def _puntos(coords, p):
    salida, previo = [], None
    for x, y in coords:
        t = (round(x, p), round(y, p))
        if t != previo:
            salida.append(t)
            previo = t
    return salida


def ruta(g, p=2):
    """Geometría shapely (en mm) a datos de <path>."""
    if g is None or g.is_empty:
        return ''
    t = g.geom_type
    if t in ('MultiPolygon', 'MultiLineString', 'GeometryCollection'):
        return ''.join(ruta(h, p) for h in g.geoms)
    if t == 'Polygon':
        anillos, cerrar = [g.exterior, *g.interiors], True
    elif t in ('LineString', 'LinearRing'):
        anillos, cerrar = [g], False
    else:
        return ''
    s = ''
    for a in anillos:
        pts = _puntos(a.coords, p)
        if len(pts) < 2:
            continue
        s += 'M' + ' '.join(f'{x:g} {y:g}' for x, y in pts) + ('Z' if cerrar else '')
    return s


def esc(t):
    return str(t).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


# ---------------------------------------------------------------------------
# Rótulos con posición relativa a un punto
ANCLA = {
    'E': (1, 0, 'start'), 'O': (-1, 0, 'end'), 'N': (0, -1, 'middle'), 'S': (0, 1, 'middle'),
    'NE': (0.75, -0.75, 'start'), 'NO': (-0.75, -0.75, 'end'), 'SE': (0.75, 0.75, 'start'), 'SO': (-0.75, 0.75, 'end'),
}


def rotulo_punto(x, y, texto, pos, sep, tam_mm, clase):
    """Devuelve (svg, x, y, ancla) de un rótulo ubicado alrededor de un punto."""
    dx, dy, ancla = ANCLA[pos]
    tx = x + dx * sep
    ty = y + dy * sep + tam_mm * 0.35  # centra la altura de las minúsculas
    if dy < 0:
        ty -= tam_mm * 0.15
    if dy > 0:
        ty += tam_mm * 0.3
    return f'<text class="{clase}" x="{tx:.2f}" y="{ty:.2f}" text-anchor="{ancla}">{esc(texto)}</text>', tx, ty, ancla


@lru_cache(maxsize=None)
def _fuente(cual, peso):
    from PIL import ImageFont
    archivo = {'texto': 'SourceSans3-variable.ttf', 'titulo': 'Bitter-variable.ttf'}[cual]
    f = ImageFont.truetype(str(RAIZ / 'fuentes' / archivo), 100)
    try:
        f.set_variation_by_axes([peso])
    except Exception:
        pass
    return f


def ancho_texto(texto, tam_mm, cual='texto', peso=400, espaciado=0.0):
    """Ancho real del texto en mm, medido con la fuente del repositorio."""
    return _fuente(cual, peso).getlength(texto) / 100 * tam_mm + espaciado * len(texto)


def caja_rotulo(x, y, texto, ancla, tam_mm, cual='texto', peso=400, espaciado=0.0, rot=0):
    """Caja aproximada (x0, y0, x1, y1) de un <text> con su línea de base en (x, y)."""
    w = ancho_texto(texto, tam_mm, cual, peso, espaciado)
    x0 = {'start': x, 'middle': x - w / 2, 'end': x - w}[ancla]
    caja = (x0, y - 0.75 * tam_mm, x0 + w, y + 0.22 * tam_mm)
    if rot:
        from shapely import affinity
        from shapely.geometry import box as caja_geo
        return affinity.rotate(caja_geo(*caja), rot, origin=(x, y)).bounds
    return caja


# ---------------------------------------------------------------------------
# Relieve
@lru_cache(maxsize=1)
def relieve_maestro():
    return np.asarray(Image.open(DATOS / 'relieve.png'))


def colorear_relieve(a, sombra_max=0.55):
    """a: recorte del relieve maestro (canales: sombra, clase*50, tierra). Devuelve RGB con el mar en blanco."""
    sombra = a[..., 0].astype(np.float32) / 255
    clase = (a[..., 1] // 50).clip(0, 4)
    tierra = a[..., 2] > 0
    t = TINTA_ALTURA[clase][..., None]
    rgb = 255 * (1 - t) + OCRE * t
    rgb *= (1 - sombra_max * sombra)[..., None]
    # Fondo blanco en el mar: la imagen es opaca y se guarda en JPEG, que Chromium
    # pasa tal cual al PDF (un PNG se descomprime y pesa diez veces más)
    rgb = np.where(tierra[..., None], rgb, 255)
    return Image.fromarray(rgb.clip(0, 255).astype(np.uint8), 'RGB')


def relieve_ventana(x_mm, y_mm, ancho_mm, alto_mm, encuadre=None, px_mm=None):
    """Relieve coloreado para una ventana. Sin encuadre: ventana en mm del mural.
    Con encuadre (otra escala): remuestrea el maestro a esa escala (vecino más cercano
    sobre el maestro suavizado) con px_mm de resolución."""
    m = relieve_maestro()
    if encuadre is None:
        x0, y0 = round(x_mm / RELIEVE_PX_MM), round(y_mm / RELIEVE_PX_MM)
        w, h = round(ancho_mm / RELIEVE_PX_MM), round(alto_mm / RELIEVE_PX_MM)
        return colorear_relieve(m[y0:y0 + h, x0:x0 + w])
    px_mm = px_mm or 0.15
    w, h = round(ancho_mm / px_mm), round(alto_mm / px_mm)
    gx = x_mm + (np.arange(w) + 0.5) * px_mm
    gy = y_mm + (np.arange(h) + 0.5) * px_mm
    # mm de la lámina -> NZTM -> píxel del maestro
    X = encuadre.x0 + gx / encuadre.k
    Y = encuadre.y0 - gy / encuadre.k
    paso = RELIEVE_PX_MM * RELIEVE_ESCALA / 1000
    ix = np.clip(((X - RELIEVE_X0) / paso).astype(int), 0, m.shape[1] - 1)
    iy = np.clip(((RELIEVE_Y0 - Y) / paso).astype(int), 0, m.shape[0] - 1)
    return colorear_relieve(m[iy[:, None], ix[None, :]])


# ---------------------------------------------------------------------------
# Relieve del mural v2: mar celeste y tintas hipsométricas continuas
MAR_MURAL = np.array([206, 226, 240], dtype=np.float32)
# Tintas por altura (m): de crema en la costa a marrón en altura y gris nieve arriba de 2400 m
HIPSO = [
    (0, (243, 240, 225)), (250, (238, 232, 208)), (600, (228, 214, 180)), (1000, (214, 193, 152)),
    (1500, (196, 170, 132)), (2000, (182, 160, 134)), (2400, (214, 210, 206)), (3000, (240, 240, 242)),
]


@lru_cache(maxsize=1)
def relieve_mural_maestro():
    Image.MAX_IMAGE_PIXELS = None
    return np.asarray(Image.open(DATOS / 'relieve-mural.png'))


def relieve_mural_ventana(x_mm, y_mm, ancho_mm, alto_mm, sombra_max=0.5):
    """Relieve del mural v2 coloreado para una ventana en mm del mural (incluye el mar)."""
    m = relieve_mural_maestro()
    x0, y0 = round(x_mm / RELIEVE_PX_MM), round(y_mm / RELIEVE_PX_MM)
    w, h = round(ancho_mm / RELIEVE_PX_MM), round(alto_mm / RELIEVE_PX_MM)
    a = m[y0:y0 + h, x0:x0 + w]
    sombra = a[..., 0].astype(np.float32) / 255
    z = a[..., 1].astype(np.float32) * 15
    tierra = a[..., 2] > 0
    alturas = np.array([c for c, _ in HIPSO], dtype=np.float32)
    colores = np.array([c for _, c in HIPSO], dtype=np.float32)
    rgb = np.dstack([np.interp(z, alturas, colores[:, i]) for i in range(3)])
    rgb *= (1 - sombra_max * sombra)[..., None]
    rgb = np.where(tierra[..., None], rgb, MAR_MURAL)
    return Image.fromarray(rgb.clip(0, 255).astype(np.uint8), 'RGB')



def relieve_mural_encuadre(encuadre, ancho_mm, alto_mm, px_mm=0.12, sombra_max=0.5):
    """El relieve del mural v2 (tintas de altura y mar) para otro encuadre, como las fichas regionales.
    Las dos grillas son NZTM con escala uniforme, así que alcanza con recortar el maestro y escalarlo
    (bicúbico, canal por canal) antes de colorear."""
    m = relieve_mural_maestro()
    paso = RELIEVE_PX_MM * MURAL_ESCALA / 1000  # metros por píxel del maestro
    # Esquinas de la ventana en NZTM -> píxeles (fraccionarios) del maestro
    x0 = (encuadre.x0 - MURAL_X0) / paso
    y0 = (MURAL_Y0 - encuadre.y0) / paso
    x1 = x0 + ancho_mm / encuadre.k / paso
    y1 = y0 + alto_mm / encuadre.k / paso
    w, h = round(ancho_mm / px_mm), round(alto_mm / px_mm)
    canales = []
    for i in range(3):
        c = Image.fromarray(m[..., i])
        canales.append(np.asarray(c.transform((w, h), Image.EXTENT, (x0, y0, x1, y1), Image.BICUBIC)).astype(np.float32))
    sombra = canales[0] / 255
    z = canales[1] * 15
    tierra = canales[2] > 127
    alturas = np.array([c for c, _ in HIPSO], dtype=np.float32)
    colores = np.array([c for _, c in HIPSO], dtype=np.float32)
    rgb = np.dstack([np.interp(z, alturas, colores[:, i]) for i in range(3)])
    rgb *= (1 - sombra_max * sombra)[..., None]
    rgb = np.where(tierra[..., None], rgb, MAR_MURAL)
    return Image.fromarray(rgb.clip(0, 255).astype(np.uint8), 'RGB')
