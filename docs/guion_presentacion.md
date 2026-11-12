# Guion · LicitaPerú en 3 minutos

La demo corre en local en http://localhost:8503 con datos reales. La extracción con IA **se ejecutó antes** (11/11/2026 23:07: 16 páginas, 60 s, US$ 0.37) y se muestra con «Usar la extracción guardada», sin volver a llamar al modelo.

## Antes de tu turno (5 minutos antes)

1. En PowerShell: `cd C:\Users\usuario\licitaperu` y `uv run streamlit run app.py --server.port 8503`. Abre http://localhost:8503.
2. **Departamento (según el SEACE)** → **Lima**.
3. **Abrir la ficha del proceso** → **LP-SM-16-2026-MML-OGA-OL-1**.
4. **Bases del proceso (PDF)** → Browse files → `C:\Users\usuario\licitaperu\docs\bases\LP-SM-16-2026-MML-OGA-OL-1_bases.pdf`.
5. Pulsa **«Usar la extracción guardada»**. Deja las casillas «Lo tengo» **sin marcar**.
6. Sube al inicio de la página y ten el cronómetro listo. Si falla internet, el radar usa la última copia guardada y lo avisa.

## 0:00 – 0:30 · El problema

> «Una ferretería que quiere venderle al Estado tiene que leer bases como estas: 96 páginas, 27 escaneadas. En este proceso de la Municipalidad de Lima, el requisito que decide si puedes postular —haber facturado 1.5 millones de soles en 10 años— está en una página escaneada. Y si te falta un documento, tu oferta no es admitida. Solo en 2026 se adjudicaron 321 compras de ferretería y materiales eléctricos, por 71 millones de soles, y las ganaron 274 proveedores.»

## 0:30 – 2:30 · La demo

**0:30 – 0:55 · Radar en Lima** (arriba de la página)

> «LicitaPerú consulta en vivo los procesos abiertos del SEACE. Busco “ferretería” en Lima: hay 3 con el registro abierto. Abro el de la Municipalidad de Lima: registro abierto hasta el 9 de diciembre y plazo de propuestas aparte, el 10.»

**0:55 – 1:25 · El PDF** (baja a «¿Qué te piden para postular?»)

> «El SEACE no deja descargar las bases de forma automática, así que el proveedor las sube. La app comprueba que sean de este proceso y detecta que 27 páginas son imágenes: les hace OCR. Luego envía al modelo solo las 16 páginas relevantes. Esta extracción la corrí antes: tardó un minuto y costó 37 centavos de dólar.»

**1:25 – 2:05 · La contradicción** (baja a la tarjeta **2. Documentos para la admisión de la oferta**)

> «Cada requisito trae sus respaldos, con página y cita, y la app busca cada cita en el PDF. Mira la admisión: las páginas 22 y 23 listan los anexos obligatorios, pero la página 46, escaneada, pide además fichas técnicas o catálogos, y la página 22 prohíbe agregar documentos. Por eso no dice “cumples”: dice “Por verificar”. Lo prudente es presentarlas o hacer la consulta.»

**2:05 – 2:30 · El checklist** (marca «Lo tengo» en **Experiencia** y en **Garantía**; baja a «Tu lista»)

> «El proveedor marca lo que ya tiene. La lista dice: 2 de 3 marcados, 3 por verificar en las bases. Marcar no cambia lo verificado, y queda claro qué falta para la oferta.»

## 2:30 – 3:00 · El negocio

> «Quién paga: el pequeño proveedor. Nuestra hipótesis es S/ 39 al mes con 10 evaluaciones; cada evaluación nos cuesta unos 37 centavos de dólar, y si varios proveedores revisan el mismo proceso, el costo se comparte. Lo que sigue: tres conversaciones con proveedores para validar el precio y publicar el evaluador en una URL con tope de gasto. LicitaPerú: encuentra la compra y sabe qué te falta.»

---

# Video de respaldo (60–90 s)

Grábalo con la misma preparación (pasos 1–5) y la herramienta de grabación de pantalla de Windows (Win + Alt + R con la Xbox Game Bar, o la grabación de la Herramienta Recortes). Narra en voz baja o agrega subtítulos.

| Tiempo | Pantalla | Qué decir |
|---|---|---|
| 0:00 – 0:10 | Arriba: título, filtros, «3 procesos coinciden» en Lima | «LicitaPerú: compras públicas abiertas del SEACE, en vivo.» |
| 0:10 – 0:22 | Ficha del caso MML: «Registro abierto», plazo de propuestas | «Registro abierto hasta el 9 de diciembre; propuestas el 10.» |
| 0:22 – 0:37 | Avisos del PDF: corresponde al proceso, versión, lectura parcial con OCR | «Las bases tienen 27 páginas escaneadas: la app les hace OCR.» |
| 0:37 – 0:60 | Tarjeta 2: respaldos de las páginas 22–23 y 46 y la comprobación | «Cada cita está en el PDF. Las páginas 22 y 23 no piden fichas técnicas; la 46 sí. Por eso: Por verificar.» |
| 0:60 – 0:75 | Marcar «Lo tengo» en Experiencia y Garantía; «Tu lista» | «2 de 3 marcados, 3 por verificar en las bases.» |
| 0:75 – 0:85 | Pie: «Extracción guardada… 16 de 96 páginas · 60 s · US$ 0.37» | «Extracción ejecutada antes: 16 páginas, un minuto, 37 centavos.» |
