# Incidencias de fuente — Tema N.º 42

**Autor:** Alejandro Soto Antezana · **Código:** 2024200531K · **Curso:** Finanzas I (055D), Unidad I, 2026-II
**Fecha de extracción:** 26/09/2026 · **Evidencia:** `log_ejecucion.txt` (ejecución final de las 13:34)

Este archivo registra los problemas técnicos que se presentaron durante la extracción. **Ninguno fue un bloqueo del portal**: no hubo respuestas 401/403, no hubo rutas prohibidas por `robots.txt` y no fue necesario solicitar sustitución de fuente (numeral 2.4.3).

## Incidencia 1 — Edición de enero de 2025 no publicada en el archivo histórico de Damodaran

| Campo | Detalle |
|---|---|
| Fuente | NYU Stern — A. Damodaran, EV/EBITDA por industria, mercados emergentes |
| URL | `https://pages.stern.nyu.edu/~adamodar/pc/archives/vebitdaemerg25.xls` |
| Fecha y hora | 26/09/2026 13:34:37 (línea del log: `GET ... vebitdaemerg25.xls -> HTTP 404`) |
| Código HTTP | **404** (el archivo no existe en el servidor) |
| robots.txt | La ruta está permitida; el script lo verificó antes de solicitarla |
| Qué hizo el código | Registró el error y continuó con los demás archivos (no se detuvo) |
| Tratamiento | Para los días de 2025 se mantiene la última edición publicada antes de cada fecha (enero de 2024). La edición vigente de enero de 2026, con datos al cierre de 2025, sí se descargó (`datasets/vebitdaemerg.xls`, HTTP 200) y se usa en la comparación de la Tabla 5 del artículo |
| ¿Requiere sustitución? | No. La fuente funciona; solo falta un archivo histórico |

## Incidencia 2 — Errata en el encabezado de la edición 2018

| Campo | Detalle |
|---|---|
| URL | `https://pages.stern.nyu.edu/~adamodar/pc/archives/vebitdaemerg18.xls` |
| Código HTTP | 200 (descarga correcta) |
| Problema | La fuente escribe el título de la columna como «Induistry Name» en lugar de «Industry Name». En la primera ejecución (26/09/2026 12:08:45) el script no encontró la industria y el log registró «0 columnas extraídas» |
| Solución | Se corrigió el código (función `es_titulo_industria` de `02_scraping_web.py`) para reconocer cualquier título que empiece con «Ind» y termine con «Name». En la ejecución final (13:34:27) se extrajeron 10 columnas |
| ¿Se editó el archivo original? | No. El `.xls` se conserva intacto en `/datos_crudos/damodaran` |

## Incidencia 3 — Valores «n.d.» en BCRPData

| Campo | Detalle |
|---|---|
| Fuente | BCRPData, series PD04701XD, PD04702XD y PD04638PD (HTTP 200 en las tres) |
| Problema | En días sin cotización, la API devuelve el texto «n.d.» (no disponible) |
| Tratamiento | `03_limpieza_datos.py` convierte los 136 «n.d.» a faltantes. Al unir con Yahoo Finance se eliminan los 98 días con algún faltante; no se imputa ningún valor |
