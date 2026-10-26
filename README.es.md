# Atlas imprimible de Nueva Zelanda

Un atlas para imprimir de las 16 regiones de Nueva Zelanda, pensado para quienes llegan con la visa working holiday. Tiene un mapa mural en nueve A4, una ficha doble faz por región, una página para decidir adónde ir y un cuadernillo con todas las fuentes. Todo se genera con Python a partir de datos abiertos, y cada hoja pasa un control automático antes de convertirse en PDF.

*Read in English: [README.md](README.md).*

![El mapa mural armado](docs/img/mural.jpg)

## Qué trae

| Archivo | Qué es |
|---|---|
| [`salida/nz-a/NZ-A-00-1.pdf` … `9`](salida/nz-a/) | **Mapa mural**: 9 A4 verticales (3 × 3) con franjas para pegar. Armado mide unos 57 × 83 cm. En inglés. |
| [`salida/MAPA-MURAL-NZ-una-pagina.pdf`](salida/MAPA-MURAL-NZ-una-pagina.pdf) | El mismo mural en una sola página de 57 × 83 cm, para una imprenta. |
| [`salida/nz-a/NZ-A-01.pdf` … `16`](salida/nz-a/) | **Fichas regionales** en A4 doble faz, de Northland (01) a Southland (16). Nombres en inglés y explicaciones en castellano. |
| [`salida/nz-a/NZ-A-99.pdf`](salida/nz-a/NZ-A-99.pdf) | **¿Dónde ir?** Las 16 regiones en una página apaisada, con semáforo y lugar para tu nota. |
| [`salida/nz-a/NZ-A-fuentes.pdf`](salida/nz-a/NZ-A-fuentes.pdf) | **Fuentes y métodos**: cada fuente numerada de las fichas, con su enlace, y cómo se calculó cada dato. |

**Mapa mural:**
- relieve con tintas de altura, las 16 regiones, los parques nacionales, las State Highways con su número, lagos, ríos y el ferri;
- un glosario de nombres māori que vas a ver en los carteles;
- bloques de curiosidades (el kiwi, la falla alpina, Taupō, el slang);
- el kiwi de Keulemans y un kiwifruit dibujados a lápiz.

**Ficha regional:**
- Frente: población y superficie, mapa con relieve y lugares numerados, cultura māori, y una curiosidad verificada con un dibujo a lápiz hecho sobre una lámina histórica.
- Dorso:
  - los sectores en los que la región se destaca en el país;
  - el trabajo de temporada por mes, según el calendario de Work and Income, con los cultivos por zona, los requisitos y qué conviene preguntar;
  - vivienda: el alquiler típico de la región, una habitación en un barrio céntrico y su equivalente en horas de salario mínimo;
  - el clima;
  - las distancias por ruta a las ciudades vecinas y el transporte.

![Una ficha regional, frente y dorso](docs/img/ficha-canterbury.jpg)

![La página de decisión](docs/img/decision.jpg)

## Cómo está hecho

```
datos abiertos ──► herramientas/*.py ──► datos/ (JSON) ──► generar-atlas.py ──► hojas/nz-a/*.html ──► construir.mjs ──► salida/*.pdf
```

- **Las hojas son HTML con SVG.**
  - Los mapas se dibujan en NZTM2000 (EPSG:2193) con Shapely y pyproj.
  - El relieve sale de un ráster maestro remuestreado.
  - Los rótulos se ubican con un colocador que evita choques.
- **`herramientas/construir.mjs` abre cada hoja en Chromium (Playwright) y no genera el PDF si la maquetación falla.** Marca como error:
  - letra de lectura de menos de 10 pt, o metadatos de menos de 8 pt;
  - texto a menos de 8 mm del borde;
  - textos que se pisan o quedan cortados;
  - imágenes de menos de 150 ppp;
  - más tinta que el límite de la hoja.
- **Cada dato de las fichas dice de qué tipo es:** dato oficial, estimación, cálculo, recomendación u orientativo. Además lleva un número de fuente; `NZ-A-fuentes` tiene la lista completa con enlaces.
- **Las fichas se ajustan solas.** Si el frente o el dorso no entra, el generador achica el mapa o saca un puesto de la lista, y guarda el resultado en `datos/nz/fichas-ajuste.json`.

| Script | Qué hace |
|---|---|
| `geo-nz.py` | Geografía base: regiones, lagos y ríos de Natural Earth, parques nacionales del DOC y relieve de Terrain Tiles |
| `linz-bajar.py` + `.github/workflows/linz.yml` | Baja capas de LINZ Topo 1:250k (rutas, lagos, nombres) con el secreto `LINZ_API_KEY` y las publica en la rama huérfana `datos-linz` |
| `linz-procesar.py` | Convierte esas capas en datos del mapa y compara cada rótulo con el Gazetteer de NZ |
| `sectores-nz.py` | La parte de cada región en el total nacional de cada sector (Stats NZ, vía Figure.NZ) |
| `calendario-nz.py` | El calendario de temporada de Work and Income, con todos los cultivos de cada región |
| `distancias-nz.py` | Distancias por ruta: el camino más corto sobre la red de rutas de LINZ |
| `imagenes.py` | Busca, baja y prepara láminas con licencia abierta (Wikimedia Commons, Internet Archive, Openverse y el Met), y registra su licencia y atribución |
| `generar-atlas.py` | `mural`, `fichas` o `matriz`: escribe las hojas en `hojas/nz-a/` (`fichas` también escribe `NZ-A-fuentes`) |
| `construir.mjs` | Control, PDF, vista previa y cobertura de tinta |

## Hecho con Claude Code

Lo construyo con Claude Code. Tengo un perfil técnico orientado a la construcción y bases de programación, y sigo aprendiendo, pero el código de acá lo escribe Claude. Yo decidí qué hacía falta: un atlas por regiones para ayudar a elegir adónde ir con una Working Holiday, un mural y una ficha por región, y una fuente para cada cifra. Claude escribió los scripts y las hojas y los fue probando. El resultado lo verifico con los chequeos de impresión que se describen arriba, que frenan la construcción si la maquetación falla, no leyendo el código.

## Generarlo vos

Necesitás Python 3.11 o más (probado con 3.13) y Node 18 o más (probado con 22).

```bash
pip install -r requirements.txt
npm install
export CHROMIUM_PATH=/ruta/a/chromium       # cualquier Chromium que Playwright pueda manejar

python3 herramientas/generar-atlas.py mural    # NZ-A-00, las 9 piezas del mural
python3 herramientas/generar-atlas.py fichas   # NZ-A-01 a 16 y NZ-A-fuentes
python3 herramientas/generar-atlas.py matriz   # NZ-A-99
node herramientas/construir.mjs hojas/nz-a/NZ-A-14.html   # → salida/nz-a/NZ-A-14.pdf
```

Los datos ya procesados están en el repositorio, así que esos comandos funcionan sin conexión.

**Para actualizar los datos:**
- Volvé a correr los scripts de datos. Bajan lo que necesitan a `cache/`, que no se sube.
- Para las capas de LINZ, cargá una clave de LINZ Data Service como secreto `LINZ_API_KEY` del repositorio y corré la tarea «Datos de LINZ».
- `distancias-nz.py` y `linz-procesar.py` leen esa rama con `git fetch origin datos-linz`.

## Datos y límites

- **Fecha de consulta:** las fuentes se consultaron el 21 y el 22 de octubre de 2026.
- **Alquileres:** Tenancy Services advierte que sus datos de bonos son provisorios mientras migra de sistema.
- **Meses de temporada:** son los meses en que Work and Income indica trabajo, no fechas de contratación.
- **Temporada de empaque:** ningún organismo publica sus fechas.
- **Clima:** el de cada región se mide en una sola estación.

Son pistas para investigar, no ofertas de trabajo. Revisá los avisos del momento antes de moverte.

## Licencias

- **Código:** MIT (ver [`LICENSE`](LICENSE)). `construir.mjs` adapta `check.mjs` de [EpicInfographics](https://github.com/OrRon/EpicInfographics), con licencia MIT (`herramientas/LICENCIA-epicinfographics.txt`).
- **Mapas, textos, hojas y PDF:** CC BY 4.0, con las excepciones de [`LICENSE-CONTENT.md`](LICENSE-CONTENT.md). Tres dibujos a lápiz siguen siendo CC BY-SA, porque los escaneos de origen lo son.
- **Tipografías:** Inter, Bitter, Source Sans 3 y Courier Prime, con licencia SIL Open Font License; Special Elite, con licencia Apache 2.0 (`fuentes/`).

**Créditos de datos:**
- LINZ (CC BY 4.0);
- Stats NZ (CC BY 4.0; límites regionales vía geoBoundaries);
- Natural Earth (dominio público);
- DOC (CC BY 4.0);
- Terrain Tiles (Mapzen, con el modelo de elevación de LINZ, SRTM y ETOPO1);
- NIWA, Tenancy Services, Work and Income, Employment NZ y Tahatū Career Navigator.

Todos están listados con enlace en `NZ-A-fuentes`.
