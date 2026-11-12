"""Pruebas de la interfaz con streamlit.testing (AppTest), sin red: la API se reemplaza por la muestra real."""
import sys
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluador  # noqa: E402
import radar  # noqa: E402
from utiles import filas_muestra, momento  # noqa: E402

APP = str(RAIZ / "app.py")


@pytest.fixture(autouse=True)
def fuente_simulada(monkeypatch):
    st.cache_data.clear()
    pedidos = []

    def descargar(departamento="0"):
        pedidos.append(departamento)
        return filas_muestra(), momento("11/11/2026 22:12:04"), radar.VIVO

    monkeypatch.setattr(radar, "descargar", descargar)
    monkeypatch.setattr(radar, "ahora", lambda: momento("11/11/2026 22:30:00"))
    return pedidos


def _textos(at):
    return " ".join([m.value for m in at.markdown] + [c.value for c in at.caption])


def test_radar_ferreteria_y_ficha_del_caso(fuente_simulada):
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert at.text_input[0].value == "ferretería" and at.toggle[0].value is True
    assert "**2 procesos** coinciden" in _textos(at)
    tabla = at.dataframe[0].value
    assert list(tabla["Código"]) == ["LP-ABR-1-2026-MIDAGRI-3", "LP-SM-16-2026-MML-OGA-OL-1"]
    assert set(tabla["Registro"]) == {"Registro abierto"}
    selector = next(s for s in at.selectbox if s.label == "Abrir la ficha del proceso")
    selector.set_value(1262798).run()
    assert at.subheader[0].value == "LP-SM-16-2026-MML-OGA-OL-1"
    textos = _textos(at)
    assert "MUNICIPALIDAD METROPOLITANA DE LIMA" in textos
    assert "**Registro de participantes:** del 04/11/2026 00:01 al 09/12/2026 23:59" in textos
    assert "puedes registrarte hasta el 09/12/2026 23:59 (quedan 28 días)" in textos
    assert "Registro abierto" in textos and "Pendiente" in textos
    assert "**Plazo de propuestas:** 10/12/2026 00:01" in textos
    assert "Plazo de propuestas: 10/12/2026 00:01 (quedan 28 días)." in textos
    assert "fileCode=db513705-7e82-4501-9564-6c0c34cc7893" in textos
    assert "no publicado en la fuente" in textos
    assert "consultado el 11/11/2026 22:12" in textos


def test_ver_cerrados_y_filtro_por_departamento(fuente_simulada, monkeypatch):
    monkeypatch.setattr(radar, "ahora", lambda: momento("12/11/2026 01:00:00"))   # la subasta ya cerró su registro
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.text_input[0].set_value("").run()
    at.toggle[0].set_value(False).run()
    tabla = at.dataframe[0].value
    cerrado = tabla[tabla["Código"] == "SIE-SIE-4-2026-EP/UO 0840-1"]
    assert list(cerrado["Registro"]) == ["Registro cerrado"]
    assert list(cerrado["Propuestas"]) == ["28/10/2026 00:01 (por verificar)"]
    next(s for s in at.selectbox if s.label.startswith("Departamento")).set_value("Lima").run()
    assert fuente_simulada[-1] == "15"   # el filtro lo hace el SEACE con el código INEI
    assert "procesos vigentes en Lima" in _textos(at)


def test_error_de_la_fuente_y_copia(monkeypatch):
    def falla(departamento="0"):
        raise radar.ErrorFuente("El SEACE no respondió (ConnectError) y no hay una copia guardada.")

    monkeypatch.setattr(radar, "descargar", falla)
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert "No se pudo consultar el radar" in at.error[0].value
    assert any(b.label == "Reintentar" for b in at.button)

    for origen, tipo in [(radar.COPIA, "copia local"), (radar.DE_RESPALDO, "copia de respaldo publicada con la app")]:
        st.cache_data.clear()
        monkeypatch.setattr(radar, "descargar", lambda d="0", o=origen: (filas_muestra(),
                                                                         momento("11/11/2026 23:47:00"), o))
        at = AppTest.from_file(APP, default_timeout=60).run()
        aviso = at.warning[0].value
        assert "**datos de respaldo**" in aviso and f"({tipo})" in aviso and "**11/11/2026 23:47**" in aviso
        assert f"{tipo} del 11/11/2026 23:47" in _textos(at)


def test_caso_de_ejemplo_sin_pdf_ni_api_ni_clave(monkeypatch):
    # Como en la nube: el SEACE no responde, no hay CLI de Claude ni clave, no hay PDF ni OCR.
    def falla(departamento="0"):
        raise radar.ErrorFuente("El SEACE no respondió.")

    monkeypatch.setattr(radar, "descargar", falla)
    monkeypatch.setattr(evaluador, "CLI", "no-existe-claude-licitaperu")
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert "IA en vivo no disponible en este servidor" in _textos(at)
    next(b for b in at.button if b.label == "Ver caso de ejemplo").click().run()
    assert not at.exception
    assert at.subheader[0].value == "LP-SM-16-2026-MML-OGA-OL-1"
    textos = _textos(at)
    assert "Extracción guardada" in textos and "Caso de ejemplo" in at.info[0].value
    assert "MUNICIPALIDAD METROPOLITANA DE LIMA" in textos and "fileCode=db513705" in textos
    assert textos.count("Por verificar") >= 3 and "página 46 (texto por OCR)" in textos
    assert "página 22 (texto del PDF)" in textos and "página 50 (texto por OCR)" in textos

    def estados():
        return [m.value for m in at.markdown if "Verificado en el texto" in m.value or "Por verificar]" in m.value]

    def lista():
        return next(m.value for m in at.markdown if m.value.startswith("**Tu lista:"))

    antes = estados()
    assert lista() == "**Tu lista: 0 de 3 marcados · 3 por verificar en las bases**"
    casillas = [c for c in at.checkbox if c.label == "Lo tengo"]
    assert len(casillas) == 3
    casillas[0].check().run()
    assert lista() == "**Tu lista: 1 de 3 marcados · 3 por verificar en las bases**" and estados() == antes
    [c for c in at.checkbox if c.label == "Lo tengo"][2].check().run()
    assert lista() == "**Tu lista: 2 de 3 marcados · 3 por verificar en las bases**" and estados() == antes
    [c for c in at.checkbox if c.label == "Lo tengo"][0].uncheck().run()
    assert lista() == "**Tu lista: 1 de 3 marcados · 3 por verificar en las bases**" and estados() == antes
    next(b for b in at.button if b.label == "Volver al radar").click().run()
    assert "No se pudo consultar el radar" in at.error[0].value   # vuelve al radar (aquí sin red)
