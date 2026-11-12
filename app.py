"""LicitaPerú · radar de oportunidades y evaluador de requisitos.

Local:  uv run streamlit run app.py --server.port 8503     Streamlit Community Cloud: archivo de inicio app.py

Radar: procesos vigentes del SEACE (radar.py), con copia de respaldo si la API no responde. Evaluador: el proveedor
sube las bases en PDF; se comprueba que sean del proceso y que se puedan leer (con OCR guardado para las páginas
escaneadas, ocr_bases.py), un LLM con salida estructurada extrae 3 requisitos y cada cita se contrasta con el texto
(evaluador.py). «Ver caso de ejemplo» abre el caso de la MML con una extracción guardada: no necesita el PDF, ni OCR,
ni clave de API.
"""
import re

import pandas as pd
import streamlit as st

import evaluador
import radar

COLORES = {radar.ABIERTO: "green", radar.POR_ABRIR: "orange", radar.CERRADO: "gray", radar.POR_VERIFICAR: "orange",
           "Pendiente": "blue", "Vencido": "gray"}
ICONOS = {radar.ABIERTO: ":material/event_available:", radar.POR_ABRIR: ":material/schedule:",
          radar.CERRADO: ":material/event_busy:", radar.POR_VERIFICAR: ":material/help:",
          "Pendiente": ":material/schedule:", "Vencido": ":material/event_busy:"}


def md(texto):
    """Texto de la fuente sin que Markdown lo interprete."""
    return re.sub(r"([\\`*_{}\[\]<>#+|$~])", r"\\\1", str(texto))


@st.cache_data(ttl=3600, show_spinner=False)
def cargar(departamento):
    filas, consultado, origen = radar.descargar(departamento)
    return radar.procesos(filas), consultado, origen


@st.cache_data(show_spinner=False, max_entries=5)
def leer(datos):
    return evaluador.leer_pdf(datos)


def ficha(p, caso=None):
    registro, detalle = radar.estado(p)
    propuestas, detalle_propuestas = radar.estado_propuestas(p)
    with st.container(border=True):
        st.subheader(p["codigo"])
        st.badge(registro, color=COLORES[registro], icon=ICONOS[registro])
        st.caption(f"Calculado con las fechas del registro de participantes del SEACE, en hora de Lima: {detalle}.")
        st.markdown(f"**Entidad:** {md(p['entidad'])}  \n"
                    f"**Objeto:** {md(p['objeto'])} · {md(p['tipo'])}  \n"
                    f"**Qué compra:** {md(p['sintesis'])}  \n"
                    f"**Valor referencial:** {md(p['valor_referencial']) if p['valor_referencial'] else 'no publicado en la fuente'}")
        st.markdown(f"**Convocatoria:** {radar.texto_fecha(p['convocatoria'])}  \n"
                    f"**Registro de participantes:** del {radar.texto_fecha(p['registro_inicio'])} al "
                    f"{radar.texto_fecha(p['registro_fin'])}")
        c1, c2 = st.columns([3, 2], vertical_alignment="center")
        c1.markdown(f"**Plazo de propuestas:** {radar.texto_fecha(p['propuestas'])}")
        c2.badge(propuestas, color=COLORES[propuestas], icon=ICONOS[propuestas])
        st.caption(f"Plazo de propuestas: {detalle_propuestas}.")
        items = pd.DataFrame(p["items"]).rename(columns={"nro": "Ítem", "tipo": "Tipo", "descripcion": "Descripción",
                                                          "cubso": "Catálogo (CUBSO)", "cantidad": "Cantidad",
                                                          "unidad": "Unidad"})
        st.dataframe(items, hide_index=True, width="stretch")
        enlaces = []
        if p["url_bases"]:
            enlaces.append(f"- [Bases del proceso (PDF) en el SEACE]({p['url_bases']})")
        enlaces.append(f"- [Buscador público del SEACE]({radar.URL_BUSCADOR}): busca la nomenclatura "
                       f"«{md(p['codigo'])}» para abrir la ficha")
        enlaces.append(f"- [Oportunidades de negocio del SEACE]({radar.URL_APP_OFICIAL})")
        st.markdown("**Enlaces oficiales**\n\n" + "\n".join(enlaces))
        if caso:
            extraccion_guardada(caso)
        else:
            evaluar(p)


def extraccion_guardada(caso):
    """El análisis publicado del caso de ejemplo: sin PDF, sin OCR en vivo y sin llamar al modelo."""
    st.markdown("#### ¿Qué te piden para postular?")
    st.badge("Extracción guardada", icon=":material/history:", color="gray")
    b, e = caso["bases"], caso["extraccion"]
    st.caption(f"Bases revisadas en local: {md(b['documento'])} ({b['paginas']} páginas; el número del proceso aparece "
               f"en {b['menciona_el_numero_en']}). Metadatos del PDF: {b['creado']}; "
               f"{'bases integradas' if b['integradas'] else 'no son bases integradas'}. Páginas escaneadas leídas con "
               f"OCR (PaddleOCR): {b['con_ocr']}. El PDF no se publica: descárgalo desde el enlace oficial.")
    res = {"requisitos": caso["requisitos"], "modelo": e["modelo"], "segundos": e["segundos"],
           "costo_usd": e["costo_usd"], "enviadas": e["paginas_enviadas"], "total": e["total_paginas"],
           "sin_leer": e["sin_leer_al_extraer"], "guardada": e["momento"], "comprobado": caso["comprobado"]}
    checklist(res, "ejemplo")


def evaluar(p):
    st.markdown("#### ¿Qué te piden para postular?")
    st.info("El SEACE bloquea la descarga automática de las bases. Descárgalas con tu navegador desde el enlace "
            "oficial y súbelas aquí.", icon=":material/upload_file:")
    archivo = st.file_uploader("Bases del proceso (PDF)", type=["pdf"], key=f"pdf_{p['id']}")
    if not archivo:
        return
    datos = archivo.getvalue()
    lectura = evaluador.aplicar_ocr(leer(datos))
    clave = f"{p['id']}_{lectura['huella']}"

    # ¿Es el PDF de este proceso?
    coincide = evaluador.corresponde(lectura, p["codigo"])
    if coincide["corresponde"]:
        st.success(f"El PDF corresponde al proceso: menciona «{coincide['buscado']}» en {len(coincide['paginas'])} "
                   "páginas.", icon=":material/task_alt:")
    else:
        st.error(f"No encontramos «{coincide['buscado']}» en el PDF: revisa que sean las bases de este proceso.",
                 icon=":material/error:")
    version = (f"Metadatos del PDF: creado el {lectura['creado']}. " if lectura["creado"] else "") + (
        "La portada dice «bases integradas»." if lectura["integradas"] else
        "La portada no dice «bases integradas»: si el SEACE publica las integradas, vuelve a cargarlas.")
    st.caption(f"Versión · {version} Huella del archivo: {lectura['huella']}.")

    # ¿Se puede leer?
    if lectura["estado"] == "legible":
        st.success(f"Texto legible: {lectura['motivo']}.", icon=":material/task_alt:")
    elif lectura["estado"] == "parcial":
        texto = f"Lectura parcial: {lectura['motivo']}."
        if lectura["ocr"]:
            texto += f" Ya hay OCR (PaddleOCR) de las páginas {evaluador.rangos(lectura['ocr'])}."
        if lectura["sin_leer"]:
            texto += (f" Sin leer todavía: {evaluador.rangos(lectura['sin_leer'])}; los requisitos que estén ahí no "
                      "aparecerán.")
        (st.warning if lectura["sin_leer"] else st.success)(texto, icon=":material/document_scanner:")
    else:
        st.error(f"Todavía no se puede evaluar: {lectura['motivo']}.", icon=":material/warning:")

    seguir = coincide["corresponde"] or st.checkbox("Es el archivo correcto: evaluar de todos modos",
                                                    key=f"forzar_{clave}")
    guardada = evaluador.ultima_extraccion(lectura["huella"])
    b1, b2 = st.columns(2)
    if guardada and b2.button("Usar la extracción guardada", icon=":material/history:", key=f"guardada_{clave}",
                              disabled=not seguir,
                              help=f"Corrida del {guardada['momento']}: {len(guardada['paginas_enviadas'])} páginas, "
                                   f"{guardada['segundos']:.0f} s, US$ {guardada['costo_usd'] or 0:.2f}. No vuelve a "
                                   "llamar al modelo; las citas se comprueban otra vez contra el PDF."):
        st.session_state[f"req_{clave}"] = {
            "requisitos": evaluador.verificar(guardada["requisitos"], lectura["paginas"], lectura["ocr"]),
            "modelo": guardada["modelo"], "segundos": guardada["segundos"], "costo_usd": guardada["costo_usd"],
            "enviadas": guardada["paginas_enviadas"], "total": len(lectura["paginas"]),
            "sin_leer": guardada["sin_leer"], "guardada": guardada["momento"]}
    ia = evaluador.estado_ia()
    if b1.button("Extraer 3 requisitos con IA", icon=":material/auto_awesome:", type="primary",
                 disabled=not (lectura["evaluable"] and seguir and ia["disponible"]), key=f"extraer_{clave}",
                 help=None if ia["disponible"] else ia["detalle"]):
        with st.spinner("Leyendo las páginas relevantes y comprobando cada cita en el texto…"):
            try:
                paginas = evaluador.seleccionar_paginas(lectura)
                resultado = evaluador.extraer_requisitos(lectura, paginas)
                st.session_state[f"req_{clave}"] = {
                    "requisitos": evaluador.verificar(resultado["requisitos"], lectura["paginas"], lectura["ocr"]),
                    "modelo": resultado["modelo"], "segundos": resultado["segundos"],
                    "costo_usd": resultado["costo_usd"], "enviadas": resultado["paginas_enviadas"],
                    "total": len(lectura["paginas"]), "sin_leer": list(lectura["sin_leer"])}
            except evaluador.ErrorIA as e:
                st.session_state[f"req_{clave}"] = {"error": str(e)}
    if not ia["disponible"]:
        st.caption(ia["detalle"])
    res = st.session_state.get(f"req_{clave}")
    if not res:
        return
    if "error" in res:
        st.error(f"No se pudieron extraer los requisitos: {res['error']}.", icon=":material/error:")
        return
    checklist(res, clave)


def checklist(res, clave):
    marcados = []
    for i, r in enumerate(res["requisitos"], 1):
        verificado = r["estado"] == evaluador.VERIFICADO
        with st.container(border=True):
            st.markdown(f"**{i}. {md(r['requisito'])}**")
            c1, c2 = st.columns(2)
            c1.badge(r["estado"], color="green" if verificado else "orange",
                     icon=":material/verified:" if verificado else ":material/help:")
            c2.badge(r["momento"], color="blue" if r["momento"] == "Con la oferta" else "violet",
                     icon=":material/send:" if r["momento"] == "Con la oferta" else ":material/handshake:")
            st.markdown(f"**Qué se pide:** {md(r['que_se_pide'])}  \n"
                        f"**Dónde:** página {r['pagina']} del PDF ({r['origen']}) · {md(r['seccion'])}")
            st.markdown("> " + md(r["fragmento"]))
            if r["respaldos"]:
                filas = []
                for c in r["respaldos"]:
                    marca = "✅" if c["estado"] == evaluador.VERIFICADO else "❔"
                    filas.append(f"- {marca} **{md(c['dato'])}** — página {c['pagina']} ({c['origen']}) · "
                                 f"{md(c['seccion'])}: «{md(c['fragmento'])}»"
                                 + ("" if c["estado"] == evaluador.VERIFICADO else f" — _{md(c['verificacion'])}_"))
                st.markdown("**Respaldos en las bases**\n\n" + "\n".join(filas))
            st.caption(f"Comprobación: {md(r['verificacion'].rstrip('. '))}.")
            marcados.append(st.checkbox("Lo tengo", key=f"tengo_{clave}_{i}"))
    lista = evaluador.resumen_lista(res["requisitos"], marcados)
    lineas = [f"- **{etiqueta}, sin marcar:** " + "; ".join(md(n) for n in nombres)
              for etiqueta, nombres in lista["sin_marcar"].items()]
    if lista["por_verificar"]:
        lineas.append("- **Por verificar en las bases** (aunque lo marques): "
                      + "; ".join(md(n) for n in lista["por_verificar"]))
    with st.container(border=True):
        st.markdown(f"**Tu lista: {lista['titulo']}**")
        if lineas:
            st.markdown("\n".join(lineas))
    enviadas = res.get("enviadas") or []
    if res.get("comprobado"):
        origen = (f"Extracción guardada del {res['guardada']}, hecha antes con {res['modelo']} (salida estructurada); "
                  f"no se llamó al modelo. Las citas se comprobaron contra el PDF en local el {res['comprobado']}. "
                  "En esa corrida se ")
    elif res.get("guardada"):
        origen = (f"Extracción guardada del {res['guardada']}, hecha antes con {res['modelo']} (salida estructurada); "
                  "ahora no se llamó al modelo y las citas se volvieron a comprobar contra el PDF. En esa corrida se ")
    else:
        origen = f"Extraído con {res['modelo']} (salida estructurada). Se "
    st.caption(f"{origen}enviaron {len(enviadas)} de {res.get('total')} páginas, con su número original "
               f"({evaluador.rangos(enviadas)}) · {res['segundos']:.0f} s · costo de referencia "
               f"US$ {res.get('costo_usd') or 0:.2f}. Revisa siempre las bases completas antes de postular.")
    if res.get("sin_leer"):
        st.warning(f"Análisis incompleto: las páginas {evaluador.rangos(res['sin_leer'])} son imágenes que aún no "
                   "tenían OCR al extraer; lo que digan (por ejemplo, partes del requerimiento) no se analizó.",
                   icon=":material/document_scanner:")


st.set_page_config(page_title="LicitaPerú", page_icon="🔎", layout="centered")
st.title("LicitaPerú")
st.caption("Compras públicas para pequeños proveedores: encuentra oportunidades y mira qué te falta para postular.")

ia = evaluador.estado_ia()
st.session_state.setdefault("ejemplo", False)
e1, e2 = st.columns([2, 3], vertical_alignment="center")
if st.session_state.ejemplo:
    if e1.button("Volver al radar", icon=":material/arrow_back:"):
        st.session_state.ejemplo = False
        st.rerun()
elif e1.button("Ver caso de ejemplo", icon=":material/menu_book:"):
    st.session_state.ejemplo = True
    st.rerun()
e2.caption(("✅ " if ia["disponible"] else "⚠️ ") + ia["detalle"])

if st.session_state.ejemplo:
    caso = evaluador.cargar_caso_ejemplo()
    st.info("**Caso de ejemplo:** licitación real de la Municipalidad Metropolitana de Lima con una **extracción "
            "guardada**. No necesitas subir el PDF, ni OCR, ni una clave de API: las citas ya se comprobaron contra "
            "las bases. Los datos del proceso son los del SEACE; el estado se calcula con la fecha de hoy.",
            icon=":material/menu_book:")
    ficha(radar.procesos(caso["filas_seace"])[0], caso=caso)
    st.caption("LicitaPerú es un proyecto independiente: usa datos públicos del SEACE (OECE) y no representa al "
               "Estado.")
    st.stop()

c1, c2 = st.columns([3, 2])
palabras = c1.text_input("Palabras clave", value="ferretería",
                         help="Busca en el código, la entidad, la síntesis y los ítems, sin importar tildes.")
departamento = c2.selectbox("Departamento (según el SEACE)", ["Todo el Perú"] + list(radar.DEPARTAMENTOS.values()))
c3, c4 = st.columns([3, 2])
objeto = c3.selectbox("Objeto", ["Todos", "Bien", "Servicio", "Obra", "Consultoría de Obra"])
solo_abiertos = c4.toggle("Solo con registro abierto", value=True)

codigo_dep = next((c for c, n in radar.DEPARTAMENTOS.items() if n == departamento), "0")
try:
    with st.spinner("Consultando el SEACE…"):
        lista, consultado, origen = cargar(codigo_dep)
except radar.ErrorFuente as e:
    st.error(f"No se pudo consultar el radar. {e} Puedes abrir el caso de ejemplo.", icon=":material/cloud_off:")
    if st.button("Reintentar"):
        cargar.clear()
        st.rerun()
    st.stop()

lugar = "todo el Perú" if codigo_dep == "0" else departamento
if origen == radar.VIVO:
    fuente = (f"Fuente: [SEACE · Oportunidades de negocio]({radar.URL_APP_OFICIAL}) (API pública) · consultado el "
              f"{radar.texto_fecha(consultado)} · {len(lista):,} procesos vigentes en {lugar}")
else:
    tipo = "copia local" if origen == radar.COPIA else "copia de respaldo publicada con la app"
    st.warning(f"El SEACE no respondió desde este servidor. Se muestran **datos de respaldo** ({tipo}) consultados "
               f"el **{radar.texto_fecha(consultado)}**: pueden estar desactualizados.", icon=":material/history:")
    if st.button("Reintentar con el SEACE"):
        cargar.clear()
        st.rerun()
    fuente = (f"Fuente: [SEACE · Oportunidades de negocio]({radar.URL_APP_OFICIAL}) · {tipo} del "
              f"{radar.texto_fecha(consultado)} · {len(lista):,} procesos en {lugar}")
st.caption(fuente)

resultados = radar.filtrar(lista, palabras, None if objeto == "Todos" else objeto, solo_abiertos)
if not resultados:
    st.info("No hay procesos que coincidan. Prueba con otra palabra, otro departamento o desactiva «Solo con registro "
            "abierto».")
    st.stop()

tabla = pd.DataFrame([{"Registro": radar.estado(p)[0], "Registro hasta": radar.texto_fecha(p["registro_fin"]),
                       "Código": p["codigo"], "Entidad": p["entidad"],
                       "Propuestas": radar.texto_propuestas(p), "Objeto": p["objeto"]} for p in resultados])
st.markdown(f"**{len(resultados)} procesos** coinciden")
st.dataframe(tabla, hide_index=True, width="stretch")

por_id = {p["id"]: p for p in resultados}
elegido = st.selectbox("Abrir la ficha del proceso", list(por_id),
                       format_func=lambda i: f"{por_id[i]['codigo']} · {por_id[i]['entidad'][:60]}")
ficha(por_id[elegido])
st.caption("LicitaPerú es un proyecto independiente: usa datos públicos del SEACE (OECE) y no representa al Estado.")
