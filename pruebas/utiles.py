"""Ayudas para las pruebas: muestra real de la API y PDF mínimos generados a mano (con texto o en blanco)."""
import json
import textwrap
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent
MUESTRA = AQUI / "datos" / "muestra_oportunidades.json"


def filas_muestra():
    """5 filas reales de la API del SEACE (11-11-2026): MML, MIDAGRI, SEAL, una ya vencida y un servicio."""
    return json.loads(MUESTRA.read_text(encoding="utf-8"))


def momento(texto="11/11/2026 22:30:00"):
    import radar
    return datetime.strptime(texto, "%d/%m/%Y %H:%M:%S").replace(tzinfo=radar.LIMA)


def _escapar(linea):
    return linea.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def pdf(paginas):
    """PDF válido con una página por texto (Helvetica, WinAnsi). Un texto vacío da una página sin texto."""
    n = len(paginas)
    objetos = {1: b"<< /Type /Catalog /Pages 2 0 R >>",
               2: f"<< /Type /Pages /Kids [{' '.join(f'{4 + 2 * i} 0 R' for i in range(n))}] /Count {n} >>".encode(),
               3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"}
    for i, texto in enumerate(paginas):
        lineas = textwrap.wrap(texto, 90) if texto else []
        flujo = ("BT /F1 10 Tf 12 TL 40 800 Td " + " ".join(f"({_escapar(l)}) '" for l in lineas) + " ET"
                 ).encode("cp1252") if lineas else b""
        objetos[4 + 2 * i] = (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                              f"/Resources << /Font << /F1 3 0 R >> >> /Contents {5 + 2 * i} 0 R >>").encode()
        objetos[5 + 2 * i] = b"<< /Length %d >>\nstream\n" % len(flujo) + flujo + b"\nendstream"
    salida = bytearray(b"%PDF-1.4\n")
    posiciones = {}
    for num in sorted(objetos):
        posiciones[num] = len(salida)
        salida += b"%d 0 obj\n" % num + objetos[num] + b"\nendobj\n"
    xref = len(salida)
    salida += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objetos) + 1)
    for num in sorted(objetos):
        salida += b"%010d 00000 n \n" % posiciones[num]
    salida += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objetos) + 1, xref)
    return bytes(salida)
