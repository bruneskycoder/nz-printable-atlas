#!/usr/bin/env python3
"""Matriz región × sector del mapa mural (datos/sectores-nz.json).

    python3 herramientas/sectores-nz.py

Baja tres tablas de Stats NZ (republicadas por Figure.NZ) a cache/sectores/ y
calcula, para cada una de las 16 regiones, qué parte del total nacional de cada
sector tiene. Es geografía productiva: dónde están los animales, las hectáreas y
los empleos; no dice nada de vacantes.

Fuentes (todas de Stats NZ, CC BY 4.0):
  - Agricultural Production Statistics, junio 2025 (final), por consejo regional
    (Infoshare AGR003AA): ganado lechero, ovino y vacuno de carne.
  - Agricultural Production Census, junio 2022 (final), por región: superficie de
    fruta, uva de vino, hortalizas al aire libre y plantaciones forestales. La
    encuesta de 2025 ya no pregunta por horticultura, así que 2022 es lo último.
  - Business Demography, febrero 2025 (BDS_BDS_001): empleados en unidades
    geográficas (el lugar de trabajo) por industria ANZSIC06 y región.

Requiere: Python con openpyxl.
"""
import csv
import json
import urllib.request
from datetime import date
from pathlib import Path

import openpyxl

RAIZ = Path(__file__).resolve().parent.parent
CACHE = RAIZ / 'cache' / 'sectores'
SALIDA = RAIZ / 'datos' / 'sectores-nz.json'

FIGURE = 'https://figure.nz/table/{}/download-source-dataset'
TABLAS = {
    'aps2025': ('83PJnWFeJehqJYaS', 'aps2025.csv'),
    'aps2022': ('E6jEllmS8Dqm1AkL', 'aps2022.xlsx'),
    'bds2025': ('iFW1sTZa325SRowc', 'bds.xlsx'),
}

ISO = {
    'Northland': 'NTL', 'Auckland': 'AUK', 'Waikato': 'WKO', 'Bay of Plenty': 'BOP', 'Gisborne': 'GIS',
    "Hawke's Bay": 'HKB', 'Taranaki': 'TKI', 'Manawatu-Wanganui': 'MWT', 'Manawatu-Whanganui': 'MWT',
    'Wellington': 'WGN', 'Tasman': 'TAS', 'Nelson': 'NLS', 'Marlborough': 'MBH', 'West Coast': 'WTC',
    'Canterbury': 'CAN', 'Otago': 'OTA', 'Southland': 'STL',
}

# Columnas de la matriz: clave, nombre, fuente y qué se suma
SECTORES = [
    ('lecheria', 'Lechería', 'aps2025', ['Total Dairy Cattle (including Bobby Calves)'], 'cabezas de ganado lechero'),
    ('ovinos', 'Ovinos', 'aps2025', ['Total Sheep'], 'ovejas'),
    ('vacunos', 'Vacunos de carne', 'aps2025', ['Total Beef Cattle'], 'cabezas de ganado de carne'),
    ('fruta', 'Fruta', 'aps2022', 'fruta', 'hectáreas de frutales (sin uva de vino, olivos ni nueces)'),
    ('vid', 'Viñedos', 'aps2022', ['Wine grapes   (planted area)'], 'hectáreas de uva de vino'),
    ('hortalizas', 'Hortalizas', 'aps2022', ['Total outdoor area used for growing vegetables and cooking herbs'],
     'hectáreas de hortalizas al aire libre'),
    ('forestal', 'Forestal', 'aps2022', ['Plantations of exotic trees intended for harvest'], 'hectáreas de plantaciones para cosecha'),
    ('frigorificos', 'Frigoríficos', 'bds2025', ['C111100'], 'empleados en procesamiento de carne'),
    ('alojamiento', 'Alojamiento', 'bds2025', ['H440000'], 'empleados en alojamiento (hoteles, moteles, hostels, campings)'),
    ('construccion', 'Construcción', 'bds2025', ['E'], 'empleados en construcción'),
    ('transporte', 'Transporte y depósitos', 'bds2025', ['I'], 'empleados en transporte, correo y depósitos'),
    ('tecnicos', 'Arquitectura e ingeniería', 'bds2025', ['M692'],
     'empleados en servicios de arquitectura, ingeniería y técnicos (incluye dibujo técnico)'),
]

# Frutales del censo 2022: pepita, carozo, kiwi, subtropicales, uva de mesa, berries y cítricos
FRUTA = ['Apples', 'Pears', 'Nashi pears', 'Peaches', 'Apricots', 'Nectarines', 'Cherries', 'Plums',
         'TOTAL kiwifruit', 'Avocados', 'Feijoas', 'Tamarillos', 'Passionfruit', 'Persimmons', 'Table grapes',
         'Blackcurrants', 'Blueberries', 'Boysenberries', 'Raspberries', 'Strawberries', 'Oranges',
         'Grapefruit / goldfruit', 'Lemons', 'Mandarins', 'Tangelos', 'Other fruit, nut and edible tree crops grown outdoors']


def bajar(clave):
    tabla, archivo = TABLAS[clave]
    destino = CACHE / archivo
    if not destino.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        print('  bajando', FIGURE.format(tabla))
        with urllib.request.urlopen(FIGURE.format(tabla), timeout=600) as r:
            destino.write_bytes(r.read())
    return destino


def iso_de(nombre):
    n = str(nombre).replace(' Region', '').strip()
    return ISO.get(n)


def numero(v):
    """Valor numérico, o None si está suprimido (S, C, ..) por confidencialidad."""
    if isinstance(v, (int, float)):
        return float(v)
    v = str(v or '').strip().replace(',', '')
    try:
        return float(v)
    except ValueError:
        return None


def leer_aps2025():
    """{variable: {iso: valor}} y total nacional, para junio 2025."""
    filas = list(csv.reader(open(bajar('aps2025'), encoding='utf-8')))
    reg, var = filas[1], filas[2]
    cols, actual = {}, None
    for i, (r, v) in enumerate(zip(reg, var)):
        if r.strip():
            actual = r.strip()
        if v.strip():
            cols[(actual, v.strip())] = i
    anio = next(f for f in filas if f and f[0].strip() == '2025')
    out = {}
    for (region, v), i in cols.items():
        clave = 'NZ' if region.startswith('Total New') else iso_de(region)
        if clave:
            out.setdefault(v, {})[clave] = numero(anio[i])
    return out


def leer_aps2022():
    wb = openpyxl.load_workbook(bajar('aps2022'), read_only=True, data_only=True)
    filas = list(wb['Table 1'].iter_rows(values_only=True))
    desc = [str(d or '').strip() for d in filas[5]]
    out = {}
    for f in filas[7:]:
        if not f[0]:
            continue
        clave = 'NZ' if str(f[0]).startswith('Total New Zealand') else iso_de(f[0])
        if not clave:
            continue
        for i, d in enumerate(desc):
            if d:
                out.setdefault(d, {})[clave] = numero(f[i])
    # Fruta: suma de los frutales; las celdas suprimidas cuentan como cero y se marcan
    fruta = {}
    for d, vals in out.items():
        nombre = d.split('  ')[0].strip()
        if nombre in FRUTA:
            for k, v in vals.items():
                fruta[k] = fruta.get(k, 0) + (v or 0)
    out['fruta'] = fruta
    return out


def leer_bds2025():
    wb = openpyxl.load_workbook(bajar('bds2025'), read_only=True, data_only=True)
    out = {}
    for fila in wb['Data'].iter_rows(min_row=2, values_only=True):
        cod, area, anio, medida, valor = fila[4], fila[7], fila[8], fila[10], fila[12]
        if anio != 2025 or medida != 'EC_COUNT':
            continue
        clave = 'NZ' if str(area).startswith('Total New Zealand') else iso_de(area)
        if clave:
            out.setdefault(cod, {})[clave] = numero(valor)
    return out


def main():
    fuentes = {'aps2025': leer_aps2025(), 'aps2022': leer_aps2022(), 'bds2025': leer_bds2025()}
    regiones = list(dict.fromkeys(ISO.values()))
    sectores = []
    for clave, nombre, fuente, variables, unidad in SECTORES:
        datos = fuentes[fuente]
        vars_ = [variables] if isinstance(variables, str) else variables
        total = sum(datos[v]['NZ'] for v in vars_)
        valores, porcentaje, suprimidas = {}, {}, []
        for iso in regiones:
            vs = [datos[v].get(iso) for v in vars_]
            if any(x is None for x in vs):
                suprimidas.append(iso)
                valores[iso] = porcentaje[iso] = None
                continue
            valores[iso] = round(sum(vs))
            porcentaje[iso] = round(100 * sum(vs) / total, 1)
        asignado = sum(v for v in valores.values() if v)
        sectores.append({'clave': clave, 'nombre': nombre, 'fuente': fuente, 'unidad': unidad,
                         'total_nz': round(total), 'asignado_a_regiones_pct': round(100 * asignado / total, 1),
                         'suprimidas': suprimidas, 'valores': valores, 'porcentaje': porcentaje})
        print(f'  {nombre:26s} total {total:>12,.0f}  en regiones {100 * asignado / total:5.1f} %  '
              f'suprimidas: {", ".join(suprimidas) or "—"}')
    SALIDA.write_text(json.dumps({
        '_nota': ('Porcentaje del total nacional de cada sector que hay en cada región. Geografía productiva, '
                  'no vacantes. Generado por herramientas/sectores-nz.py. None = dato suprimido por Stats NZ '
                  'por confidencialidad. La suma por sector puede no dar 100: hay áreas fuera de las 16 regiones '
                  '(Chatham, «fuera de región») y redondeos.'),
        'consultado': date.today().isoformat(),
        'fuentes': {
            'aps2025': 'Stats NZ, Agricultural Production Statistics, junio 2025 (final), por consejo regional '
                       '(Infoshare AGR003AA, publicado el 2026-04-16), vía Figure.NZ.',
            'aps2022': 'Stats NZ, Agricultural Production Census, año a junio 2022 (final), tabla 1 por región, vía Figure.NZ.',
            'bds2025': 'Stats NZ, Business Demography Statistics, febrero 2025 (BDS_BDS_001: unidades geográficas '
                       'por área e industria ANZSIC06, cantidad de empleados), vía Figure.NZ.',
        },
        'sectores': sectores,
    }, ensure_ascii=False, indent=1) + '\n')
    print(f'  {SALIDA.relative_to(RAIZ)}')


if __name__ == '__main__':
    main()
