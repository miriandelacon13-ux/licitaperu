"""Pruebas sin red del radar: fechas, estado, búsqueda y copia de respaldo. Desde la raíz: uv run pytest -v"""
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import radar  # noqa: E402
from utiles import filas_muestra, momento  # noqa: E402

PROCESOS = {p["codigo"]: p for p in radar.procesos(filas_muestra())}
MML = PROCESOS["LP-SM-16-2026-MML-OGA-OL-1"]


def test_ficha_del_caso_principal():
    assert MML["entidad"] == "MUNICIPALIDAD METROPOLITANA DE LIMA"
    assert MML["objeto"] == "Bien" and MML["tipo"] == "Licitación Pública"
    assert MML["sintesis"].startswith("ADQUISICIÓN DE MATERIALES FERRETEROS, REPUESTOS Y ACCESORIOS")
    assert radar.texto_fecha(MML["registro_inicio"]) == "04/11/2026 00:01"
    assert radar.texto_fecha(MML["registro_fin"]) == "09/12/2026 23:59"
    assert radar.texto_fecha(MML["propuestas"]) == "10/12/2026 00:01"
    assert MML["valor_referencial"] is None   # la fuente publica «---»
    assert MML["url_bases"] == ("https://prod1.seace.gob.pe/SeaceWeb-PRO/SdescargarArchivoAlfresco"
                                "?fileCode=db513705-7e82-4501-9564-6c0c34cc7893")
    assert '"' in MML["sintesis"] and "¿" not in MML["sintesis"]   # «¿» de la fuente vuelve a ser comilla


def test_fechas_invalidas_quedan_sin_dato():
    assert radar.fecha("---") is None and radar.fecha(None) is None and radar.fecha("31/02/2026 10:00:00") is None


@pytest.mark.parametrize("cuando, esperado, detalle", [
    ("03/11/2026 12:00:00", radar.POR_ABRIR, "empieza el 04/11/2026 00:01"),
    ("11/11/2026 22:30:00", radar.ABIERTO, "puedes registrarte hasta el 09/12/2026 23:59 (quedan 28 días)"),
    ("09/12/2026 10:00:00", radar.ABIERTO, "quedan 13 h"),
    ("09/12/2026 23:59:00", radar.ABIERTO, "quedan 0 h"),
    ("10/12/2026 00:00:00", radar.CERRADO, "terminó el 09/12/2026 23:59"),
])
def test_estado_del_registro(cuando, esperado, detalle):
    estado, texto = radar.estado(MML, momento(cuando))
    assert estado == esperado and detalle in texto


def test_plazo_de_propuestas_por_separado():
    assert radar.estado_propuestas(MML, momento()) == ("Pendiente", "10/12/2026 00:01 (quedan 28 días)")
    assert radar.estado_propuestas(MML, momento("10/12/2026 00:01:00"))[0] == "Vencido"


def test_fechas_incoherentes_quedan_por_verificar():
    assert radar.estado(MML | {"registro_fin": None}, momento())[0] == radar.POR_VERIFICAR
    al_reves = MML | {"registro_fin": MML["registro_inicio"] - (MML["registro_fin"] - MML["registro_inicio"])}
    assert radar.estado(al_reves, momento())[0] == radar.POR_VERIFICAR
    assert radar.estado_propuestas(MML | {"propuestas": None}, momento())[0] == radar.POR_VERIFICAR


def test_subasta_inversa_con_propuestas_antes_del_cierre():
    # Fuente real: registro del 28/10 00:01 al 11/11 23:59 y «propuestas» el 28/10 00:01.
    sie = PROCESOS["SIE-SIE-4-2026-EP/UO 0840-1"]
    assert not radar.propuestas_coherente(sie) and radar.propuestas_coherente(MML)
    assert radar.texto_propuestas(sie) == "28/10/2026 00:01 (por verificar)"
    assert radar.estado_propuestas(sie, momento())[0] == radar.POR_VERIFICAR
    assert radar.estado(sie, momento("11/11/2026 22:30:00")) == (radar.ABIERTO, "puedes registrarte hasta el "
                                                                 "11/11/2026 23:59 (quedan 1 h)")
    assert radar.estado(sie, momento("12/11/2026 00:30:00")) == (radar.CERRADO, "el registro de participantes "
                                                                 "terminó el 11/11/2026 23:59")


def test_busqueda_sin_tildes_y_por_raiz():
    assert radar.coincide(MML, "ferretería") and radar.coincide(MML, "FERRETERIA")   # «ferreteros» en la fuente
    assert radar.coincide(PROCESOS["LP-ABR-1-2026-MIDAGRI-3"], "ferreteria herramientas")
    assert radar.coincide(PROCESOS["LP-ABR-10-2025-SEAL-4"], "conductores eléctricos")
    assert not radar.coincide(PROCESOS["CP SER-SM-6-2026-DPC/ACFFAA-1"], "ferretería")


def test_filtrar_solo_abiertos_y_por_objeto():
    lista = radar.procesos(filas_muestra())
    abiertos = radar.filtrar(lista, "", solo_abiertos=True, momento=momento("12/11/2026 00:30:00"))
    assert "SIE-SIE-4-2026-EP/UO 0840-1" not in [p["codigo"] for p in abiertos]   # registro cerró el 11/11 23:59
    ferreteria = radar.filtrar(lista, "ferretería", "Bien", True, momento())
    assert [p["codigo"] for p in ferreteria] == ["LP-ABR-1-2026-MIDAGRI-3", "LP-SM-16-2026-MML-OGA-OL-1"]  # por plazo


def test_si_el_seace_falla_se_usa_la_copia(tmp_path, monkeypatch):
    monkeypatch.setattr(radar, "CACHE", tmp_path)
    monkeypatch.setattr(radar, "RESPALDO", tmp_path / "no-hay-respaldo.json.gz")

    class Respuesta:
        def raise_for_status(self):
            pass

        def json(self):
            return filas_muestra()

    monkeypatch.setattr(radar.httpx, "get", lambda url, timeout: Respuesta())
    filas, _, origen = radar.descargar("15")
    assert len(filas) == 5 and origen == radar.VIVO
    assert json.loads((tmp_path / "oportunidades_15.json").read_text(encoding="utf-8"))["url"].endswith("/0/15/0/0")

    def falla(url, timeout):
        raise httpx.ConnectError("sin red")

    monkeypatch.setattr(radar.httpx, "get", falla)
    filas, _, origen = radar.descargar("15")
    assert len(filas) == 5 and origen == radar.COPIA
    with pytest.raises(radar.ErrorFuente):
        radar.descargar("04")   # sin copia local ni respaldo


def test_sin_red_ni_copia_se_usa_el_respaldo_publicado(tmp_path, monkeypatch):
    # El respaldo real del repositorio (herramientas/preparar_respaldo.py), como en un servidor recién desplegado.
    monkeypatch.setattr(radar, "CACHE", tmp_path)

    def falla(url, timeout):
        raise httpx.ConnectTimeout("la API no responde desde la nube")

    monkeypatch.setattr(radar.httpx, "get", falla)
    todo, consultado, origen = radar.descargar("0")
    assert origen == radar.DE_RESPALDO and consultado.strftime("%d/%m/%Y %H:%M") == "11/11/2026 23:47"
    lima, _, _ = radar.descargar("15")
    assert 0 < len(lima) < len(todo)
    codigos = {p["codigo"] for p in radar.procesos(lima)}
    assert "LP-SM-16-2026-MML-OGA-OL-1" in codigos and "LP-ABR-10-2025-SEAL-4" not in codigos   # SEAL es de Arequipa
    arequipa, _, _ = radar.descargar("04")
    assert "LP-ABR-10-2025-SEAL-4" in {p["codigo"] for p in radar.procesos(arequipa)}
