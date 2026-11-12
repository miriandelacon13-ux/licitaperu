"""Pruebas de la interfaz con streamlit.testing (AppTest), sin red: la API se reemplaza por la muestra real."""
import sys
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import radar  # noqa: E402
from utiles import filas_muestra, momento  # noqa: E402

APP = str(RAIZ / "app.py")


@pytest.fixture(autouse=True)
def fuente_simulada(monkeypatch):
    st.cache_data.clear()
    pedidos = []

    def descargar(departamento="0"):
        pedidos.append(departamento)
        return filas_muestra(), momento("11/11/2026 22:12:04"), False

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

    st.cache_data.clear()
    monkeypatch.setattr(radar, "descargar", lambda d="0": (filas_muestra(), momento("10/11/2026 08:00:00"), True))
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert "copia guardada del 10/11/2026 08:00" in at.warning[0].value
