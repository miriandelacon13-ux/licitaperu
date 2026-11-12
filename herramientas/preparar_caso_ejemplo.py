"""Genera caso_ejemplo/mml_lp-sm-16-2026.json: el caso de la MML que la app muestra con «Ver caso de ejemplo».

Usa la extracción guardada (bitácora local, sin volver a llamar al modelo), vuelve a comprobar cada cita contra el PDF
local y su OCR, y guarda solo lo publicable: la ficha pública del SEACE, datos del PDF (páginas, versión, OCR) y los
requisitos con sus citas breves de las bases (documento oficial público) y sus estados. No guarda el PDF, el texto
completo ni la bitácora. Así el caso funciona en la nube sin el PDF, sin OCR en vivo y sin clave de API.

Requiere en esta computadora: docs/bases/LP-SM-16-2026-MML-OGA-OL-1_bases.pdf, datos/ocr/ y registros/llamadas_ia.jsonl.
Desde la raíz:  uv run python herramientas/preparar_caso_ejemplo.py
"""
import gzip
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import evaluador  # noqa: E402
import radar  # noqa: E402

CODIGO = "LP-SM-16-2026-MML-OGA-OL-1"
PDF = RAIZ / "docs" / "bases" / f"{CODIGO}_bases.pdf"
CAMPOS_REQUISITO = ["requisito", "que_se_pide", "momento", "pagina", "seccion", "fragmento", "ambiguo", "nota", "estado",
                    "verificacion", "origen"]
CAMPOS_RESPALDO = ["dato", "pagina", "seccion", "fragmento", "estado", "verificacion", "origen"]
# Lo que no debe publicarse: correos, teléfonos, DNI y los nombres de las firmas digitales que trae el PDF.
PROHIBIDO = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|\b9\d{8}\b|\bDNI\s*N?°?\s*\d{8}\b|BOGDANOVICH|Firmado digitalmente", re.I)


def main():
    lectura = evaluador.aplicar_ocr(evaluador.leer_pdf(PDF.read_bytes()))
    guardada = evaluador.ultima_extraccion(lectura["huella"])
    if not guardada:
        sys.exit("No hay una extracción guardada para este PDF en registros/llamadas_ia.jsonl")
    requisitos = evaluador.verificar(guardada["requisitos"], lectura["paginas"], lectura["ocr"])
    with gzip.open(radar.RESPALDO, "rt", encoding="utf-8") as f:
        filas = [r for r in json.load(f)["filas"] if r.get("nomenclatura") == CODIGO]
    if not filas:
        filas = [r for r in json.loads((RAIZ / "pruebas" / "datos" / "muestra_oportunidades.json")
                                       .read_text(encoding="utf-8")) if r.get("nomenclatura") == CODIGO]
    coincide = evaluador.corresponde(lectura, CODIGO)
    caso = {
        "titulo": "Licitación de materiales ferreteros de la Municipalidad Metropolitana de Lima",
        "codigo": CODIGO,
        "filas_seace": filas,
        "bases": {"documento": coincide["buscado"], "paginas": len(lectura["paginas"]),
                  "menciona_el_numero_en": len(coincide["paginas"]), "huella": lectura["huella"],
                  "creado": lectura["creado"], "integradas": lectura["integradas"],
                  "paginas_imagen": evaluador.rangos(lectura["sin_texto"]), "con_ocr": evaluador.rangos(lectura["ocr"]),
                  "sin_leer": evaluador.rangos(lectura["sin_leer"]) or "ninguna"},
        "extraccion": {"momento": guardada["momento"], "modelo": guardada["modelo"], "segundos": guardada["segundos"],
                       "costo_usd": guardada["costo_usd"], "paginas_enviadas": guardada["paginas_enviadas"],
                       "sin_leer_al_extraer": guardada["sin_leer"], "total_paginas": len(lectura["paginas"])},
        "comprobado": radar.ahora().strftime("%d/%m/%Y %H:%M"),
        "requisitos": [{**{k: r[k] for k in CAMPOS_REQUISITO},
                        "respaldos": [{k: c[k] for k in CAMPOS_RESPALDO} for c in r["respaldos"]]}
                       for r in requisitos]}
    texto = json.dumps(caso, ensure_ascii=False, indent=1)
    hallado = PROHIBIDO.findall(json.dumps(caso["requisitos"], ensure_ascii=False))
    if hallado:
        sys.exit(f"No se guarda: hay datos que no se deben publicar en los requisitos: {hallado}")
    salida = RAIZ / "caso_ejemplo" / "mml_lp-sm-16-2026.json"
    salida.parent.mkdir(exist_ok=True)
    salida.write_text(texto, encoding="utf-8")
    print(f"{salida.relative_to(RAIZ)}: {len(texto):,} caracteres; {len(filas)} fila(s) del SEACE; "
          f"extracción del {guardada['momento']} ({len(guardada['paginas_enviadas'])} páginas, US$ "
          f"{guardada['costo_usd']:.2f}); estados: {[r['estado'] for r in requisitos]}; respaldos verificados: "
          f"{sum(c['estado'] == evaluador.VERIFICADO for r in requisitos for c in r['respaldos'])}/"
          f"{sum(len(r['respaldos']) for r in requisitos)}")


if __name__ == "__main__":
    main()
