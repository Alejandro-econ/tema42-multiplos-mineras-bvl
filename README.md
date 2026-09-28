# Múltiplos de valoración de las mineras listadas en la BVL: P/E, P/B y EV/EBITDA

| Dato | Detalle |
|---|---|
| Nombres y apellidos | Alejandro Soto Antezana |
| Código de matrícula | 2024200531K |
| Curso | Finanzas I (055D) — Unidad I — 2026-II |
| Universidad | Universidad Nacional del Centro del Perú, Facultad de Economía |
| Tema del temario | N.º 42 — Múltiplos de valoración de las mineras listadas en la BVL: P/E, P/B y EV/EBITDA |
| Empresa analizada | Southern Copper Corporation (SCCO), emisor listado en la Bolsa de Valores de Lima |
| Periodo (parámetros congelados) | FECHA_INICIO = 2015-01-01 · FECHA_CORTE = 2025-12-31 (primer día con datos: 05/01/2015) |
| Repositorio GitHub | https://github.com/Alejandro-econ/tema42-multiplos-mineras-bvl |

## Pregunta de investigación

¿Cómo han evolucionado los múltiplos P/E, P/B y EV/EBITDA de Southern Copper frente al sector minero de mercados emergentes, y en qué medida el EV/EBITDA se relaciona con el precio del cobre, el precio de la plata y el tipo de cambio?

Modelo (1 endógena y 3 exógenas, en logaritmos):
`ln(EV/EBITDA)_t = b0 + b1·ln(Cobre)_t + b2·ln(Plata)_t + b3·ln(TipoCambio)_t + u_t`

## Fuentes y endpoints

| Vía | Fuente | Endpoint o URL | ¿Clave? |
|---|---|---|---|
| 1 · API | BCRPData (BCRP) — series PD04701XD (cobre), PD04702XD (plata), PD04638PD (tipo de cambio) | `https://estadisticas.bcrp.gob.pe/estadisticas/series/api/{codigo}/json/2015-01-01/2025-12-31` | No |
| 1 · API | Yahoo Finance (librería yfinance) — ticker SCCO | `yfinance.Ticker("SCCO").history(start="2015-01-01", end="2026-01-01", auto_adjust=False, actions=True)` | No |
| 1 · API | SEC EDGAR, API XBRL — Southern Copper, CIK 0001001838 | `https://data.sec.gov/api/xbrl/companyfacts/CIK0001001838.json` | No (exige User-Agent con nombre y correo, ver .env.example) |
| 2 · Descarga programática | NYU Stern — A. Damodaran, múltiplos por industria (Emerging Markets) | `https://pages.stern.nyu.edu/~adamodar/pc/archives/vebitdaemergAA.xls` (AA = 15 … 25) y `https://pages.stern.nyu.edu/~adamodar/pc/datasets/{vebitdaemerg, pbvemerg, peemerg}.xls` | No |

**Llave común de unión:** la fecha (día). Los estados financieros trimestrales (SEC) y la referencia anual (Damodaran) se llevan a frecuencia diaria usando el último dato ya publicado en cada fecha.

## Orden de ejecución

Desde la carpeta raíz del proyecto:

```
pip install -r requirements.txt
cp .env.example .env          # luego escribir nombre y correo en .env
python codigo/01_extraccion_api.py
python codigo/02_scraping_web.py
python codigo/03_limpieza_datos.py
python codigo/04_analisis.py
```

| Script | Qué produce |
|---|---|
| 01_extraccion_api.py | datos_crudos/datos_crudos_bcrp_2024200531K.csv, datos_crudos_yahoo_2024200531K.csv, datos_crudos_sec_2024200531K.csv y el JSON original de la SEC |
| 02_scraping_web.py | datos_crudos/damodaran/*.xls (originales) y datos_crudos/datos_crudos_damodaran_2024200531K.csv |
| 03_limpieza_datos.py | datos_procesados/datos_procesados_2024200531K.csv, datos_procesados/benchmark_actual_damodaran_2024200531K.csv y salidas/hash_sha256_datos_procesados.txt |
| 04_analisis.py | salidas/tabla0 … tabla7 (.csv), modelos (.txt) y figura1 … figura3 (.png) |

## Versiones

- Lenguaje: Python 3.13.15 (Google Colab).
- Librerías: ver requirements.txt (versiones exactas del entorno donde se ejecutó).

## Verificación de integridad

- Archivo: `datos_procesados/datos_procesados_2024200531K.csv`
- Hash SHA-256: 45c559e713655211fabcdbe241458dd1cd5c165f17b3d37f714bd3e349e978fa

## Notas de reproducibilidad

- Las fechas de consulta son constantes (FECHA_INICIO y FECHA_CORTE); no se usan fechas dinámicas.
- Los datos crudos no se editan. Toda transformación está en 03_limpieza_datos.py.
- La edición de enero de 2025 del archivo de Damodaran no está publicada en su archivo histórico (respuesta HTTP 404 al 26/09/2026); para 2025 se usa la última edición disponible (enero de 2024). Queda registrado en log_ejecucion.txt y en incidencias_fuente.md.
- La edición 2018 de Damodaran rotula la columna de industrias con una errata de la fuente («Induistry Name»); el script 02 la reconoce igual.
- Damodaran publica el EV/EBITDA en dos grupos («Only positive EBITDA firms» y «All firms»). Se usa el grupo de empresas con EBITDA positivo, porque Southern Copper tiene EBITDA positivo en todo el periodo.
- Para el P/E del sector se usa el múltiplo agregado de Damodaran («Aggregate Mkt Cap/ Net Income (all firms)»), comparable con el P/E de Southern Copper (capitalización ÷ utilidad).
- Ética del rastreo: se revisa robots.txt, se usa User-Agent identificable y pausa de 1 segundo entre solicitudes. No se extraen datos personales (Ley N.º 29733).
