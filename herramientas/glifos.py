"""Glifos de sector del mapa mural: un círculo del color del sector con un
pictograma blanco, dibujado a mano en una grilla de 24 × 24 (como estilo/iconos.js).
El mismo glifo va en el mapa, en la matriz región × sector y en el calendario."""

# Pictogramas: (tipo, datos). 'r' = relleno blanco, 't' = trazo blanco, 'c' = círculos (cx, cy, r)
DIBUJOS = {
    'lecheria': [('r', 'M12 3.2 C10 6 5.6 10.8 5.6 14.6 A6.4 6.4 0 0 0 18.4 14.6 C18.4 10.8 14 6 12 3.2 Z')],
    'ovinos': [('c', [(8.6, 11.6, 3.6), (12.4, 9.8, 3.8), (15.6, 12.2, 3.4), (11.2, 14.4, 3.4), (14.6, 15.2, 2.8)]),
               ('r', 'M17.6 8.6 C19.6 8.2 21.4 9.4 21.2 11.2 C21 12.8 19.4 13.4 18.2 12.8 Z'),
               ('r', 'M9.2 16.6 H10.8 V20.6 H9.2 Z M14.2 16.8 H15.8 V20.6 H14.2 Z')],
    'vacunos': [('r', 'M7.4 8.2 H16.6 L15.4 16.6 C14.6 19.4 9.4 19.4 8.6 16.6 Z'),
                ('r', 'M7.6 8.4 C4.6 8.2 2.8 6.6 2.6 3.8 C4.2 5.6 6 6.4 8.4 6.4 Z'),
                ('r', 'M16.4 8.4 C19.4 8.2 21.2 6.6 21.4 3.8 C19.8 5.6 18 6.4 15.6 6.4 Z')],
    'fruta': [('r', 'M12 8 C9 5.6 4.6 7 4.6 12 C4.6 16.5 7.6 20.5 9.8 20.5 C10.9 20.5 11.2 20 12 20 C12.8 20 13.1 20.5 '
                    '14.2 20.5 C16.4 20.5 19.4 16.5 19.4 12 C19.4 7 15 5.6 12 8 Z'),
              ('r', 'M12.6 7.2 C12.8 4.8 14.6 3.2 17.2 3 C17 5.6 15.2 7.1 12.6 7.2 Z')],
    'vid': [('c', [(7.6, 9.2, 2.3), (12, 9.2, 2.3), (16.4, 9.2, 2.3), (9.8, 13.2, 2.3), (14.2, 13.2, 2.3), (12, 17.2, 2.3)]),
            ('t', 'M12 6.8 V3.4 M12 4.6 C13.6 3.4 15.6 3.4 17 4.4')],
    'hortalizas': [('r', 'M14.2 6.8 L18.2 10.8 L7.2 20.4 C6 21.4 4.4 19.8 5.4 18.6 Z'),
                   ('t', 'M16.2 8.8 L19.6 3.6 M17.2 9.8 L21.4 7 M15.2 7.8 L15.2 3')],
    'forestal': [('r', 'M12 2.6 L17.6 10 H14.6 L19.2 16.2 H13.3 V21.2 H10.7 V16.2 H4.8 L9.4 10 H6.4 Z')],
    'frigorificos': [('t', 'M12 3 V21 M4.2 7.5 L19.8 16.5 M4.2 16.5 L19.8 7.5 M9.6 4.4 L12 6.6 L14.4 4.4 M9.6 19.6 L12 17.4 L14.4 19.6 '
                           'M4.2 10.6 L7.2 9.4 L6.6 6.4 M19.8 13.4 L16.8 14.6 L17.4 17.6 M4.2 13.4 L7.2 14.6 L6.6 17.6 M19.8 10.6 L16.8 9.4 L17.4 6.4')],
    'alojamiento': [('r', 'M2.8 18.8 V6.4 H5 V13 H21.2 V18.8 H19 V16.2 H5 V18.8 Z'),
                    ('r', 'M6.2 9.6 H10.6 V12.2 H6.2 Z M11.6 9.2 H18.4 C20 9.2 21.2 10.4 21.2 12 H11.6 Z')],
    'esqui': [('r', 'M1.8 19.6 L8.6 7.6 L12.4 13.2 L15.4 9.2 L22.2 19.6 Z'),
              ('t', 'M6.6 11.2 L8.6 12.6 L10.4 11.2')],
    'pesca': [('r', 'M2.6 12 C6.6 6.4 12.6 6 16.4 10 L20.8 6.6 V17.4 L16.4 14 C12.6 18 6.6 17.6 2.6 12 Z')],
    'construccion': [('r', 'M3.6 16.4 H20.4 V18.6 H3.6 Z M5.6 16.4 C5.6 11.4 8.2 8.6 12 8.6 C15.8 8.6 18.4 11.4 18.4 16.4 Z'),
                     ('r', 'M10.8 6 H13.2 V10 H10.8 Z')],
    'transporte': [('r', 'M1.8 7.4 H14 V16.2 H1.8 Z M14.8 10.2 H18.4 L21.6 13.6 V16.2 H14.8 Z'),
                   ('c', [(6, 17.6, 2), (17.6, 17.6, 2)])],
    'tecnicos': [('r', 'M4 20.4 V3.6 L20.4 20.4 Z M7 17.4 H13.2 L7 11.2 Z')],
}

# Al cultivo o trabajo de una fila de calendario le corresponde el glifo de un sector de la matriz
EQUIVALENTE = {'turismo': 'alojamiento', 'esqui': 'esqui'}


def pictograma(clave):
    clave = EQUIVALENTE.get(clave, clave)
    partes = []
    for tipo, datos in DIBUJOS[clave]:
        if tipo == 'c':
            partes += [f'<circle class="dibujo" cx="{x}" cy="{y}" r="{r}"/>' for x, y, r in datos]
        elif tipo == 't':
            partes.append(f'<path class="trazo" d="{datos}"/>')
        else:
            partes.append(f'<path class="dibujo" fill-rule="evenodd" d="{datos}"/>')
    return ''.join(partes)


def glifo_svg(clave, x, y, radio):
    """Glifo centrado en (x, y), en las unidades del SVG que lo contiene."""
    k = radio / 12
    clave = EQUIVALENTE.get(clave, clave)
    return (f'<g class="glifo g-{clave}" transform="translate({x - radio:.2f} {y - radio:.2f}) scale({k:.4f})">'
            f'<circle class="fondo" cx="12" cy="12" r="12"/>'
            f'<g transform="translate(12 12) scale(0.7) translate(-12 -12)">{pictograma(clave)}</g></g>')


def glifo_html(clave, mm=5):
    """Glifo suelto para tablas y leyendas (un <svg> de mm × mm)."""
    return (f'<svg class="glifo-suelto" viewBox="0 0 24 24" style="width:{mm}mm;height:{mm}mm">'
            + glifo_svg(clave, 12, 12, 12) + '</svg>')
