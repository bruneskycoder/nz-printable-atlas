# Plan: mapa mural de Nueva Zelanda, versión 2 (`NZ-A-00`)

**Nivel:** profundo. Suma varias fuentes externas (LINZ, DOC, Work and Income, estadísticas sectoriales), una de ellas con clave, y cambia la grilla del mural.
**Estado:** aprobado (2026-10-21), en ejecución.
**Última actualización:** 2026-10-21

## Objetivo

Mejorar el mural `NZ-A-00` (versión 1: 8 A4 apaisados, 1:2.100.000) tomando del brief *Póster cartográfico de Aotearoa New Zealand para Working Holiday* lo que conviene, sin seguirlo a rajatabla.

**Cómo se ve el éxito:** mirándolo seguido, podés
- reconocer las dos islas, las 16 regiones y los 13 parques nacionales;
- ubicar ciudades, la State Highway 1 y el ferry;
- decir en qué regiones conviene investigar cada sector (lechería, ovinos y vacunos, fruta, vid, forestal, turismo) y en qué meses hay temporada;
- todo sin confundir dónde está la actividad con dónde hay vacantes.

## Fuera de alcance

- **Las fichas `NZ-A-01` a `16` y la matriz `NZ-A-99`.** Se actualizan después, con los mismos datos. La única excepción es la línea «Mapa mural: NZ-A-00, pieza N» de cada ficha, que cambia con la grilla nueva.
- **A1 de imprenta.** Elegiste el mural A4 casero. Igual sale, sin costo extra, una vista completa en una sola página, por si algún día lo querés plotear.
- **Límites regionales de Stats NZ 2025.** A esta escala no se distinguen de los de 2017, así que se mantienen los de 2017 y el pie lo aclara.
- **Del brief, no se adopta:**
  - mapa de calor o zonas de «alta demanda»;
  - íconos de construcción, mantenimiento, logística y CAD en cada ciudad (siguen a la población: van como columna y nota);
  - QR;
  - README de fuentes aparte (las fuentes van en el pie, en el README y en los datos JSON);
  - SVG suelto (la fuente editable ya es HTML con SVG).

## Contexto y supuestos

**Hechos verificados (2026-10-21):**
- El mural v1 está en la rama `claude/vibrant-ptolemy-7vl6xb`, que no está fusionada con la principal. Esta rama parte de ahí.
- **Rutas, ríos y lagos de la v1:** salen de Natural Earth 1:10 millones, sin número de ruta. A 1:2.100.000 eso es ampliarlos 5 veces: es el punto más flojo.
- **Lugar libre:** cerca de un cuarto del mural es mar vacío (piezas 3, 5, 6 y 8).
- **Red desde el entorno:**
  - responden Stats NZ, LINZ, DOC, PickNZ e Immigration NZ;
  - Work and Income responde de forma intermitente;
  - Stats NZ y LINZ piden clave para bajar datos (401 y 403 sin clave);
  - el bucket abierto de LINZ con modelos de elevación (`nz-elevation`) responde sin clave.
- **Parques nacionales:** la capa *DOC Public Conservation Land* (ArcGIS, abierta) trae los 13, con `Type = NATIONAL_PARK`, entre ellos Paparoa y Te Papa-Kura-o-Taranaki.
- **Lechería** (LIC/DairyNZ, *NZ Dairy Statistics 2024/25*, tabla 3.1): Waikato tiene el 23,2 % de las vacas; Canterbury, el 20,1 % (North 14,9 + South 5,2); Hawke's Bay, el 0,9 %.
  - Corrige al brief, que incluye Hawke's Bay y nombra Canterbury solo por su parte sur.
- **Vid** (NZ Winegrowers, 2025): Marlborough tiene el 72 % del área en producción, Hawke's Bay alrededor del 11 % y Central Otago alrededor del 5 %.
- **Horticultura:** la encuesta agropecuaria de Stats NZ de 2025 no incluyó preguntas de horticultura. Hay que usar la última edición que sí las tenga, o una fuente de la industria.

**Supuestos:**
- **Clave de LINZ:** va como secreto de GitHub Actions (`LINZ_API_KEY`). La tarea `.github/workflows/linz.yml` baja las capas y las publica en la rama `datos-linz`; desde la sesión solo se leen los datos, nunca la clave.
- **Capas de LINZ** (verificadas en el catálogo el 2026-10-21): la serie Topo 1:500k está discontinuada, así que se usa la 1:250k:
  - rutas (50184, con número de State Highway en `hway_num`);
  - ríos (50182);
  - lagos (50168);
  - costa (51559);
  - nombres del Gazetteer (51681).
  - El pedido está en `datos/nz/linz-pedido.json`.
- **Ovinos y bovinos:** Hawke's Bay y Gisborne están entre las zonas principales de la Isla Norte. Es inferencia; se verifica con Stats NZ.

## Decisiones tomadas con vos

| Tema | Decisión |
|---|---|
| Formato | Mural casero de A4, un poco más grande que la v1 |
| Capa laboral | Matriz región × sector en el mar, más 2 o 3 glifos chicos junto al número de cada región |
| Exactitud | Clave gratuita de LINZ para rutas, ríos, lagos y nombres, cargada como secreto de GitHub |
| Color y tinta | Excepción para el mural: más colores y más tinta, si se entiende mejor y queda más lindo (ver «Paleta del mural») |
| Alcance | Solo el mural; las fichas, después |

## Tamaño: 9 A4 verticales en 3 × 3 (recomendado)

Las tres grillas comparadas usan el mismo margen de 10 mm y la misma solapa de 10 mm que la v1:

| Opción | Hojas | Mural | Escala | Mapa respecto de la v1 | Comentario |
|---|---|---|---|---|---|
| v1 actual: 2 × 4 apaisado | 8 | 54 × 73 cm | 1:2.100.000 | igual | — |
| **A: 3 × 3 vertical** | **9** | **55 × 81 cm** | **1:1.900.000** | **+10 % de lado, +22 % de superficie** | Una hoja más. Queda al 93 % del A1 que pedía el brief |
| B: 4 × 3 vertical | 12 | 73 × 81 cm | 1:1.850.000 | +13 % de lado | Tres hojas más por un 3 % adicional; sobra una columna de mar |
| C: 2 × 5 apaisado | 10 | 54 × 91 cm | 1:1.950.000 | +8 % de lado | Más hojas que A y mapa más chico |

**Criterio dominante:** crecimiento del mapa por hoja agregada. A domina a B y a C.
- **Restricción que impone:** cada panel tiene que entrar entero en una pieza (máximo unos 170 × 255 mm), porque un texto partido por una junta no se lee bien.
- **Dónde caen los paneles:**
  - la pieza 1 (noroeste) y la 9 (sudeste) quedan casi todo mar;
  - la 2 y la 4 (mar de Tasmania) y la 8 tienen bastante mar libre.

## Paleta del mural (excepción a las cuatro tintas)

Pediste más color y más tinta para que se entienda mejor y quede más lindo. Las reglas para el mural:
- **Mar celeste claro.** Los paneles van en recuadros blancos sobre el mar.
- **Tierra en un tono neutro claro**, con relieve sombreado y tintas de altura del ocre al marrón.
- **Parques nacionales en verde**, con trama y borde.
- **Límites de región en violeta.**
- **Rutas:** la State Highway 1 en rojo con borde; las demás State Highways, más finas.
- **Ríos y lagos en azul.**
- **Un color propio por sector, igual en los glifos, la matriz y el calendario.** Siempre con forma y rótulo, para que no dependa solo del color.
- **Tinta:**
  - el límite por pieza pasa del 20 % al 35 %, solo para el mural;
  - las demás hojas siguen con su regla;
  - el chequeo mide cada pieza y frena por encima del 35 %;
  - **riesgo:** el papel de 75 g se puede ondular con tanta tinta; si pasa, conviene papel de 90 g o más.
- **Alcance de los estilos:** van en una clase propia del mural, así las fichas no cambian.

## Reutilización

- `herramientas/generar-atlas.py`, `atlas_nz.py`, `bloques_mural.py`: se usan con la grilla y la escala como parámetros. El corte en piezas, las solapas, las marcas de registro y los bloques en el mar ya existen.
- `herramientas/geo-nz.py`: se le suma la bajada de LINZ y del DOC. Los archivos nuevos van aparte (`datos/nz/linz/`, `datos/nz/parques.json`), así las fichas no cambian hasta que se decida.
- `herramientas/construir.mjs`: el mismo chequeo (10 pt, márgenes, tinta < 20 %, sin encimados).
- `datos/regiones.json`: población del Censo 2023 para la columna «población».
- **Nuevo:**
  - `datos/sectores-nz.json`: cifras por región y sector, cada una con fuente y fecha;
  - `datos/calendario-nz.json`;
  - los bloques de la matriz y del calendario;
  - los glifos de sector.

## Contenido nuevo

1. **Parques nacionales (DOC):** los 13, con trama verde clara y borde verde de trazos.
   - El verde es una excepción explícita a las cuatro tintas: es la convención universal para áreas protegidas y no se confunde con el ocre del relieve.
   - El borde de trazos hace que se lean también en gris.
2. **Rutas de LINZ:** la State Highway 1 más gruesa, con escudos «1», y número en las demás State Highways principales. Ferry Wellington–Picton y aeropuertos, como en la v1.
3. **Ríos y lagos de LINZ 1:500k**, en lugar de Natural Earth.
4. **Rasgos y destinos que faltan**, con nombre oficial del Gazetteer (incluidos los nombres dobles):
   - Tongariro y Ngāuruhoe;
   - glaciares Franz Josef y Fox;
   - Milford Sound / Piopiotahi;
   - Cook Strait;
   - Cape Reinga, Bay of Islands y The Catlins.
   - Opcional, si entran limpios: los centros de esquí principales.
5. **Matriz región × sector** (16 filas):
   - **Población** (Censo 2023): una línea aclara que construcción, mantenimiento, logística y CAD siguen a la población.
   - **Lechería:** % de las vacas.
   - **Ovinos:** % de las ovejas.
   - **Vacunos de carne:** %.
   - **Vid:** % del área en producción.
   - **Fruticultura:** % de las hectáreas.
   - **Forestal:** % de las plantaciones (MPI, por región forestal; las regiones agrupadas comparten celda).
   - **Turismo:** % del gasto turístico.
   - Un sector sin fuente verificable por región (frigoríficos, pesca) no entra a la matriz: va a la nota.
6. **Glifos en el mapa:** junto al número de cada región, como máximo 3. La regla va impresa en la leyenda: «la región tiene el 10 % o más del total nacional del sector».
7. **Calendario:**
   - unas 8 a 10 filas de cultivo o actividad más región (por ejemplo, kiwi en Bay of Plenty: cosecha y poda), sacadas de Work and Income y contrastadas con PickNZ;
   - 12 meses, con fecha de consulta y la leyenda «ventana orientativa; varía según cultivo, clima, empleador y año»;
   - sin franjas nacionales extrapoladas.
8. **Nota visible:** «Sectores y zonas orientativos; no representan vacantes activas, salarios ni garantía de contratación.»
9. **Chequeo de nombres:** todos los rótulos (los 69 de la v1 más los nuevos) se comparan contra el Gazetteer. Las diferencias de grafía o macrones salen en un informe.

## Pasos

- [ ] 1. **Grilla 3 × 3 a 1:1.900.000 con el contenido de la v1.**
  - Relieve recalculado; armado y prueba de unión con las piezas 2 y 3 (la junta cruza Northland).
  - Las fichas solo cambian la referencia a la pieza.
  - Verificación: vista completa sin encimados y ningún bloque partido por una junta.
- [ ] 2. **Parques nacionales del DOC.**
  - Verificación: son 13; los nombres coinciden con el DOC; tinta < 20 % por pieza.
- [ ] 3. **Datos sectoriales con fuente.**
  - Verificación: cada columna suma alrededor de 100 %; el total de vacas coincide con LIC (4.677.580); cada cifra tiene fuente y fecha.
- [ ] 4. **Calendario de Work and Income.**
  - Verificación: cada celda se rastrea hasta la fuente y lleva la fecha de consulta.
- [ ] 5. **Bloques nuevos** (matriz, calendario, leyenda ampliada, nota) **y glifos.**
  - Verificación: el chequeo automático pasa (10 pt, nada a menos de 8 mm del borde, sin encimados).
- [ ] 6. **Rasgos y destinos faltantes.**
  - Verificación: posición contra el Gazetteer o el DOC; ningún rótulo en el mar ni en otra región.
- [ ] 7. **LINZ** (necesita el secreto de GitHub): rutas con número, ríos, lagos, costa y el chequeo de nombres.
  - Verificación: SH1 continua de Cape Reinga a Bluff, con el corte del estrecho; informe de nombres sin diferencias pendientes.
- [ ] 8. **Prueba en gris:** vista previa en escala de grises revisada; rutas, ríos y parques se distinguen.
- [ ] 9. **Exportar:**
  - las 9 piezas, el PDF combinado y la vista completa en PNG;
  - una página única de 55 × 81 cm;
  - README (armado 3 × 3, fuentes) y `PLAN.md` actualizados.

Los pasos 1 a 6 y 8 no dependen de la clave. El 7 empieza cuando la tarea de GitHub deja los datos en la rama `datos-linz`, y después se repiten el 8 y el 9.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| La matriz o el calendario no entran en una pieza (unos 170 × 255 mm). | Partir la matriz por isla, en dos bloques; recortar filas del calendario antes que achicar la letra. |
| Work and Income falla de forma intermitente desde el entorno. | Reintentar. Si no, leerlo por buscador, marcarlo así y revalidarlo antes de imprimir. |
| No hay dato regional de horticultura reciente. | Usar el último disponible, con su año a la vista; si no existe, la columna se va. |
| Las regiones forestales y las de LIC no coinciden con las 16 regiones. | Celdas agrupadas, con nota. |
| Las rutas de LINZ sin número de State Highway. | Identificar la SH1 por nombre o por la red de NZTA; si no se puede, la SH1 va destacada sin escudos. |
| La tinta extra ondula el papel de 75 g. | Límite del 35 % por pieza, medido; si se ondula, papel de 90 g o más. |
| Las fichas dicen «pieza N» con la numeración vieja. | Se regeneran solo para esa línea, con los datos sin tocar. |

## Verificación final

**Automática:**
- el chequeo de `construir.mjs` en las 9 piezas;
- sumas de la matriz y control cruzado con LIC;
- informe de nombres contra el Gazetteer;
- vista previa completa en color y en gris, revisada.

**Manual:**
1. Imprimí las piezas 2 y 3 al 100 % y unilas. Las marcas ▶◀ tienen que quedar desfasadas menos de 1 mm.
2. En la barra de escala, 100 km tienen que medir 52,6 mm con regla.
3. A 1,5 m tenés que distinguir las dos islas, las regiones y los parques en verde.
4. A 40 cm, la matriz y el calendario se tienen que leer cómodos.
5. Hacé una fotocopia en blanco y negro de una pieza. Rutas, ríos y parques se tienen que distinguir.
6. Elegí tres pueblos al azar y comparalos con un mapa en línea. Tienen que estar en el mismo lugar.

## Registro de decisiones y desvíos

- 2026-10-21 — Se analizó el brief contra el mural v1. Se adopta lo que agrega exactitud o utilidad; se descarta lo que repite, satura o no se puede verificar (ver «Fuera de alcance»).
- 2026-10-21 — Formato: mural A4 en 3 × 3 vertical a 1:1.900.000, en lugar del A1 del brief. Elegiste A4 «un poco más grande»; de las tres grillas medidas, es la que más agranda el mapa por hoja.
- 2026-10-21 — Capa laboral: matriz con porcentajes oficiales y glifos con regla impresa. El brief pedía íconos por zona, pero la ubicación de un ícono dentro de una región sugiere una precisión que el dato no tiene.
- 2026-10-21 — Plan aprobado. Excepción de color y tinta para el mural (ver «Paleta del mural»).
- 2026-10-21 — La clave de LINZ va como secreto de GitHub Actions, no del entorno. Es más simple de cargar y no hace falta una sesión nueva.
- 2026-10-21 — LINZ discontinuó la serie 1:500k: se usa la 1:250k (CC BY 4.0) y se simplifica.
