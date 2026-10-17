#!/usr/bin/env node
// Construye hojas imprimibles: HTML -> chequeo -> PDF -> vista previa -> tinta.
//
//   node herramientas/construir.mjs hojas/ing-t/ING-T-01.html [otra.html ...] [--forzar] [--detalle]
//
// Pasos por cada archivo:
//   1. Abre la hoja en Chromium y mide la maquetación real:
//        ERRORES (frenan la construcción)
//          texto-chico      letra de lectura por debajo de 10 pt, o metadato por
//                           debajo de 8 pt (metadatos: pie, códigos, referencias,
//                           etiquetas dentro de diagramas SVG, [data-meta])
//          texto-encimado   dos textos se pisan
//          texto-cortado    un texto queda cortado por su caja
//          fuera-de-margen  texto a menos de 8 mm del borde de la hoja
//          sin-hoja         el archivo no tiene ningún elemento .hoja
//        AVISOS (se revisan a ojo)
//          casi-encimado    dos textos casi se tocan
//   2. Si no hay errores (o con --forzar), genera el PDF en salida/.
//   3. Rasteriza el PDF y mide:
//          tinta            densidad media de tinta por hoja (objetivo <= 20 %,
//                           o el valor de data-tinta-max en la .hoja)
//          borde            cualquier tinta a menos de 8 mm del borde = error
//   4. Deja una vista previa PNG en salida/previas/ para revisar a ojo.
//
// Las mediciones de maquetación están adaptadas de check.mjs de
// EpicInfographics (MIT, (c) 2026 epic-infographics contributors); ver
// herramientas/LICENCIA-epicinfographics.txt.

import { chromium } from 'playwright-core';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { resolve, basename, dirname, relative, join } from 'node:path';
import { mkdirSync, readFileSync, existsSync, rmSync, readdirSync } from 'node:fs';
import { execFileSync } from 'node:child_process';

const RAIZ = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const CHROMIUM = process.env.CHROMIUM_PATH || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';

const PX_POR_MM = 96 / 25.4;
const PX_POR_PT = 96 / 72;
// Calibración CAL-01 (2026-10-16): el texto más chico cómodo a 40 cm es 10 pt.
const LETRA_MIN_PT = 10;       // texto de lectura: error por debajo
const LETRA_META_PT = 8;       // metadatos: error por debajo
const SELECTOR_META = '.pie, .ref, .ver, .etiqueta-corr, .codigo, .coleccion, .cabecera .lateral, svg, sup, [data-meta]';
const MARGEN_SEGURO_MM = 8;    // nada a menos de esto del borde
const TINTA_MAX_DEFECTO = 20;  // % de densidad media

const args = process.argv.slice(2);
const forzar = args.includes('--forzar');
const detalle = args.includes('--detalle');
const archivos = args.filter((a) => !a.startsWith('--'));
if (!archivos.length) {
  console.error('Uso: node herramientas/construir.mjs hojas/<carpeta>/<HOJA>.html [...] [--forzar]');
  process.exit(2);
}

const navegador = await chromium.launch({ executablePath: CHROMIUM });
let totalErrores = 0;
const resumen = [];

try {
  for (const archivo of archivos) {
    const ruta = resolve(archivo);
    const nombre = basename(ruta, '.html');
    const carpeta = basename(dirname(ruta));
    const dirSalida = join(RAIZ, 'salida', carpeta);
    const dirPrevias = join(RAIZ, 'salida', 'previas');
    mkdirSync(dirSalida, { recursive: true });
    mkdirSync(dirPrevias, { recursive: true });

    console.log(`\n== ${relative(RAIZ, ruta)}`);
    const pagina = await navegador.newPage({ viewport: { width: 1200, height: 1200 } });
    await pagina.goto(pathToFileURL(ruta).href, { waitUntil: 'networkidle' });
    await pagina.evaluate(() => document.fonts.ready);
    await pagina.waitForTimeout(150);

    const informe = await pagina.evaluate(medirMaquetacion, {
      PX_POR_MM, PX_POR_PT, LETRA_MIN_PT, LETRA_META_PT, SELECTOR_META, MARGEN_SEGURO_MM,
    });

    for (const e of informe.errores) console.log(`  ✗ ERROR ${e}`);
    for (const a of informe.avisos) console.log(`  ! aviso ${a}`);
    if (detalle) for (const m of informe.metas) console.log(`  · meta ${m}`);
    console.log(`  maquetación: ${informe.errores.length} error(es), ${informe.avisos.length} aviso(s), ${informe.textos} textos medidos, ${informe.hojas.length} hoja(s)`);

    let errores = informe.errores.length;
    if (errores && !forzar) {
      console.log('  → no se genera el PDF: corregí los errores (o usá --forzar para ver la vista previa igual)');
      totalErrores += errores;
      await pagina.close();
      continue;
    }

    const pdf = join(dirSalida, `${nombre}.pdf`);
    await pagina.pdf({ path: pdf, preferCSSPageSize: true, printBackground: true });
    await pagina.close();

    // Tamaño de página real del PDF
    const info = execFileSync('pdfinfo', ['-f', '1', '-l', '999', pdf]).toString();
    const tamanios = [...info.matchAll(/Page\s+\d+ size:\s+([\d.]+) x ([\d.]+) pts/g)].map((m) => [
      (Number(m[1]) / 72) * 25.4, (Number(m[2]) / 72) * 25.4,
    ]);
    tamanios.forEach(([w, h], i) => {
      const a4 = (Math.abs(w - 210) < 0.6 && Math.abs(h - 297) < 0.6) || (Math.abs(w - 297) < 0.6 && Math.abs(h - 210) < 0.6);
      if (!a4) { console.log(`  ✗ ERROR tamaño    página ${i + 1} mide ${w.toFixed(1)} × ${h.toFixed(1)} mm (no es A4)`); errores++; }
    });

    // Rasterizado para tinta y borde (60 ppp alcanza para medir)
    for (const f of readdirSync(dirPrevias)) if (f.startsWith(`${nombre}-`)) rmSync(join(dirPrevias, f));
    const base = join(dirPrevias, `${nombre}-medir`);
    execFileSync('pdftoppm', ['-r', '60', pdf, base], { stdio: 'ignore' });
    const ppms = readdirSync(dirPrevias).filter((f) => f.startsWith(`${nombre}-medir`) && f.endsWith('.ppm')).sort();
    ppms.forEach((f, i) => {
      const { tinta, borde } = medirTinta(join(dirPrevias, f), 60);
      const max = informe.hojas[i]?.tintaMax ?? TINTA_MAX_DEFECTO;
      const marca = tinta > max ? '✗' : '·';
      console.log(`  ${marca} tinta     página ${i + 1}: ${tinta.toFixed(1)} % (máximo ${max} %)`);
      if (tinta > max) errores++;
      if (borde > 0 && !informe.hojas[i]?.bordeOk) {
        console.log(`  ✗ ERROR borde     página ${i + 1}: hay tinta a menos de ${MARGEN_SEGURO_MM} mm del borde (${borde} píxeles)`);
        errores++;
      }
      rmSync(join(dirPrevias, f));
    });

    // Vista previa para revisar a ojo
    execFileSync('pdftoppm', ['-r', '110', '-png', pdf, join(dirPrevias, nombre)], { stdio: 'ignore' });
    console.log(`  PDF: ${relative(RAIZ, pdf)}  ·  vista previa: salida/previas/${nombre}-*.png`);
    totalErrores += errores;
    resumen.push({ hoja: nombre, paginas: tamanios.length, errores, avisos: informe.avisos.length });
  }
} finally {
  await navegador.close();
}

console.log('\nResumen:');
for (const r of resumen) console.log(`  ${r.hoja}: ${r.paginas} pág., ${r.errores} error(es), ${r.avisos} aviso(s)`);
process.exit(totalErrores ? 1 : 0);

// ---------------------------------------------------------------------------
// Densidad de tinta (0–100 %) y píxeles entintados en la franja de borde.
// Lee un PPM binario (P6) generado por pdftoppm.
function medirTinta(ruta, ppp) {
  const buf = readFileSync(ruta);
  let pos = 0;
  const token = () => {
    while (buf[pos] === 0x23 || /\s/.test(String.fromCharCode(buf[pos]))) {
      if (buf[pos] === 0x23) while (buf[pos] !== 0x0a) pos++;
      pos++;
    }
    let s = '';
    while (!/\s/.test(String.fromCharCode(buf[pos]))) s += String.fromCharCode(buf[pos++]);
    return s;
  };
  if (token() !== 'P6') throw new Error(`${ruta} no es PPM P6`);
  const ancho = Number(token()), alto = Number(token());
  token(); // valor máximo
  pos++;
  const franja = Math.round((MARGEN_SEGURO_MM / 25.4) * ppp);
  let suma = 0, borde = 0;
  for (let y = 0; y < alto; y++) {
    for (let x = 0; x < ancho; x++) {
      const i = pos + (y * ancho + x) * 3;
      const r = buf[i], g = buf[i + 1], b = buf[i + 2];
      suma += 765 - (r + g + b);
      if ((x < franja || y < franja || x >= ancho - franja || y >= alto - franja) && Math.min(r, g, b) < 230) borde++;
    }
  }
  return { tinta: (suma / (765 * ancho * alto)) * 100, borde };
}

// ---------------------------------------------------------------------------
// Se ejecuta dentro de la página. Devuelve errores, avisos y datos por hoja.
function medirMaquetacion({ PX_POR_MM, PX_POR_PT, LETRA_MIN_PT, LETRA_META_PT, SELECTOR_META, MARGEN_SEGURO_MM }) {
  const errores = [];
  const avisos = [];
  const hojas = [...document.querySelectorAll('.hoja')].map((el) => ({
    el,
    caja: el.getBoundingClientRect(),
    tintaMax: el.dataset.tintaMax ? Number(el.dataset.tintaMax) : undefined,
    bordeOk: el.hasAttribute('data-borde-ok'),
  }));
  if (!hojas.length) errores.push('sin-hoja         el archivo no tiene ningún elemento con class="hoja"');

  const visible = (el) => {
    for (let n = el; n && n !== document.documentElement; n = n.parentElement) {
      const cs = getComputedStyle(n);
      if (cs.display === 'none' || cs.visibility === 'hidden') return false;
      if (parseFloat(cs.opacity) < 0.05) return false;
    }
    return true;
  };
  const describir = (el) => {
    let sel = el.tagName.toLowerCase();
    if (el.id) sel += `#${el.id}`;
    else if (el.classList.length) sel += '.' + [...el.classList].slice(0, 2).join('.');
    const t = (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 30);
    return t ? `<${sel}> “${t}${t.length === 30 ? '…' : ''}”` : `<${sel}>`;
  };
  const mm = (px) => (px / PX_POR_MM).toFixed(1);

  // Rectángulos ajustados a la tinta real de cada texto (ver check.mjs original)
  const porElemento = new Map();
  const recorrido = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (recorrido.nextNode()) {
    const nodo = recorrido.currentNode;
    if (!nodo.textContent.trim()) continue;
    const el = nodo.parentElement;
    if (!el || !visible(el)) continue;
    (porElemento.get(el) ?? porElemento.set(el, []).get(el)).push(nodo);
  }
  const ctx = document.createElement('canvas').getContext('2d');
  const metricas = (el, texto) => {
    const cs = getComputedStyle(el);
    ctx.font = `${cs.fontStyle} ${cs.fontWeight} ${parseFloat(cs.fontSize)}px ${cs.fontFamily}`;
    const m = ctx.measureText(texto);
    return {
      asc: m.fontBoundingBoxAscent ?? 0, desc: m.fontBoundingBoxDescent ?? 0,
      tintaAsc: m.actualBoundingBoxAscent ?? 0, tintaDesc: m.actualBoundingBoxDescent ?? 0,
      avance: m.width,
    };
  };
  const cajaDe = (pts) => {
    const xs = pts.map((p) => p.x), ys = pts.map((p) => p.y);
    const left = Math.min(...xs), right = Math.max(...xs), top = Math.min(...ys), bottom = Math.max(...ys);
    return { left, right, top, bottom, width: right - left, height: bottom - top };
  };

  const textos = [];
  for (const [el, nodos] of porElemento) {
    const tam = parseFloat(getComputedStyle(el).fontSize);
    let rects = [];
    if (el instanceof SVGElement) {
      try {
        const ctm = el.getScreenCTM();
        const n = el.getNumberOfChars();
        const chars = el.textContent;
        if (ctm && n) {
          for (let i = 0; i < n; i++) {
            const ch = chars[i];
            if (!ch || !ch.trim()) continue;
            const ext = el.getExtentOfChar(i);
            const m = metricas(el, ch);
            const rot = (el.getRotationOfChar(i) * Math.PI) / 180;
            const cx = ext.x + ext.width / 2, cy = ext.y + ext.height / 2;
            const off = (m.asc - m.desc) / 2, w2 = m.avance / 2;
            const cos = Math.cos(rot), sin = Math.sin(rot);
            const pts = [[-w2, off - m.tintaAsc], [w2, off - m.tintaAsc], [-w2, off + m.tintaDesc], [w2, off + m.tintaDesc]]
              .map(([x, y]) => {
                const rx = cx + x * cos - y * sin, ry = cy + x * sin + y * cos;
                return { x: ctm.a * rx + ctm.c * ry + ctm.e, y: ctm.b * rx + ctm.d * ry + ctm.f };
              });
            rects.push(cajaDe(pts));
          }
        }
      } catch { /* no es texto SVG */ }
      if (!rects.length) rects = [el.getBoundingClientRect()];
    } else {
      let ang = 0;
      for (let n = el; n && n !== document.documentElement; n = n.parentElement) {
        const t = getComputedStyle(n).transform;
        if (t && t !== 'none') { const m = new DOMMatrix(t); ang += Math.atan2(m.b, m.a) * 180 / Math.PI; }
      }
      if (getComputedStyle(el).writingMode.startsWith('vertical')) ang += 90;
      const norm = ((Math.round(ang) % 360) + 360) % 360;
      const derecho = norm % 180 < 3 || norm % 180 > 177;
      const deCostado = Math.abs((norm % 180) - 90) < 3;
      const texto = nodos.map((n) => n.textContent).join(' ').trim();
      const m = metricas(el, texto);
      const aireArriba = Math.max(0, m.asc - m.tintaAsc), aireAbajo = Math.max(0, m.desc - m.tintaDesc);
      let iL = 0, iR = 0, iT = 0, iB = 0;
      if (derecho) { iT = aireArriba; iB = aireAbajo; }
      else if (deCostado) { iL = iR = (aireArriba + aireAbajo) / 2; }
      else { iL = iR = iT = iB = (aireArriba + aireAbajo) / 2; }
      for (const nodo of nodos) {
        const rango = document.createRange();
        rango.selectNodeContents(nodo);
        for (const r of rango.getClientRects()) {
          const left = r.left + Math.min(iL, r.width / 3), right = r.right - Math.min(iR, r.width / 3);
          const top = r.top + Math.min(iT, r.height / 3), bottom = r.bottom - Math.min(iB, r.height / 3);
          rects.push({ left, right, top, bottom, width: right - left, height: bottom - top });
        }
      }
    }
    rects = rects.filter((r) => r.width > 0.5 && r.height > 0.5);
    if (!rects.length) continue;
    textos.push({ el, rects, tam, area: rects.reduce((s, r) => s + r.width * r.height, 0) });
  }

  // Tamaño de letra (en pt reales; las transformaciones SVG escalan la letra)
  const metas = [];
  for (const { el, tam } of textos) {
    let escala = 1;
    if (el instanceof SVGElement) {
      const ctm = el.getScreenCTM();
      if (ctm) escala = Math.hypot(ctm.a, ctm.b);
    }
    const pt = (tam * escala) / PX_POR_PT;
    if (el.closest('[data-letra-ok]')) continue;
    const esMeta = !!el.closest(SELECTOR_META);
    const minimo = esMeta ? LETRA_META_PT : LETRA_MIN_PT;
    if (pt < minimo - 0.05) errores.push(`texto-chico      ${describir(el)} mide ${pt.toFixed(1)} pt (mínimo ${minimo} pt${esMeta ? ', metadato' : ''})`);
    else if (esMeta && pt < LETRA_MIN_PT - 0.05) metas.push(`${describir(el)} ${pt.toFixed(1)} pt`);
  }

  // Margen de seguridad respecto del borde de su hoja
  const franja = MARGEN_SEGURO_MM * PX_POR_MM;
  for (const { el, rects } of textos) {
    if (el.closest('[data-borde-ok]')) continue;
    const r0 = rects[0];
    const hoja = hojas.find((h) => r0.top >= h.caja.top - 1 && r0.top <= h.caja.bottom + 1 && r0.left >= h.caja.left - 1 && r0.left <= h.caja.right + 1);
    if (!hoja) { errores.push(`fuera-de-margen  ${describir(el)} está fuera de toda hoja`); continue; }
    const c = hoja.caja;
    const malo = rects.find((r) => r.left < c.left + franja || r.top < c.top + franja || r.right > c.right - franja || r.bottom > c.bottom - franja);
    if (malo) {
      const d = Math.min(malo.left - c.left, malo.top - c.top, c.right - malo.right, c.bottom - malo.bottom);
      errores.push(`fuera-de-margen  ${describir(el)} queda a ${mm(d)} mm del borde (mínimo ${MARGEN_SEGURO_MM} mm)`);
    }
  }

  // Contenido que se sale por debajo del cuerpo: un recuadro con fondo puede tapar
  // el pie sin que ningún texto se encime con otro, así que se mide cada caja
  for (const cuerpo of document.querySelectorAll('.hoja .cuerpo')) {
    const limite = cuerpo.getBoundingClientRect().bottom;
    const pie = cuerpo.closest('.hoja').querySelector('.pie');
    const techoPie = pie ? pie.getBoundingClientRect().top : limite;
    let peor = null, fondo = limite + 0.5 * PX_POR_MM;
    for (const el of cuerpo.querySelectorAll('*')) {
      const b = el.getBoundingClientRect();
      if (b.height > 0 && b.bottom > fondo && visible(el)) { fondo = b.bottom; peor = el; }
    }
    if (!peor) continue;
    if (fondo > techoPie + 0.3 * PX_POR_MM) errores.push(`desborde         ${describir(peor)} se sale ${mm(fondo - limite)} mm del cuerpo y entra ${mm(fondo - techoPie)} mm en el pie`);
    else avisos.push(`casi-desborde    ${describir(peor)} se sale ${mm(fondo - limite)} mm del cuerpo (se come el aire antes del pie)`);
  }

  // Texto cortado por una caja con overflow oculto (salvo la propia .hoja, que ya cubre el margen)
  for (const { el, rects } of textos) {
    if (el instanceof SVGElement) continue;
    for (let anc = el; anc && anc !== document.body; anc = anc.parentElement) {
      if (anc.classList.contains('hoja')) break;
      const cs = getComputedStyle(anc);
      const corta = (v) => v === 'hidden' || v === 'clip' || v === 'scroll' || v === 'auto';
      if (!corta(cs.overflowX) && !corta(cs.overflowY)) continue;
      const b = anc.getBoundingClientRect();
      const cortado = rects.some((r) =>
        (corta(cs.overflowX) && (r.left < b.left - 2 || r.right > b.right + 2)) ||
        (corta(cs.overflowY) && (r.top < b.top - 2 || r.bottom > b.bottom + 2)));
      if (cortado) { errores.push(`texto-cortado    ${describir(el)} queda cortado por ${describir(anc)}`); break; }
    }
  }

  // Textos encimados
  const vistos = new Set();
  for (let i = 0; i < textos.length; i++) {
    for (let j = i + 1; j < textos.length; j++) {
      const a = textos[i], b = textos[j];
      if (a.el.contains(b.el) || b.el.contains(a.el)) continue;
      let inter = 0;
      for (const ra of a.rects) for (const rb of b.rects) {
        const w = Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left);
        const h = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top);
        if (w < 2 || h < 2) continue;
        inter += w * h;
      }
      if (!inter) continue;
      const prop = inter / Math.min(a.area, b.area);
      if (prop < 0.05) continue;
      const clave = `${describir(a.el)}|${describir(b.el)}`;
      if (vistos.has(clave)) continue;
      vistos.add(clave);
      if (a.el.closest('[data-encimado-ok]') || b.el.closest('[data-encimado-ok]')) continue;
      const linea = `${describir(a.el)} y ${describir(b.el)} (${Math.round(prop * 100)} % del menor tapado)`;
      if (prop >= 0.12) errores.push(`texto-encimado   ${linea}`);
      else avisos.push(`casi-encimado    ${linea}`);
    }
  }

  return {
    errores, avisos, metas, textos: textos.length,
    hojas: hojas.map((h) => ({ tintaMax: h.tintaMax, bordeOk: h.bordeOk })),
  };
}
