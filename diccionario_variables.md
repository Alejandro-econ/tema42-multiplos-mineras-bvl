# Diccionario de variables — datos_procesados_2024200531K.csv

**Autor:** Alejandro Soto Antezana · **Código:** 2024200531K · **Tema 42:** Múltiplos de valoración de las mineras listadas en la BVL: P/E, P/B y EV/EBITDA
**Unidad de observación:** día hábil común a la Bolsa de Nueva York y al BCRP · **Periodo:** 05/01/2015 – 31/12/2025 (primer y último día con datos) · **Empresa:** Southern Copper Corporation (SCCO), emisor listado en la BVL.

**Rol en el modelo:** Y = variable endógena (la que se explica); X = variable exógena (la que explica).

| Variable | Rol | Definición | Unidad | Frecuencia | Fuente exacta | URL o endpoint de origen |
|---|---|---|---|---|---|---|
| fecha | llave | Día de negociación (llave común de unión) | AAAA-MM-DD | Diaria | Yahoo Finance y BCRP | — |
| ticker | identificador | Símbolo bursátil de la empresa | texto | — | Yahoo Finance | `yfinance.Ticker("SCCO")` |
| precio_accion_usd | insumo | Precio de cierre de la acción, sin ajuste por splits | US$ por acción | Diaria | Yahoo Finance | `yfinance.Ticker("SCCO").history(start, end, auto_adjust=False)` |
| acciones_mill | insumo | Acciones comunes en circulación (último reporte publicado) | millones de acciones | Trimestral, llevada a diaria | SEC EDGAR (dei:EntityCommonStockSharesOutstanding) | `https://data.sec.gov/api/xbrl/companyfacts/CIK0001001838.json` |
| cap_bursatil_musd | insumo | Capitalización bursátil = precio × acciones | millones de US$ | Diaria | Cálculo propio (Yahoo + SEC) | — |
| patrimonio_musd | insumo | Patrimonio de los accionistas (us-gaap:StockholdersEquity) | millones de US$ | Trimestral, llevada a diaria | SEC EDGAR | mismo endpoint SEC |
| deuda_total_musd | insumo | Deuda financiera total (us-gaap:LongTermDebt) | millones de US$ | Trimestral, llevada a diaria | SEC EDGAR | mismo endpoint SEC |
| caja_musd | insumo | Efectivo y equivalentes (us-gaap:CashAndCashEquivalentsAtCarryingValue) | millones de US$ | Trimestral, llevada a diaria | SEC EDGAR | mismo endpoint SEC |
| deuda_neta_musd | descriptiva | Deuda total − caja | millones de US$ | Diaria | Cálculo propio | — |
| valor_empresa_musd | insumo | EV = capitalización + deuda neta | millones de US$ | Diaria | Cálculo propio | — |
| utilidad_neta_ttm_musd | insumo | Utilidad neta de los últimos 12 meses (4 trimestres) | millones de US$ | Trimestral, llevada a diaria | SEC EDGAR (us-gaap:NetIncomeLoss; respaldo ProfitLoss) | mismo endpoint SEC |
| ebitda_ttm_musd | insumo | EBITDA 12 meses = utilidad operativa + depreciación y amortización | millones de US$ | Trimestral, llevada a diaria | SEC EDGAR (OperatingIncomeLoss + DepreciationDepletionAndAmortization) | mismo endpoint SEC |
| pe | descriptiva | P/E = capitalización ÷ utilidad neta 12 meses | veces | Diaria | Cálculo propio | — |
| pb | descriptiva | P/B = capitalización ÷ patrimonio | veces | Diaria | Cálculo propio | — |
| **ev_ebitda** | **Y (endógena)** | EV/EBITDA = valor de empresa ÷ EBITDA 12 meses | veces | Diaria | Cálculo propio | — |
| ev_ebitda_sector_damodaran | referencia | EV/EBITDA de la industria Metals & Mining, mercados emergentes, empresas con EBITDA positivo (edición de enero de cada año) | veces | Anual, llevada a diaria | NYU Stern – A. Damodaran | `https://pages.stern.nyu.edu/~adamodar/pc/archives/vebitdaemergAA.xls` |
| **precio_cobre_usd_lb** | **X1 (exógena)** | Cotización internacional del cobre, Londres (serie PD04701XD, dividida entre 100) | US$ por libra | Diaria | BCRPData | `https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PD04701XD/json/2015-01-01/2025-12-31` |
| **precio_plata_usd_oz** | **X2 (exógena)** | Cotización internacional de la plata, H. Harman (serie PD04702XD) | US$ por onza troy | Diaria | BCRPData | `.../api/PD04702XD/json/2015-01-01/2025-12-31` |
| **tipo_cambio_pen_usd** | **X3 (exógena)** | Tipo de cambio interbancario, venta (serie PD04638PD) | soles por US$ | Diaria | BCRPData | `.../api/PD04638PD/json/2015-01-01/2025-12-31` |
| fecha_ultimo_reporte_sec | control | Fecha de cierre del último estado financiero ya publicado ese día | AAAA-MM-DD | Diaria | SEC EDGAR | mismo endpoint SEC |
| atipico_pe / atipico_pb / atipico_ev_ebitda | control | 1 si el múltiplo está fuera de [Q1 − 3·RIC ; Q3 + 3·RIC]; 0 si no | 0 / 1 | Diaria | Cálculo propio | — |

**Nota sobre la frecuencia.** Los estados financieros se publican cada trimestre. Cada día se usa el último estado financiero que ya era público (fecha de presentación ante la SEC + 1 día). Por eso el múltiplo cambia a diario con el precio, y su denominador cambia cuando se publica un nuevo reporte.
