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
    assert "las páginas 3 son imágenes que no se pudieron leer" in pedido


def test_rangos():
    assert evaluador.rangos([1, 28, 29, 30, 52, 66]) == "1, 28–30, 52, 66" and evaluador.rangos([]) == ""


def _req(fragmento, pagina, ambiguo=False, momento="Con la oferta"):
    return {"requisito": "R", "que_se_pide": "x", "momento": momento, "pagina": pagina, "seccion": "3.1",
            "fragmento": fragmento, "ambiguo": ambiguo, "nota": "depende del anexo" if ambiguo else ""}


def test_verificar_citas_contra_el_texto():
    paginas = evaluador.leer_pdf(pdf(PAGINAS))["paginas"]
    ok, otra, falsa, ambigua, corta = evaluador.verificar([
        _req("debe contar con inscripcion  vigente en el Registro Nacional de Proveedores", 2),  # sin tilde, 2 espacios
        _req("Facturación mínima de S/ 150,000.00 por la venta de bienes", 2),
        _req("Facturación mínima de S/ 200,000.00 por la venta de bienes", 3),
        _req("El postor debe contar con inscripción vigente en el Registro", 2, ambiguo=True),
        _req("RNP", 2, momento="Otro")], paginas, ocr=[3])
    assert ok["estado"] == evaluador.VERIFICADO and ok["origen"] == "texto del PDF"
    assert otra["estado"] == evaluador.POR_VERIFICAR and "está en la página 3, no en la 2" in otra["verificacion"]
    assert falsa["estado"] == evaluador.POR_VERIFICAR and falsa["origen"] == "texto por OCR"
    assert "no aparece literal" in falsa["verificacion"]
    assert ambigua["estado"] == evaluador.POR_VERIFICAR and "depende del anexo" in ambigua["verificacion"]
    assert corta["estado"] == evaluador.POR_VERIFICAR and corta["momento"] == "No lo indica"


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
    res = evaluador.extraer_requisitos(evaluador.leer_pdf(pdf(PAGINAS)))
    assert len(res["requisitos"]) == 3 and res["modelo"] == "claude-opus-5-5"
    esquema = json.loads(vistos["comando"][vistos["comando"].index("--json-schema") + 1])
    item = esquema["properties"]["requisitos"]["items"]
    assert item["required"][:3] == ["requisito", "que_se_pide", "momento"]
    assert item["properties"]["momento"]["enum"] == evaluador.MOMENTOS
    assert "[PÁGINA 2]" in vistos["entrada"] and "Registro Nacional" in vistos["entrada"]
    assert json.loads((tmp_path / "ia.jsonl").read_text(encoding="utf-8"))["ok"]


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
