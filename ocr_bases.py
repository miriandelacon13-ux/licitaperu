"""OCR de las páginas escaneadas de unas bases en PDF, con PaddleOCR (Document AI, sesión 10 del curso).

Muchas bases del SEACE mezclan páginas con texto y páginas que son imágenes (por ejemplo, el requerimiento
escaneado). Este script detecta esas páginas con evaluador.leer_pdf, extrae la imagen incrustada (sin renderizar el
PDF) y guarda el texto de cada una en datos/ocr/<huella del PDF>/pNN.json. La app usa esa caché al evaluar.

Es lento en CPU (unos 2 minutos por página), por eso va aparte y con caché por página:

    uv sync --group ocr
    uv run --group ocr python ocr_bases.py docs/bases/archivo.pdf [--paginas 50 51]

Configuración igual a la Tarea 2: PP-OCRv6 en español, sin módulos geométricos y sin oneDNN (paddlepaddle 3.3.1
falla en CPU con oneDNN).
"""
import argparse
import json
import time
from pathlib import Path

import evaluador

RAIZ = Path(__file__).resolve().parent
CONFIG = {"lang": "es", "use_doc_orientation_classify": False, "use_doc_unwarping": False,
          "use_textline_orientation": False, "enable_mkldnn": False}
MODELO = "PaddleOCR 3.7 · PP-OCRv6_medium (det + rec), español"


def carpeta_ocr(datos: bytes) -> Path:
    return RAIZ / "datos" / "ocr" / evaluador.huella(datos)


def main():
    import numpy as np
    from paddleocr import PaddleOCR
    from PIL import Image
    from pypdf import PdfReader
    import io

    args = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    args.add_argument("pdf", type=Path)
    args.add_argument("--paginas", type=int, nargs="*", help="solo estas páginas (por defecto, las que no tienen texto)")
    a = args.parse_args()
    datos = a.pdf.read_bytes()
    lectura = evaluador.leer_pdf(datos)
    pendientes = a.paginas or lectura["sin_texto"]
    destino = carpeta_ocr(datos)
    destino.mkdir(parents=True, exist_ok=True)
    print(f"{a.pdf.name}: {len(lectura['paginas'])} páginas; sin texto: {lectura['sin_texto']}; OCR de {pendientes}")
    lector = PdfReader(io.BytesIO(datos))
    motor = None
    for n in pendientes:
        salida = destino / f"p{n:02d}.json"
        if salida.exists():
            continue
        imagenes = list(lector.pages[n - 1].images)
        if not imagenes:
            print(f"p{n}: sin imagen incrustada; se omite")
            continue
        imagen = max(imagenes, key=lambda im: len(im.data))   # la página escaneada es la imagen más grande
        if motor is None:
            motor = PaddleOCR(**CONFIG)
        rgb = np.array(Image.open(io.BytesIO(imagen.data)).convert("RGB"))
        t = time.perf_counter()
        r = motor.predict(rgb[:, :, ::-1].copy())[0]   # PaddleX espera BGR
        lineas = [{"texto": tx, "confianza": round(float(sc), 4)} for tx, sc in zip(r["rec_texts"], r["rec_scores"])]
        salida.write_text(json.dumps({"pagina": n, "modelo": MODELO, "segundos": round(time.perf_counter() - t, 1),
                                      "imagen": f"{imagen.name} {Image.open(io.BytesIO(imagen.data)).size}",
                                      "lineas": lineas}, ensure_ascii=False), encoding="utf-8")
        print(f"p{n}: {len(lineas)} líneas en {time.perf_counter() - t:.0f} s", flush=True)


if __name__ == "__main__":
    main()
