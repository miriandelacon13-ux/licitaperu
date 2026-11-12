"""Pruebas sin red del evaluador: legibilidad, coincidencia con el proceso, OCR en caché, verificación de citas y
salida estructurada simulada. La extracción real se valida aparte, con las bases reales del proceso.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluador  # noqa: E402
from utiles import pdf  # noqa: E402

RELLENO = " Texto de relleno de una página de prueba para superar el mínimo de caracteres por página." * 2
PAGINAS = ["CAPÍTULO III. Requisitos de calificación." + RELLENO,
           "3.1 Capacidad legal. El postor debe contar con inscripción vigente en el Registro Nacional de Proveedores "
           "(RNP) en el capítulo de bienes." + RELLENO,
           "3.2 Experiencia del postor en la especialidad. Facturación mínima de S/ 150,000.00 por la venta de bienes "
           "iguales o similares durante los ocho años anteriores." + RELLENO]
ENCABEZADO = "Licitación Pública de Bienes N° 016-2026-MML-OGA-OL"


def test_pdf_con_texto_es_legible():
    lectura = evaluador.leer_pdf(pdf(PAGINAS))
    assert lectura["estado"] == "legible" and lectura["evaluable"] and lectura["sin_texto"] == []
    texto = " ".join(lectura["paginas"][1].split())   # el PDF parte las líneas
    assert "inscripción vigente en el Registro Nacional de Proveedores" in texto   # tildes intactas


def test_pdf_sin_texto_es_escaneo():
    lectura = evaluador.leer_pdf(pdf(["", ""]))
    assert lectura["estado"] == "escaneo" and not lectura["evaluable"] and "OCR" in lectura["motivo"]


def test_pdf_en_parte_escaneado_se_puede_evaluar_con_aviso():
    lectura = evaluador.leer_pdf(pdf(PAGINAS[:1] + ["", "", ""]))
    assert lectura["estado"] == "parcial" and lectura["evaluable"]
    assert "3 son imágenes sin texto y requieren OCR (páginas 2–4)" in lectura["motivo"]


def test_un_encabezado_repetido_no_cuenta_como_texto():
    # Caso real de las bases de la MML: las páginas escaneadas solo traen el encabezado como texto.
    con_texto = [f"{ENCABEZADO} {i}. " + PAGINAS[i % 3] for i in range(4)]
    solo_encabezado = [f"{ENCABEZADO} {i}" for i in range(4, 8)]
    lectura = evaluador.leer_pdf(pdf(con_texto + solo_encabezado))
    assert lectura["sin_texto"] == [5, 6, 7, 8] and lectura["estado"] == "parcial"


def test_archivo_que_no_es_pdf():
    assert evaluador.leer_pdf(b"esto no es un pdf")["estado"] == "ilegible"


def test_corresponde_al_proceso():
    lectura = evaluador.leer_pdf(pdf([f"{ENCABEZADO}. " + PAGINAS[0], "Nº 016- 2026-MML-OGA-OL " + PAGINAS[1]]))
    si = evaluador.corresponde(lectura, "LP-SM-16-2026-MML-OGA-OL-1")
    assert si["corresponde"] and si["paginas"] == [1, 2] and si["buscado"] == "N° 016-2026-MML-OGA-OL"
    assert not evaluador.corresponde(lectura, "LP-ABR-1-2026-MIDAGRI-3")["corresponde"]
    assert not evaluador.corresponde(lectura, "LP-SM-116-2026-MML-OGA-OL-1")["corresponde"]   # 116 ≠ 016


def test_ocr_en_cache_completa_las_paginas(tmp_path):
    lectura = evaluador.leer_pdf(pdf(PAGINAS[:1] + ["", ""]))
    (tmp_path / "p02.json").write_text(json.dumps({"lineas": [{"texto": "7.1 Requisitos de calificación",
                                                               "confianza": 0.99}]}), encoding="utf-8")
    con_ocr = evaluador.aplicar_ocr(lectura, tmp_path)
    assert con_ocr["ocr"] == [2] and con_ocr["sin_leer"] == [3]
    assert con_ocr["paginas"][1] == "7.1 Requisitos de calificación" and lectura["paginas"][1] == ""
    pedido = evaluador._pedido(con_ocr)
    assert "[PÁGINA 2 · texto obtenido por OCR]" in pedido and "[PÁGINA 3 · imagen sin texto" in pedido
    assert "las páginas 3 del PDF son imágenes que no se pudieron leer" in pedido


def test_rangos():
    assert evaluador.rangos([1, 28, 29, 30, 52, 66]) == "1, 28–30, 52, 66" and evaluador.rangos([]) == ""


def _req(fragmento, pagina, ambiguo=False, momento="Con la oferta", respaldos=None):
    if respaldos is None:
        respaldos = [{"dato": "dato", "pagina": pagina, "seccion": "3.1", "fragmento": fragmento}]
    return {"requisito": "R", "que_se_pide": "x", "momento": momento, "pagina": pagina, "seccion": "3.1",
            "fragmento": fragmento, "respaldos": respaldos, "ambiguo": ambiguo,
            "nota": "depende del anexo" if ambiguo else ""}


def test_verificar_citas_contra_el_texto():
    paginas = evaluador.leer_pdf(pdf(PAGINAS))["paginas"]
    ok, otra, falsa, ambigua, corta = evaluador.verificar([
        _req("debe contar con inscripcion  vigente en el Registro Nacional de Proveedores", 2),  # sin tilde, 2 espacios
        _req("Facturación mínima de S/ 150,000.00 por la venta de bienes", 2),
        _req("Facturación mínima de S/ 200,000.00 por la venta de bienes", 3),
        _req("El postor debe contar con inscripción vigente en el Registro", 2, ambiguo=True),
        _req("RNP", 2, momento="Otro")], paginas, ocr=[3])
    assert ok["estado"] == evaluador.VERIFICADO and ok["origen"] == "texto del PDF"
    assert ok["respaldos"][0]["estado"] == evaluador.VERIFICADO
    assert otra["estado"] == evaluador.POR_VERIFICAR and "está en la página 3, no en la 2" in otra["verificacion"]
    assert falsa["estado"] == evaluador.POR_VERIFICAR and falsa["origen"] == "texto por OCR"
    assert "no aparece literal" in falsa["verificacion"]
    assert ambigua["estado"] == evaluador.POR_VERIFICAR and "pero el requisito es ambiguo: depende del anexo" in         ambigua["verificacion"]
    assert corta["estado"] == evaluador.POR_VERIFICAR and corta["momento"] == "No lo indica"


def test_cada_respaldo_se_comprueba_por_separado():
    paginas = evaluador.leer_pdf(pdf(PAGINAS))["paginas"]
    principal = "Facturación mínima de S/ 150,000.00 por la venta de bienes"
    bien, mal, sin = evaluador.verificar([
        _req(principal, 3, respaldos=[
            {"dato": "Monto", "pagina": 3, "seccion": "3.2", "fragmento": principal},
            {"dato": "Etapa: con la oferta", "pagina": 1, "seccion": "III", "fragmento": "CAPÍTULO III. Requisitos de calificación"}]),
        _req(principal, 3, respaldos=[
            {"dato": "Monto", "pagina": 3, "seccion": "3.2", "fragmento": principal},
            {"dato": "Plazo: 10 años", "pagina": 3, "seccion": "3.2", "fragmento": "durante los diez años anteriores"}]),
        _req(principal, 3, respaldos=[])], paginas)
    assert bien["estado"] == evaluador.VERIFICADO and "los 2 respaldos" in bien["verificacion"]
    assert mal["estado"] == evaluador.POR_VERIFICAR and "1 de 2 respaldos" in mal["verificacion"]
    assert [c["estado"] for c in mal["respaldos"]] == [evaluador.VERIFICADO, evaluador.POR_VERIFICAR]
    assert "Plazo: 10 años (no aparece literal" in mal["verificacion"]
    assert sin["estado"] == evaluador.POR_VERIFICAR and "no dio respaldos" in sin["verificacion"]


def test_seleccion_de_paginas_conserva_los_numeros():
    paginas = [RELLENO, "2.2.1.1 Documentos para la admisión de la oferta. De no cumplir, la oferta se considera no "
               "admitida." + RELLENO, RELLENO, "7.1 Requisitos de calificación. A. Experiencia del postor: monto "
               "facturado acumulado." + RELLENO, "c. Plazo de entrega: 120 días." + RELLENO]
    lectura = evaluador.leer_pdf(pdf(paginas))
    elegidas = evaluador.seleccionar_paginas(lectura)
    assert elegidas == [2, 4]   # la 5 solo menciona el plazo: no llega al umbral
    pedido = evaluador._pedido(lectura, elegidas)
    assert "[PÁGINA 2]" in pedido and "[PÁGINA 4]" in pedido and "[PÁGINA 1]" not in pedido
    assert "Solo recibes 2 de las 5 páginas" in pedido and "números son los del PDF original" in pedido


def test_resumen_de_la_lista_separa_marcado_de_verificado():
    reqs = [{"requisito": "Experiencia", "momento": "Con la oferta", "estado": evaluador.POR_VERIFICAR},
            {"requisito": "Admisión", "momento": "Con la oferta", "estado": evaluador.VERIFICADO},
            {"requisito": "Garantía", "momento": "Para perfeccionar el contrato", "estado": evaluador.POR_VERIFICAR}]
    nada = evaluador.resumen_lista(reqs, [False, False, False])
    assert nada["titulo"] == "0 de 3 marcados · 2 por verificar en las bases"
    assert nada["sin_marcar"] == {"Para la oferta": ["Experiencia", "Admisión"], "Para el contrato, si ganas": ["Garantía"]}
    todo = evaluador.resumen_lista(reqs, [True, True, True])
    assert todo["titulo"] == "3 de 3 marcados · 2 por verificar en las bases"   # marcar no verifica
    assert todo["sin_marcar"] == {} and todo["por_verificar"] == ["Experiencia", "Garantía"]
    verificados = [r | {"estado": evaluador.VERIFICADO} for r in reqs]
    assert evaluador.resumen_lista(verificados, [True, False, True])["titulo"] ==         "2 de 3 marcados · los 3 verificados en las bases"


def test_salida_estructurada_simulada(monkeypatch, tmp_path):
    monkeypatch.setattr(evaluador, "BITACORA", tmp_path / "ia.jsonl")
    monkeypatch.setattr(evaluador.shutil, "which", lambda cli: "claude")
    vistos = {}

    def cli_simulada(comando, **kw):
        vistos["comando"], vistos["entrada"] = comando, kw["input"]
        salida = {"type": "result", "subtype": "success", "is_error": False, "total_cost_usd": 0.01,
                  "modelUsage": {"claude-opus-5-5": {"outputTokens": 120}},
                  "structured_output": {"requisitos": [_req("frase", 1)] * 4}}
        return subprocess.CompletedProcess(comando, 0, json.dumps(salida), "")

    monkeypatch.setattr(evaluador.subprocess, "run", cli_simulada)
    res = evaluador.extraer_requisitos(evaluador.leer_pdf(pdf(PAGINAS)), [2, 3])
    assert len(res["requisitos"]) == 3 and res["modelo"] == "claude-opus-5-5" and res["paginas_enviadas"] == [2, 3]
    esquema = json.loads(vistos["comando"][vistos["comando"].index("--json-schema") + 1])
    item = esquema["properties"]["requisitos"]["items"]
    assert item["required"][:3] == ["requisito", "que_se_pide", "momento"]
    assert item["properties"]["momento"]["enum"] == evaluador.MOMENTOS and "respaldos" in item["required"]
    assert "[PÁGINA 2]" in vistos["entrada"] and "Registro Nacional" in vistos["entrada"]
    assert "[PÁGINA 1]" not in vistos["entrada"]
    fila = json.loads((tmp_path / "ia.jsonl").read_text(encoding="utf-8"))
    assert fila["ok"] and fila["paginas_enviadas"] == [2, 3] and fila["costo_usd"] == 0.01


def test_errores_del_modelo(monkeypatch, tmp_path):
    monkeypatch.setattr(evaluador, "BITACORA", tmp_path / "ia.jsonl")
    monkeypatch.setattr(evaluador, "CLI", "no-existe-claude-licitaperu")
    with pytest.raises(evaluador.ErrorIA, match="no se encontró la CLI"):
        evaluador.extraer_requisitos(PAGINAS)
    monkeypatch.setattr(evaluador.shutil, "which", lambda cli: "claude")
    monkeypatch.setattr(evaluador.subprocess, "run", lambda c, **kw: subprocess.CompletedProcess(
        c, 0, json.dumps({"is_error": False, "result": "texto suelto"}), ""))
    with pytest.raises(evaluador.ErrorIA, match="salida estructurada"):
        evaluador.extraer_requisitos(PAGINAS)


def test_ultima_extraccion_guardada(tmp_path):
    bitacora = tmp_path / "ia.jsonl"
    con = {"requisitos": [_req("frase larga de prueba para citar", 1)]}
    sin = {"requisitos": [{k: v for k, v in _req("frase", 1).items() if k != "respaldos"}]}
    filas = [
        {"momento": "2026-11-11T22:50:43-05:00", "ok": True, "huella_pdf": "abc", "salida": sin},       # formato viejo
        {"momento": "2026-11-11T23:07:02-05:00", "ok": True, "huella_pdf": "abc", "salida": con, "modelo": "m",
         "segundos": 59.5, "costo_usd": 0.37, "paginas_enviadas": [22, 23], "sin_leer": [52]},
        {"momento": "2026-11-11T23:10:00-05:00", "ok": False, "huella_pdf": "abc", "error": "timeout"},
        {"momento": "2026-11-11T23:11:00-05:00", "ok": True, "huella_pdf": "otra", "salida": con}]
    bitacora.write_text("\n".join(json.dumps(f) for f in filas) + "\nlínea rota\n", encoding="utf-8")
    g = evaluador.ultima_extraccion("abc", bitacora)
    assert g["momento"] == "11/11/2026 23:07" and g["paginas_enviadas"] == [22, 23] and g["costo_usd"] == 0.37
    assert g["sin_leer"] == [52] and g["requisitos"][0]["respaldos"]
    assert evaluador.ultima_extraccion("nada", bitacora) is None and evaluador.ultima_extraccion(None, bitacora) is None


def test_caso_de_ejemplo_publicable():
    import re
    caso = evaluador.cargar_caso_ejemplo()
    texto = evaluador.CASO_EJEMPLO.read_text(encoding="utf-8")
    assert not re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", texto)          # sin correos
    assert not re.search(r"BOGDANOVICH|Firmado digitalmente", texto)  # sin firmas digitales del PDF
    assert caso["codigo"] == "LP-SM-16-2026-MML-OGA-OL-1" and caso["filas_seace"]
    assert caso["extraccion"]["momento"] == "11/11/2026 23:07" and len(caso["extraccion"]["paginas_enviadas"]) == 16
    assert [r["estado"] for r in caso["requisitos"]] == [evaluador.POR_VERIFICAR] * 3
    for r in caso["requisitos"]:
        assert r["respaldos"] and all(isinstance(c["pagina"], int) and c["fragmento"] for c in r["respaldos"])
    paginas = {c["pagina"] for r in caso["requisitos"] for c in r["respaldos"]}
    assert {22, 23, 46, 50, 51, 13, 24} <= paginas


def test_estado_de_la_ia(monkeypatch):
    monkeypatch.setattr(evaluador, "CLI", "no-existe-claude-licitaperu")
    ia = evaluador.estado_ia()
    assert not ia["disponible"] and "clave de API" in ia["detalle"] and "caso de ejemplo" in ia["detalle"]
