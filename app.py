"""LicitaPerú · radar de oportunidades y evaluador de requisitos (demo local).

Iniciar desde la raíz del proyecto:  uv run streamlit run app.py --server.port 8503

Radar: procesos vigentes del SEACE (radar.py). Evaluador: el proveedor sube las bases en PDF; se comprueba que sean
del proceso y que se puedan leer (con OCR guardado para las páginas escaneadas, ocr_bases.py), un LLM con salida
estructurada extrae 3 requisitos y cada cita se contrasta con el texto (evaluador.py).
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
    filas, consultado, desde_copia = radar.descargar(departamento)
    return radar.procesos(filas), consultado, desde_copia


@st.cache_data(show_spinner=False, max_entries=5)
def leer(datos):
    return evaluador.leer_pdf(datos)


def ficha(p):
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
        evaluar(p)


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
    if st.button("Extraer 3 requisitos con IA", icon=":material/auto_awesome:", type="primary",
                 disabled=not (lectura["evaluable"] and seguir), key=f"extraer_{clave}"):
        with st.spinner("Leyendo las bases y comprobando cada cita en el texto… (puede tardar un minuto)"):
            try:
                resultado = evaluador.extraer_requisitos(lectura)
                st.session_state[f"req_{clave}"] = {
                    "requisitos": evaluador.verificar(resultado["requisitos"], lectura["paginas"], lectura["ocr"]),
                    "modelo": resultado["modelo"], "segundos": resultado["segundos"]}
            except evaluador.ErrorIA as e:
                st.session_state[f"req_{clave}"] = {"error": str(e)}
    res = st.session_state.get(f"req_{clave}")
    if not res:
        return
    if "error" in res:
        st.error(f"No se pudieron extraer los requisitos: {res['error']}.", icon=":material/error:")
        return
    checklist(res, clave)


def checklist(res, clave):
    falta = {m: [] for m in evaluador.MOMENTOS}
    revisar, tengo = [], 0
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
            st.caption(f"Comprobación: {md(r['verificacion'].rstrip('. '))}.")
            if st.checkbox("Lo tengo", key=f"tengo_{clave}_{i}"):
                tengo += 1
            elif verificado:
                falta[r["momento"]].append(r["requisito"])
            else:
                revisar.append(r["requisito"])
    total = len(res["requisitos"])
    with st.container(border=True):
        st.markdown(f"**Tu lista: tienes {tengo} de {total}**")
        lineas = []
        etiquetas = {"Con la oferta": "Para la oferta", "Para perfeccionar el contrato": "Para el contrato, si ganas",
                     "No lo indica": "Sin momento indicado"}
        for momento, nombres in falta.items():
            if nombres:
                lineas.append(f"- **{etiquetas[momento]}:** te falta " + "; ".join(md(n) for n in nombres))
        if revisar:
            lineas.append("- **Por verificar en las bases:** " + "; ".join(md(n) for n in revisar))
        st.markdown("\n".join(lineas) if lineas else "No te queda nada pendiente de lo que se extrajo.")
    st.caption(f"Extraído con {res['modelo']} (salida estructurada, {res['segundos']:.0f} s) y comprobado contra el "
               "texto del PDF. Revisa siempre las bases completas antes de postular.")


st.set_page_config(page_title="LicitaPerú", page_icon="🔎", layout="centered")
st.title("LicitaPerú")
st.caption("Compras públicas para pequeños proveedores: encuentra oportunidades y mira qué te falta para postular.")

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
        lista, consultado, desde_copia = cargar(codigo_dep)
except radar.ErrorFuente as e:
    st.error(f"No se pudo consultar el radar. {e}", icon=":material/cloud_off:")
    if st.button("Reintentar"):
        cargar.clear()
        st.rerun()
    st.stop()

fuente = (f"Fuente: [SEACE · Oportunidades de negocio]({radar.URL_APP_OFICIAL}) (API pública) · "
          f"consultado el {radar.texto_fecha(consultado)} · {len(lista):,} procesos vigentes en "
          f"{'todo el Perú' if codigo_dep == '0' else departamento}")
if desde_copia:
    st.warning(f"El SEACE no respondió: se muestra la copia guardada del {radar.texto_fecha(consultado)}.",
               icon=":material/history:")
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
