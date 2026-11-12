"""Radar de oportunidades de LicitaPerú: procesos vigentes publicados por el SEACE.

Fuente: la API pública que usa la app oficial «Oportunidades de negocio» del SEACE
(https://prod4.seace.gob.pe/openegocio/). Devuelve los ítems de los procedimientos convocados y vigentes, con sus
fechas y el código del archivo de bases. Se filtra por departamento en el propio servidor (código INEI), como hace
la app oficial; el campo «ubigeo» de cada fila es un código interno y no se usa para ubicar.

Cada descarga se guarda en datos/cache/; si la API no responde, se usa la última copia y la app lo avisa.
"""
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

RAIZ = Path(__file__).resolve().parent
CACHE = RAIZ / "datos" / "cache"
API = "https://prod4.seace.gob.pe:8086/api/oportunidades/codObjeto/codDepartamento/sintesisProceso/codTipoProceso"
URL_BASES = "https://prod1.seace.gob.pe/SeaceWeb-PRO/SdescargarArchivoAlfresco?fileCode={}"
URL_BUSCADOR = "https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml"
URL_APP_OFICIAL = "https://prod4.seace.gob.pe/openegocio/"
LIMA = timezone(timedelta(hours=-5), "hora de Lima")   # el Perú no tiene horario de verano
DEPARTAMENTOS = {"01": "Amazonas", "02": "Áncash", "03": "Apurímac", "04": "Arequipa", "05": "Ayacucho",
                 "06": "Cajamarca", "07": "Callao", "08": "Cusco", "09": "Huancavelica", "10": "Huánuco", "11": "Ica",
                 "12": "Junín", "13": "La Libertad", "14": "Lambayeque", "15": "Lima", "16": "Loreto",
                 "17": "Madre de Dios", "18": "Moquegua", "19": "Pasco", "20": "Piura", "21": "Puno",
                 "22": "San Martín", "23": "Tacna", "24": "Tumbes", "25": "Ucayali"}


class ErrorFuente(Exception):
    """La API del SEACE no respondió y no hay copia guardada."""


def ahora():
    return datetime.now(LIMA)


# 1 · Descarga

def descargar(departamento="0"):
    """Filas de la API para un departamento ("0" = todo el Perú).

    Devuelve (filas, consultado, desde_copia): desde_copia es True si la API falló y se usó la última copia.
    """
    url = f"{API}/0/{departamento}/0/0"
    copia = CACHE / f"oportunidades_{departamento}.json"
    try:
        respuesta = httpx.get(url, timeout=60)
        respuesta.raise_for_status()
        filas = respuesta.json()
        if not isinstance(filas, list):
            raise ValueError("respuesta inesperada")
    except (httpx.HTTPError, ValueError) as e:
        if copia.exists():
            guardado = json.loads(copia.read_text(encoding="utf-8"))
            return guardado["filas"], datetime.fromisoformat(guardado["consultado"]), True
        raise ErrorFuente(f"El SEACE no respondió ({type(e).__name__}) y no hay una copia guardada.") from None
    consultado = ahora()
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        copia.write_text(json.dumps({"url": url, "consultado": consultado.isoformat(), "filas": filas},
                                    ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return filas, consultado, False


# 2 · De filas (ítems) a procesos

def fecha(texto):
    """"10/12/2026 00:01:00" → datetime en hora de Lima; None si falta o no se entiende."""
    try:
        return datetime.strptime(str(texto).strip(), "%d/%m/%Y %H:%M:%S").replace(tzinfo=LIMA)
    except ValueError:
        return None


def _limpio(texto):
    # La fuente pone «¿» donde el original tenía comillas tipográficas.
    return re.sub(r"\s+", " ", str(texto or "").replace("¿", '"')).strip()


def normalizar(texto):
    sin_tildes = unicodedata.normalize("NFD", str(texto).lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", sin_tildes).strip()


def procesos(filas):
    """Agrupa los ítems por procedimiento, con fechas ya convertidas y el enlace oficial a las bases."""
    resultado = {}
    for f in filas:
        pid = f["idProcedimiento"]
        if pid not in resultado:
            valor = str(f.get("valorReferencial") or "").strip()
            resultado[pid] = {
                "id": pid, "codigo": _limpio(f.get("nomenclatura")), "entidad": _limpio(f.get("detEntidad")),
                "tipo": _limpio(f.get("detTipoProceso")), "objeto": _limpio(f.get("detObjeto")),
                "sintesis": _limpio(f.get("sintesisProceso")), "moneda": _limpio(f.get("monedaProceso")),
                "valor_referencial": None if valor in ("", "---") else valor,
                "convocatoria": fecha(f.get("fechaConvocatoria")),
                "registro_inicio": fecha(f.get("fecInicioParticipantes")),
                "registro_fin": fecha(f.get("fecFinParticipantes")),
                "propuestas": fecha(f.get("fechaPresentacionPropuestas")),
                "documento_base": (f.get("documentoBase") or "").strip() or None,
                "items": []}
            doc = resultado[pid]["documento_base"]
            resultado[pid]["url_bases"] = URL_BASES.format(doc) if doc else None
        resultado[pid]["items"].append({
            "nro": _limpio(f.get("nroItem")), "tipo": _limpio(f.get("tipoItem")),
            "descripcion": _limpio(f.get("detItem")), "cubso": _limpio(f.get("detCubso")),
            "cantidad": _limpio(f.get("cantItem")), "unidad": _limpio(f.get("detUnidadMedida"))})
    for p in resultado.values():
        partes = [p["codigo"], p["entidad"], p["sintesis"]] + [i["descripcion"] + " " + i["cubso"] for i in p["items"]]
        p["texto"] = " " + normalizar(" ".join(partes)) + " "
    return list(resultado.values())


# 3 · Estado según las fechas

def propuestas_coherente(p):
    """La fecha de propuestas solo se usa como plazo si va después del cierre del registro.

    En la fuente, 299 de 3,192 ítems (casi todos subastas inversas y adjudicaciones selectivas) traen la fecha de
    propuestas antes del cierre del registro: ahí no indica un plazo vencido y se muestra como «por verificar».
    """
    return p["propuestas"] is not None and p["registro_fin"] is not None and p["propuestas"] > p["registro_fin"]


ABIERTO = "Registro abierto"
POR_ABRIR = "Registro por abrir"
CERRADO = "Registro cerrado"
POR_VERIFICAR = "Por verificar"


def estado(p, momento=None):
    """Estado del registro de participantes (la ventana que decide si un proveedor nuevo aún puede entrar)."""
    momento = momento or ahora()
    inicio, fin = p["registro_inicio"], p["registro_fin"]
    if fin is None:
        return POR_VERIFICAR, "la fuente no trae la fecha de cierre del registro de participantes"
    if inicio and fin < inicio:
        return POR_VERIFICAR, "la fuente trae el cierre del registro antes de su inicio"
    if inicio and momento < inicio:
        return POR_ABRIR, f"el registro de participantes empieza el {texto_fecha(inicio)}"
    if momento <= fin:
        return ABIERTO, f"puedes registrarte hasta el {texto_fecha(fin)} ({texto_plazo(fin - momento)})"
    return CERRADO, f"el registro de participantes terminó el {texto_fecha(fin)}"


def estado_propuestas(p, momento=None):
    """El plazo de propuestas, por separado: ("Pendiente" | "Vencido" | "Por verificar", detalle)."""
    momento = momento or ahora()
    if p["propuestas"] is None:
        return POR_VERIFICAR, "la fuente no trae la fecha de presentación de propuestas"
    if not propuestas_coherente(p):
        return POR_VERIFICAR, ("la fuente registra la presentación de propuestas antes del cierre del registro "
                               "(pasa en subastas inversas y adjudicaciones selectivas): confirma el cronograma en "
                               "las bases")
    if momento < p["propuestas"]:
        return "Pendiente", f"{texto_fecha(p['propuestas'])} ({texto_plazo(p['propuestas'] - momento)})"
    return "Vencido", f"fue el {texto_fecha(p['propuestas'])}"


def texto_fecha(f):
    return f.strftime("%d/%m/%Y %H:%M") if f else "sin dato"


def texto_propuestas(p):
    if p["propuestas"] is None:
        return "sin dato"
    if propuestas_coherente(p):
        return texto_fecha(p["propuestas"])
    return f"{texto_fecha(p['propuestas'])} (por verificar)"


def texto_plazo(diferencia):
    horas = diferencia.total_seconds() / 3600
    if horas < 24:
        return f"quedan {max(int(horas), 0)} h"
    dias = int(horas // 24)
    return "queda 1 día" if dias == 1 else f"quedan {dias} días"


# 4 · Búsqueda por palabras

def _raiz(palabra):
    """Raíz simple para que «ferretería» encuentre «ferreteros» y «materiales» encuentre «material»."""
    return re.sub(r"(ias|ia|os|as|es|o|a|s)$", "", palabra) if len(palabra) > 4 else palabra


def coincide(p, palabras):
    """True si todas las palabras (sin tildes, por su raíz) aparecen en el código, la entidad, la síntesis o los ítems."""
    return all(f" {_raiz(w)}" in p["texto"] for w in normalizar(palabras).split())


def filtrar(lista, palabras="", objeto=None, solo_abiertos=False, momento=None):
    salida = []
    for p in lista:
        if palabras.strip() and not coincide(p, palabras):
            continue
        if objeto and p["objeto"] != objeto:
            continue
        if solo_abiertos and estado(p, momento)[0] != ABIERTO:
            continue
        salida.append(p)
    return sorted(salida, key=lambda p: (p["registro_fin"] is None, p["registro_fin"] or ahora()))
