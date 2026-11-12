# LicitaPerú · Paso 1: verificación de fuentes y caso para la demo

Consulta: 2026-11-11, entre 22:05 y 22:15 (hora de Lima). Todo lo de abajo se comprobó descargando o consultando la fuente; lo que no se pudo abrir figura como bloqueo.

## Fuentes oficiales

| Fuente | URL | Formato | Resultado | Para qué sirve |
|---|---|---|---|---|
| SEACE · Oportunidades de negocio (API pública que usa la app oficial) | `https://prod4.seace.gob.pe:8086/api/oportunidades/codObjeto/codDepartamento/sintesisProceso/codTipoProceso/0/0/0/0` (app: https://prod4.seace.gob.pe/openegocio/) | JSON, 4.8 MB | **Abre (HTTP 200).** 3,192 ítems de 2,559 procedimientos **vigentes**; propuestas entre 22-10-2026 y 18-12-2026 | Radar de procesos **abiertos** |
| OECE · Portal de Datos Abiertos (CONOSCE), conjunto «Convocatorias» 2026 | https://conosce.osce.gob.pe/buscador/assets/67ae6c4a/reportes/convocatorias/2026/CONVOCATORIAS2026_0.xlsx (portal: https://bi.seace.gob.pe/pentaho/api/repos/%3Apublic%3Aportal%3Adatosabiertos.html/content?userid=public&password=key) | XLSX, 10.8 MB, actualizado 06-11-2026 | **Abre.** 47,407 ítems / 43,238 convocatorias del 05-01 al 30-10-2026. **Solo procedimientos ya adjudicados** (lo dice el portal; estados: Contratado, Consentido, Adjudicado; 0 con propuestas después del 11-11) | Histórico |
| OECE · CONOSCE «Adjudicaciones» 2026 | https://conosce.osce.gob.pe/buscador/assets/67ae6c4a/reportes/adjudicaciones/2026/ADJUDICACIONES2026_0.xlsx | XLSX, 10.6 MB | **Abre.** 47,512 ítems, con proveedor ganador y monto adjudicado | Inteligencia comercial |
| OECE · Diccionario de datos | https://conosce.osce.gob.pe/buscador/assets/67ae6c4a/reportes/Diccionario.xlsx | XLSX | Abre (23 hojas, una por conjunto) | Definición de campos |
| OECE · Portal de Contrataciones Abiertas (OCDS) | https://contratacionesabiertas.oece.gob.pe/api/v1/releases | JSON (OCDS) | **Bloqueado: HTTP 403** a clientes no navegador | — |
| SEACE · descarga de documentos (bases) | `https://prod1.seace.gob.pe/SeaceWeb-PRO/SdescargarArchivoAlfresco?fileCode=<documentoBase>` | PDF (esperado) | **Bloqueado: HTTP 403** a clientes no navegador. No se intentó esquivar | Evaluador de requisitos |

Licencia de los datos OCDS del OECE: CC BY 4.0 (Open Contracting Data Registry, publicación 135).

## Campos reales

**Oportunidades (abiertos):** idProcedimiento, detEntidad, detTipoProceso, detModalidadSeleccion, nomenclatura, numProceso, anhoProceso, siglasProceso, codObjeto/detObjeto, valorReferencial (sale «---»), monedaProceso, fechaConvocatoria, fecInicioParticipantes, fecFinParticipantes, fechaPresentacionPropuestas, **documentoBase** (código del archivo de bases), ubigeo (código interno, no INEI), nroItem, detItem, tipoItem (ITEM/PAQUETE), codCubso/detCubso, cantItem, detUnidadMedida, valorReferencialItem («---»), sintesisProceso, versionSeace, estadoItem. urlProceso y urlBases vienen vacíos.

**CONOSCE Convocatorias (históricos):** CODIGOENTIDAD, ENTIDAD_RUC, ENTIDAD, TIPOENTIDAD, CODIGOCONVOCATORIA, DESCRIPCION_PROCESO, PROCESO (nomenclatura), TIPOCOMPRA, OBJETOCONTRACTUAL, SECTOR / NIVEL DE GOBIERNO, SISTEMA_CONTRATACION, TIPOPROCESOSELECCION, MONTOREFERENCIAL, N_ITEM, DESCRIPCION_ITEM, UNIDAD_MEDIDA, ESTADOITEM, PAQUETE, CODIGOITEM, ITEMCUBSO, MONTO_REFERENCIAL_ITEM, MONEDA, DEPARTAMENTO/PROVINCIA/DISTRITO_ITEM, FECHA_CONVOCATORIA, FECHAINTEGRACIONBASES, FECHAPRESENTACIONPROPUESTA. Sin enlaces a documentos.

**CONOSCE Adjudicaciones:** además, CANTIDAD_ADJUDICADO_ITEM, MONTO_REFERENCIAL_ITEM_SOLES, MONTO_ADJUDICADO_ITEM_SOLES, RUC PROVEEDOR, PROVEEDOR, TIPO_PROVEEDOR, FECHA_BUENAPRO, FECHA_CONSENTIMIENTO_BP.

Rubro en 2026 (adjudicados, bienes de ferretería, materiales eléctricos o herramientas, por palabras clave): 354 ítems en 321 convocatorias, S/ 71.5 millones, mediana S/ 95,221 por ítem, 274 proveedores distintos (63 personas naturales).

## Caso elegido (ABIERTO, no histórico)

| Campo | Valor (fuente: API de Oportunidades del SEACE) |
|---|---|
| Identificador | **LP-SM-16-2026-MML-OGA-OL-1** · idProcedimiento 1262798 |
| Entidad | Municipalidad Metropolitana de Lima |
| Tipo | Licitación Pública (sin modalidad) · objeto: Bien · 1 paquete |
| Objeto | Adquisición de materiales ferreteros, repuestos y accesorios para el PIP «Mejoramiento del servicio de movilidad urbana en las vías locales del eje estructurante Áncash y Junín en el Centro Histórico de Lima…» (CUI 2629…, cortado en la fuente) |
| Ubicación | Centro Histórico de Lima, distrito, provincia y departamento de Lima (según la síntesis del proceso) |
| Plazos | Convocatoria 03-11-2026 13:19 · registro de participantes 04-11-2026 00:01 a **09-12-2026 23:59** · presentación de propuestas **10-12-2026 00:01** |
| Valor referencial | No publicado en la fuente («---») |
| Documento (bases) | https://prod1.seace.gob.pe/SeaceWeb-PRO/SdescargarArchivoAlfresco?fileCode=db513705-7e82-4501-9564-6c0c34cc7893 — **Por verificar** (403 para descarga automática) |

Respaldo: **LP-ABR-1-2026-MIDAGRI-3** (Ministerio de Desarrollo Agrario y Riego), materiales de ferretería y seguridad, herramientas e instrumentos para sedes en Lima; registro hasta 23-11-2026 23:59, propuestas 24-11-2026 00:01; bases: https://prod1.seace.gob.pe/SeaceWeb-PRO/SdescargarArchivoAlfresco?fileCode=bceb1d64-bbd3-47c9-8d20-ed3248608f20 (Por verificar).

## Paso 2 (11-11-2026, 22:20–22:30): lo que se comprobó al construir el radar

- **Filtro por departamento:** la API filtra en el servidor con el código INEI del departamento (`.../0/15/0/0` = Lima: 856 procesos). Revisado en Lima, Arequipa, Puno y Cusco: las entidades corresponden al departamento y todo está contenido en la consulta nacional. El campo `ubigeo` de cada fila es un código interno y no se usa. La lista oficial de departamentos (`/api/personas/departamento`) pide sesión (401).
- **Fechas:** en 299 de 3,192 ítems (247 subastas inversas, 51 adjudicaciones selectivas) la fecha de propuestas va antes del cierre del registro. El estado se calcula con la ventana de registro de participantes; esa fecha de propuestas se muestra «por verificar».
- **Ficha pública:** el SEACE 3.0 abre la ficha navegando desde el buscador público (https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml, HTTP 200); no se encontró una URL directa estable por proceso, así que no se inventa.
- **Bases:** el enlace oficial es el que arma la app «Oportunidades de negocio» con `documentoBase`; la descarga automática sigue en 403.

## Requisitos

| # | Requisito | Página / sección | Estado |
|---|---|---|---|
| 1 | — | — | Por verificar: falta abrir las bases |
| 2 | — | — | Por verificar |
| 3 | — | — | Por verificar |
