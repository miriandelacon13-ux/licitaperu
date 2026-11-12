"""Evaluador de requisitos de LicitaPerú: de las bases en PDF a una lista que el proveedor puede marcar.

1. leer_pdf: ¿el PDF tiene texto legible? Página por página, sin contar los encabezados que se repiten (una página
   escaneada suele traer solo el encabezado como texto). También da la fecha de los metadatos y si la portada dice
   «bases integradas».
2. corresponde: ¿el PDF es del proceso elegido? Busca su número (p. ej. «N° 016-2026-MML-OGA-OL»).
3. aplicar_ocr: completa las páginas escaneadas con el texto de PaddleOCR guardado por ocr_bases.py.
4. extraer_requisitos: un LLM con salida estructurada (JSON Schema) devuelve 3 requisitos con qué se pide, en qué
   momento se presenta, la página, la sección y un fragmento literal. Integración local: la CLI de Claude Code
   (`claude -p --json-schema`) con la sesión iniciada en esta computadora; no hay claves en el repo.
5. verificar: cada fragmento debe aparecer tal cual en la página citada; si no, el requisito queda «Por verificar».

Las llamadas al modelo quedan en registros/llamadas_ia.jsonl.
"""
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader

RAIZ = Path(__file__).resolve().parent
BITACORA = RAIZ / "registros" / "llamadas_ia.jsonl"
CARPETA_OCR = RAIZ / "datos" / "ocr"
CLI = os.environ.get("LICITAPERU_CLAUDE_CLI", "claude")
MODELO = "claude-opus-5-5"
SEGUNDOS_MAX = 300
MIN_CARACTERES = 100      # menos que esto (sin encabezados) = página sin texto útil: escaneo, portada o en blanco
VERIFICADO = "Verificado en el texto"
POR_VERIFICAR = "Por verificar"
MOMENTOS = ["Con la oferta", "Para perfeccionar el contrato", "No lo indica"]


class ErrorIA(Exception):
    """El modelo no respondió o su respuesta no sirve; el mensaje es corto para mostrarlo en pantalla."""


def huella(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()[:16]


def rangos(numeros):
    """[1, 28, 29, 30] → "1, 28–30"."""
    grupos, inicio, previo = [], None, None
    for n in sorted(numeros):
        if previo is not None and n == previo + 1:
            previo = n
            continue
        if inicio is not None:
            grupos.append(f"{inicio}–{previo}" if previo != inicio else f"{inicio}")
        inicio = previo = n
    if inicio is not None:
        grupos.append(f"{inicio}–{previo}" if previo != inicio else f"{inicio}")
    return ", ".join(grupos)


# 1 · Lectura

def _clave_linea(linea):
    return re.sub(r"\d+", "#", re.sub(r"\s+", " ", linea)).strip().lower()


def leer_pdf(datos: bytes) -> dict:
    """Texto por página y diagnóstico: estado "legible" | "parcial" | "escaneo" | "ilegible"."""
    base = {"paginas": [], "con_texto": 0, "sin_texto": [], "ocr": [], "estado": "ilegible", "legible": False,
            "evaluable": False, "huella": huella(datos), "creado": None, "integradas": False}
    try:
        lector = PdfReader(io.BytesIO(datos))
        paginas = [(pagina.extract_text() or "") for pagina in lector.pages]
        creado = (lector.metadata or {}).get("/CreationDate") and lector.metadata.creation_date
    except Exception as e:   # PDF dañado o protegido
        return base | {"motivo": f"no se pudo abrir el PDF ({type(e).__name__})"}
    # Encabezados y pies: líneas que se repiten en muchas páginas (con 5 páginas o más) no cuentan como contenido.
    repetidas = set()
    if len(paginas) >= 5:
        veces = Counter(k for t in paginas for k in {_clave_linea(l) for l in t.splitlines() if l.strip()})
        repetidas = {k for k, v in veces.items() if v >= max(3, 0.3 * len(paginas))}
    con_texto, sin_texto, raros = 0, [], 0
    for i, texto in enumerate(paginas, 1):
        propio = "".join(l for l in texto.splitlines() if _clave_linea(l) not in repetidas)
        visibles = re.sub(r"\s", "", propio)
        if len(visibles) < MIN_CARACTERES:
            sin_texto.append(i)
            continue
        con_texto += 1
        if sum(c.isalpha() for c in visibles) / len(visibles) < 0.5 or "(cid:" in texto:
            raros += 1
    total = len(paginas)
    portada = " ".join(paginas[:3])
    base |= {"paginas": paginas, "con_texto": con_texto, "sin_texto": sin_texto,
             "creado": creado.strftime("%d/%m/%Y %H:%M") if creado else None,
             "integradas": bool(re.search(r"bases\s+integradas", portada, re.I))}
    if total == 0:
        return base | {"motivo": "el PDF no tiene páginas"}
    if raros > 0.2 * max(con_texto, 1):
        return base | {"motivo": f"{raros} páginas tienen texto mal codificado"}
    if con_texto == 0:
        return base | {"estado": "escaneo", "motivo": "ninguna página tiene texto: es un escaneo y necesita OCR"}
    if sin_texto:
        return base | {"estado": "parcial", "evaluable": True,
                       "motivo": f"{con_texto} de {total} páginas tienen texto; {len(sin_texto)} son imágenes sin "
                                 f"texto y requieren OCR (páginas {rangos(sin_texto)})"}
    return base | {"estado": "legible", "legible": True, "evaluable": True,
                   "motivo": f"las {total} páginas tienen texto legible"}


# 2 · ¿Es el PDF del proceso?

def corresponde(lectura, codigo):
    """Busca el número del proceso en el PDF: «LP-SM-16-2026-MML-OGA-OL-1» → «016-2026-MML-OGA-OL»."""
    m = re.search(r"-(\d+)-(\d{4})-(.+)-\d+$", codigo.strip())
    if not m:
        return {"corresponde": None, "buscado": codigo, "paginas": []}
    numero, anio, siglas = int(m[1]), m[2], m[3]
    patron = rf"(?<!\d)0*{numero}\s*-\s*{anio}\s*-\s*" + r"\s*-\s*".join(re.escape(s.strip()) for s in siglas.split("-"))
    paginas = [i for i, t in enumerate(lectura["paginas"], 1) if re.search(patron, t, re.I)]
    return {"corresponde": bool(paginas), "buscado": f"N° {numero:03d}-{anio}-{siglas}", "paginas": paginas}


# 3 · OCR guardado

def aplicar_ocr(lectura, carpeta=None):
    """Copia de la lectura con el texto OCR de las páginas escaneadas que ya estén en caché."""
    carpeta = Path(carpeta) if carpeta else CARPETA_OCR / lectura["huella"]
    paginas, hechas = list(lectura["paginas"]), []
    for n in lectura["sin_texto"]:
        archivo = carpeta / f"p{n:02d}.json"
        if archivo.exists():
            lineas = json.loads(archivo.read_text(encoding="utf-8"))["lineas"]
            paginas[n - 1] = "\n".join(l["texto"] for l in lineas)
            hechas.append(n)
    faltan = [n for n in lectura["sin_texto"] if n not in hechas]
    return lectura | {"paginas": paginas, "ocr": hechas, "sin_leer": faltan}


# 4 · Extracción con salida estructurada

ESQUEMA = {
    "type": "object",
    "properties": {"requisitos": {"type": "array", "minItems": 1, "maxItems": 3, "items": {
        "type": "object",
        "properties": {
            "requisito": {"type": "string", "description": "Nombre corto, p. ej. «Experiencia del postor»"},
            "que_se_pide": {"type": "string", "description": "Lo que se exige en concreto: montos, plazos, documentos"},
            "momento": {"type": "string", "enum": MOMENTOS,
                        "description": "Cuándo se presenta, según las bases"},
            "pagina": {"type": "integer", "description": "Número del marcador [PÁGINA n] donde está el fragmento"},
            "seccion": {"type": "string", "description": "Numeral y título de la sección tal como aparecen"},
            "fragmento": {"type": "string", "description": "Cita literal y breve del texto, sin cambiar palabras"},
            "ambiguo": {"type": "boolean", "description": "true si el requisito no es claro o falta un dato"},
            "nota": {"type": "string", "description": "Qué es ambiguo o qué falta; vacío si nada"}},
        "required": ["requisito", "que_se_pide", "momento", "pagina", "seccion", "fragmento", "ambiguo", "nota"],
        "additionalProperties": False}}},
    "required": ["requisitos"], "additionalProperties": False}

SISTEMA = ("Eres analista de contrataciones públicas del Perú. Ayudas a pequeños proveedores a entender qué les piden "
           "las bases de un procedimiento de selección. Solo usas el texto que te entregan; nunca inventas requisitos.")


def _pedido(lectura):
    ocr, sin_leer = set(lectura.get("ocr", [])), set(lectura.get("sin_leer", []))
    bloques = []
    for i, t in enumerate(lectura["paginas"], 1):
        if i in sin_leer:
            bloques.append(f"[PÁGINA {i} · imagen sin texto: no se pudo leer]")
        else:
            bloques.append(f"[PÁGINA {i}{' · texto obtenido por OCR' if i in ocr else ''}]\n{t.strip()}")
    aviso = (f"\nOJO: las páginas {rangos(sin_leer)} son imágenes que no se pudieron leer. Si un requisito remite a "
             "ellas, dilo en la nota y marca ambiguo=true." if sin_leer else "")
    return f"""Estas son las bases de un procedimiento de selección del Estado peruano, página por página:

{chr(10).join(bloques)}
{aviso}
Extrae los 3 requisitos que más ayudan a un pequeño proveedor a decidir si puede postular y qué debe preparar. Prioriza, si aparecen: (1) el requisito de calificación más exigente (por ejemplo, la experiencia del postor con su monto); (2) los documentos obligatorios para que la oferta sea admitida; (3) lo que se exige al ganador para perfeccionar el contrato (por ejemplo, la garantía de fiel cumplimiento).
Para cada uno indica:
- requisito: un nombre corto;
- que_se_pide: lo exigido en concreto (montos, plazos, documentos, anexos), en lenguaje simple;
- momento: "Con la oferta", "Para perfeccionar el contrato" (después de la buena pro) o "No lo indica", según digan las bases;
- pagina: el número n del marcador [PÁGINA n] donde está el fragmento;
- seccion: el numeral y el título tal como aparecen en las bases;
- fragmento: una cita breve (máximo 200 caracteres) copiada literalmente del texto de esa página, sin cambiar ni una palabra;
- ambiguo y nota: si algo no es claro, falta un dato, hay una contradicción o depende de otro documento, ambiguo=true y explica qué en la nota.
No completes con conocimiento general: si no lo ves en el texto, no lo pongas."""


def _registrar(fila):
    BITACORA.parent.mkdir(exist_ok=True)
    with BITACORA.open("a", encoding="utf-8") as f:
        f.write(json.dumps(fila, ensure_ascii=False) + "\n")


def extraer_requisitos(lectura):
    """Llama al modelo con el esquema y devuelve {"requisitos": [...], "modelo", "segundos", "costo_usd"}."""
    if isinstance(lectura, list):   # compatibilidad: lista de páginas
        lectura = {"paginas": lectura}
    cli = shutil.which(CLI)
    if not cli:
        raise ErrorIA("no se encontró la CLI de Claude Code en esta computadora")
    comando = [cli, "-p", "--model", MODELO, "--effort", "low", "--tools", "", "--strict-mcp-config",
               "--no-session-persistence", "--disable-slash-commands", "--output-format", "json",
               "--system-prompt", SISTEMA, "--json-schema", json.dumps(ESQUEMA)]
    inicio = time.perf_counter()
    fila = {"momento": datetime.now().astimezone().isoformat(timespec="seconds"), "modelo_pedido": MODELO,
            "paginas": len(lectura["paginas"]), "huella_pdf": lectura.get("huella"), "ocr": lectura.get("ocr", []),
            "sin_leer": lectura.get("sin_leer", [])}
    with tempfile.TemporaryDirectory() as carpeta:   # carpeta vacía: no se carga ningún CLAUDE.md
        try:
            proceso = subprocess.run(comando, input=_pedido(lectura), capture_output=True, text=True,
                                     encoding="utf-8", timeout=SEGUNDOS_MAX, cwd=carpeta)
        except subprocess.TimeoutExpired:
            _registrar(fila | {"ok": False, "error": "timeout"})
            raise ErrorIA(f"el modelo no respondió en {SEGUNDOS_MAX} s") from None
    fila["segundos"] = round(time.perf_counter() - inicio, 2)
    try:
        salida = json.loads(proceso.stdout)
    except ValueError:
        detalle = ((proceso.stderr or proceso.stdout or "").strip().splitlines() or ["sin salida"])[-1][:150]
        _registrar(fila | {"ok": False, "error": detalle})
        raise ErrorIA(f"respuesta inesperada de la CLI ({detalle})") from None
    estructurada = salida.get("structured_output")
    if salida.get("is_error") or not isinstance(estructurada, dict):
        _registrar(fila | {"ok": False, "error": str(salida.get("result", ""))[:200]})
        raise ErrorIA("el modelo no devolvió la salida estructurada")
    uso = salida.get("modelUsage") or {}
    modelo = max(uso, key=lambda m: uso[m].get("outputTokens", 0)) if uso else MODELO
    _registrar(fila | {"ok": True, "modelo": modelo, "costo_usd": salida.get("total_cost_usd"),
                       "salida": estructurada})
    return {"requisitos": estructurada.get("requisitos", [])[:3], "modelo": modelo, "segundos": fila["segundos"],
            "costo_usd": salida.get("total_cost_usd")}


# 5 · Verificación contra el texto

def _norm(texto):
    sin_tildes = unicodedata.normalize("NFD", str(texto).lower()).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[\"'«»“”‘’…]", " ", sin_tildes)).strip()


def verificar(requisitos, paginas, ocr=()):
    """Agrega «estado», «verificacion» y «origen» a cada requisito: el fragmento debe estar literal en la página."""
    normalizadas = [_norm(p) for p in paginas]
    salida = []
    for r in requisitos:
        r = dict(r)
        fragmento = _norm(r.get("fragmento", "")).strip(" .")
        pagina = r.get("pagina")
        r["origen"] = "texto por OCR" if pagina in ocr else "texto del PDF"
        if r.get("momento") not in MOMENTOS:
            r["momento"] = "No lo indica"
        if len(fragmento) < 15:
            r["estado"], r["verificacion"] = POR_VERIFICAR, "el fragmento es demasiado corto para comprobarlo"
        elif isinstance(pagina, int) and 1 <= pagina <= len(paginas) and fragmento in normalizadas[pagina - 1]:
            if r.get("ambiguo"):
                r["estado"], r["verificacion"] = POR_VERIFICAR, f"el fragmento está en la página {pagina}, pero " \
                                                                f"el requisito es ambiguo: {r.get('nota') or 'sin nota'}"
            else:
                r["estado"] = VERIFICADO
                r["verificacion"] = f"el fragmento aparece literal en la página {pagina} ({r['origen']})"
        else:
            otras = [i for i, t in enumerate(normalizadas, 1) if fragmento in t]
            r["estado"] = POR_VERIFICAR
            r["verificacion"] = (f"el fragmento está en la página {otras[0]}, no en la {pagina}" if otras
                                 else "el fragmento no aparece literal en el documento")
        salida.append(r)
    return salida
