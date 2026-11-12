"""Genera respaldo/oportunidades.json.gz: copia pública de la API del SEACE que la app usa si la API no responde
(por ejemplo, desde un servidor en la nube) y no hay una copia local más reciente.

Guarda los procesos vigentes de todo el Perú y un mapa ubigeo → departamento armado con el filtro por departamento
del propio SEACE (una consulta por departamento, con el código INEI), para que el filtro siga funcionando con la copia.

Desde la raíz:  uv run python herramientas/preparar_respaldo.py
"""
import gzip
import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import httpx  # noqa: E402

import radar  # noqa: E402


def consultar(departamento):
    r = httpx.get(f"{radar.API}/0/{departamento}/0/0", timeout=120)
    r.raise_for_status()
    return r.json()


def main():
    consultado = radar.ahora()
    nacional = consultar("0")
    mapa, conflictos = {}, set()
    for codigo in radar.DEPARTAMENTOS:
        for fila in consultar(codigo):
            ubigeo = str(fila["ubigeo"])
            if mapa.get(ubigeo, codigo) != codigo:
                conflictos.add(ubigeo)
            mapa.setdefault(ubigeo, codigo)
        time.sleep(0.5)
    cubiertas = sum(str(f["ubigeo"]) in mapa for f in nacional)
    salida = RAIZ / "respaldo" / "oportunidades.json.gz"
    salida.parent.mkdir(exist_ok=True)
    contenido = {"fuente": f"{radar.API}/0/0/0/0", "consultado": consultado.isoformat(timespec="seconds"),
                 "nota": "Copia de respaldo de datos públicos del SEACE; puede estar desactualizada.",
                 "filas": nacional, "departamento_por_ubigeo": mapa,
                 "cobertura_departamento": f"{cubiertas} de {len(nacional)} filas"}
    with gzip.open(salida, "wt", encoding="utf-8") as f:
        json.dump(contenido, f, ensure_ascii=False)
    print(f"{salida.relative_to(RAIZ)}: {len(nacional)} filas, {len({f['idProcedimiento'] for f in nacional})} "
          f"procesos, consultado {consultado:%d/%m/%Y %H:%M}; ubigeos con departamento: {len(mapa)}; filas cubiertas: "
          f"{cubiertas}/{len(nacional)}; conflictos: {sorted(conflictos)}; {salida.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
