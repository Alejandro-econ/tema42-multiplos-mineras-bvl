# Nombres y apellidos: Alejandro Soto Antezana
# Código de matrícula: 2024200531K
# Tema del temario: N.º 42 — Múltiplos de valoración de las mineras listadas en la BVL: P/E, P/B y EV/EBITDA
# Fecha de extracción: 2026-09-26
"""
03_limpieza_datos.py  —  DEPURACIÓN, UNIÓN DE FUENTES Y CÁLCULO DE MÚLTIPLOS

Entradas (de /datos_crudos): BCRP, Yahoo Finance, SEC y Damodaran.
Salidas  (en /datos_procesados):
  - datos_procesados_2024200531K.csv          -> base DIARIA del estudio
  - benchmark_actual_damodaran_2024200531K.csv -> múltiplos del sector (enero 2026)
Además calcula el hash SHA-256 de la base diaria.

Idea central (armonización de frecuencias):
  El precio de la acción cambia TODOS los días; los estados financieros se publican
  cada TRIMESTRE. Cada día se usa el último estado financiero que ya era público
  ese día (fecha de presentación ante la SEC + 1 día). Así el múltiplo diario usa
  solo información que el mercado conocía en esa fecha (sin "mirar el futuro").
"""

import hashlib
import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------
# 0. PARÁMETROS CONGELADOS
# --------------------------------------------------------------------------
FECHA_INICIO = "2015-01-01"
FECHA_CORTE = "2025-12-31"
CODIGO = "2024200531K"
TICKER = "SCCO"
FORMULARIOS_VALIDOS = {"10-Q", "10-K", "10-Q/A", "10-K/A"}
FACTOR_IQR = 3.0          # regla para marcar valores atípicos
DIA_PUBLICACION_DAMODARAN = 15   # se asume disponible el 15 de enero de cada edición

RAIZ = Path(__file__).resolve().parent.parent
CRUDOS = RAIZ / "datos_crudos"
PROCESADOS = RAIZ / "datos_procesados"
SALIDAS = RAIZ / "salidas"
PROCESADOS.mkdir(exist_ok=True)
SALIDAS.mkdir(exist_ok=True)
ARCHIVO_LOG = RAIZ / "log_ejecucion.txt"


def registrar(mensaje: str) -> None:
    linea = f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] 03_limpieza_datos | {mensaje}"
    print(linea)
    with ARCHIVO_LOG.open("a", encoding="utf-8") as f:
        f.write(linea + "\n")


# ==========================================================================
# 1. BCRP: fechas en español ("02.Ene.15") y "n.d." como faltante
# ==========================================================================
MESES = {"Ene": 1, "Feb": 2, "Mar": 3, "Abr": 4, "May": 5, "Jun": 6, "Jul": 7,
         "Ago": 8, "Set": 9, "Sep": 9, "Oct": 10, "Nov": 11, "Dic": 12}
NOMBRES_BCRP = {"PD04701XD": "precio_cobre_usd_lb",
                "PD04702XD": "precio_plata_usd_oz",
                "PD04638PD": "tipo_cambio_pen_usd"}


def fecha_bcrp(texto: str) -> pd.Timestamp:
    dia, mes, anio = texto.split(".")
    return pd.Timestamp(year=2000 + int(anio), month=MESES[mes], day=int(dia))


def limpiar_bcrp() -> pd.DataFrame:
    crudo = pd.read_csv(CRUDOS / f"datos_crudos_bcrp_{CODIGO}.csv", dtype=str)
    crudo["fecha"] = crudo["fecha_bcrp"].apply(fecha_bcrp)
    crudo["valor_num"] = pd.to_numeric(crudo["valor"], errors="coerce")  # "n.d." -> NaN
    registrar(f"BCRP: {crudo['valor_num'].isna().sum()} valores 'n.d.' convertidos a faltantes")
    ancho = crudo.pivot_table(index="fecha", columns="codigo_serie", values="valor_num")
    ancho = ancho.rename(columns=NOMBRES_BCRP)
    # El cobre viene en centavos de US$ por libra: se pasa a US$ por libra
    ancho["precio_cobre_usd_lb"] = ancho["precio_cobre_usd_lb"] / 100
    return ancho.reset_index()


# ==========================================================================
# 2. YAHOO FINANCE: precio de cierre SIN ajuste por splits
# ==========================================================================
def limpiar_yahoo() -> pd.DataFrame:
    crudo = pd.read_csv(CRUDOS / f"datos_crudos_yahoo_{CODIGO}.csv")
    crudo["fecha"] = pd.to_datetime(crudo["Date"].astype(str).str[:10])
    crudo = crudo.sort_values("fecha").reset_index(drop=True)
    # Yahoo ajusta el "Close" por splits. Para multiplicar precio x acciones
    # reportadas se necesita el precio real de ese día: se deshace el ajuste.
    splits = crudo.get("Stock Splits", pd.Series(0, index=crudo.index)).fillna(0)
    razon = splits.replace(0, 1.0)
    factor = razon[::-1].cumprod()[::-1].shift(-1).fillna(1.0)
    crudo["precio_accion_usd"] = crudo["Close"] * factor
    registrar(f"Yahoo: {int((splits != 0).sum())} eventos de split detectados")
    return crudo[["fecha", "precio_accion_usd"]]


# ==========================================================================
# 3. SEC: trimestres, últimos 12 meses (TTM) y saldos, con fecha de publicación
# ==========================================================================
def cargar_sec() -> pd.DataFrame:
    sec = pd.read_csv(CRUDOS / f"datos_crudos_sec_{CODIGO}.csv")
    sec = sec[sec["formulario"].isin(FORMULARIOS_VALIDOS)].copy()
    for c in ["inicio", "fin", "fecha_presentacion"]:
        sec[c] = pd.to_datetime(sec[c], errors="coerce")
    # Disponible para el mercado el día siguiente a su presentación
    sec["disponible"] = sec["fecha_presentacion"] + pd.Timedelta(days=1)
    return sec


def trimestres_de_flujo(sec: pd.DataFrame, etiqueta: str) -> pd.DataFrame:
    """
    Cuentas de flujo (utilidad, EBIT, depreciación): la SEC trae trimestres de
    3 meses (10-Q) y el año completo (10-K). El 4.º trimestre se obtiene como
    AÑO - (T1 + T2 + T3). Si un mismo periodo aparece en varios reportes,
    se conserva el primero que se publicó (el valor que el mercado conoció).
    """
    d = sec[sec["etiqueta"] == etiqueta].dropna(subset=["inicio", "fin"]).copy()
    if d.empty:
        return pd.DataFrame(columns=["fin", "valor", "disponible"])
    d["dias"] = (d["fin"] - d["inicio"]).dt.days
    d = d.sort_values("fecha_presentacion").drop_duplicates(["inicio", "fin"], keep="first")

    trimestres = d[d["dias"].between(80, 100)][["inicio", "fin", "valor", "disponible"]]
    anuales = d[d["dias"].between(350, 380)]

    cuartos = []
    for _, anual in anuales.iterrows():
        dentro = trimestres[(trimestres["inicio"] >= anual["inicio"]) &
                            (trimestres["fin"] <= anual["fin"])]
        if (dentro["fin"] == anual["fin"]).any() or len(dentro) != 3:
            continue
        cuartos.append({"inicio": dentro["fin"].max() + pd.Timedelta(days=1),
                        "fin": anual["fin"],
                        "valor": anual["valor"] - dentro["valor"].sum(),
                        "disponible": anual["disponible"]})
    todos = pd.concat([trimestres, pd.DataFrame(cuartos)], ignore_index=True)
    return todos.sort_values("fin").drop_duplicates("fin", keep="first")


def ttm(trimestres: pd.DataFrame, nombre: str) -> pd.DataFrame:
    """Suma de los últimos 4 trimestres consecutivos (Trailing Twelve Months)."""
    t = trimestres.sort_values("fin").reset_index(drop=True)
    t[nombre] = t["valor"].rolling(4).sum()
    salto = (t["fin"] - t["fin"].shift(3)).dt.days
    t.loc[~salto.between(250, 300), nombre] = np.nan   # exige 4 trimestres seguidos
    return t.dropna(subset=[nombre])[["fin", "disponible", nombre]]


def flujo_con_respaldo(sec, etiquetas, nombre) -> pd.DataFrame:
    """Usa la primera etiqueta disponible para cada trimestre (orden de prioridad)."""
    partes = []
    for prioridad, etq in enumerate(etiquetas):
        tri = trimestres_de_flujo(sec, etq)
        if tri.empty:
            registrar(f"Etiqueta {etq} sin datos; se usa la siguiente disponible")
            continue
        tri["prioridad"] = prioridad
        partes.append(tri)
    juntos = pd.concat(partes).sort_values(["fin", "prioridad"])
    juntos = juntos.drop_duplicates("fin", keep="first")
    return ttm(juntos, nombre)


def saldo(sec, etiqueta, nombre) -> pd.DataFrame:
    """Cuentas de saldo (patrimonio, deuda, caja, acciones) a una fecha."""
    d = sec[sec["etiqueta"] == etiqueta].dropna(subset=["fin"]).copy()
    d = d.sort_values("fecha_presentacion").drop_duplicates("fin", keep="first")
    return d.rename(columns={"valor": nombre})[["fin", "disponible", nombre]].sort_values("fin")


def deuda_total(sec) -> pd.DataFrame:
    principal = saldo(sec, "LongTermDebt", "deuda")
    no_corr = saldo(sec, "LongTermDebtNoncurrent", "nc")
    corr = saldo(sec, "LongTermDebtCurrent", "c")
    respaldo = no_corr.merge(corr[["fin", "c"]], on="fin", how="left")
    respaldo["deuda"] = respaldo["nc"] + respaldo["c"].fillna(0)
    respaldo = respaldo[~respaldo["fin"].isin(principal["fin"])]
    return pd.concat([principal, respaldo[["fin", "disponible", "deuda"]]]).sort_values("fin")


def pegar_a_diario(base: pd.DataFrame, tabla: pd.DataFrame, columnas) -> pd.DataFrame:
    """Para cada día, toma el último dato ya publicado (merge_asof hacia atrás)."""
    t = tabla.dropna(subset=["disponible"]).sort_values("disponible").copy()
    t["disponible"] = t["disponible"].astype("datetime64[ns]")
    base = base.copy()
    base["fecha"] = base["fecha"].astype("datetime64[ns]")
    return pd.merge_asof(base.sort_values("fecha"), t[["disponible"] + columnas],
                         left_on="fecha", right_on="disponible",
                         direction="backward").drop(columns="disponible")


# ==========================================================================
# 4. DAMODARAN: referencia del sector
# ==========================================================================
def leer_damodaran():
    crudo = pd.read_csv(CRUDOS / f"datos_crudos_damodaran_{CODIGO}.csv")
    crudo["columna"] = crudo["columna"].astype(str).str.strip()
    if "grupo" not in crudo.columns:
        crudo["grupo"] = ""
    crudo["grupo"] = crudo["grupo"].fillna("").astype(str)

    def primer_valor(sub, nombres):
        for n in nombres:
            v = sub[sub["columna"].str.lower() == n.lower()]["valor"]
            if not v.empty:
                return pd.to_numeric(v.iloc[0], errors="coerce")
        return np.nan

    def ev_ebitda_positivos(sub):
        """
        Damodaran publica dos grupos: 'Only positive EBITDA firms' y 'All firms'.
        Southern Copper siempre tiene EBITDA positivo, así que se compara con el
        grupo de empresas con EBITDA positivo. Si el archivo no trae rótulo de
        grupo (ediciones antiguas), se usa la primera columna EV/EBITDA.
        """
        positivos = sub[sub["grupo"].str.lower().str.contains("positive")]
        return primer_valor(positivos if not positivos.empty else sub, ["EV/EBITDA"])

    # 4.1 Serie anual EV/EBITDA del sector (ediciones 2015-2025)
    hist = []
    for edicion, sub in crudo[(crudo["multiplo_archivo"] == "ev_ebitda") &
                              (crudo["edicion"] <= 2025)].groupby("edicion"):
        hist.append({"disponible": pd.Timestamp(int(edicion), 1, DIA_PUBLICACION_DAMODARAN),
                     "ev_ebitda_sector_damodaran": ev_ebitda_positivos(sub)})
    hist = pd.DataFrame(hist)

    # 4.2 Edición vigente (enero 2026 = datos al cierre de 2025) para la tabla comparativa
    actual = crudo[crudo["edicion"] == 2026]
    fila = {
        "edicion": "Enero 2026 (datos al cierre de 2025)",
        "industria": "Metals & Mining - Emerging Markets",
        # P/E agregado (capitalización total ÷ utilidad total), comparable con el
        # P/E de Southern Copper; el "Trailing PE" es un promedio simple de empresas
        # que se infla con utilidades muy pequeñas.
        "pe_sector": primer_valor(actual[actual["multiplo_archivo"] == "pe"],
                                  ["Aggregate Mkt Cap/ Net Income (all firms)", "Trailing PE"]),
        "pb_sector": primer_valor(actual[actual["multiplo_archivo"] == "pbv"], ["PBV"]),
        "ev_ebitda_sector": ev_ebitda_positivos(actual[actual["multiplo_archivo"] == "ev_ebitda"]),
    }
    pd.DataFrame([fila]).to_csv(PROCESADOS / f"benchmark_actual_damodaran_{CODIGO}.csv",
                                index=False, encoding="utf-8")
    registrar(f"Damodaran: {len(hist)} ediciones históricas; edición vigente = {fila}")
    return hist


# ==========================================================================
# 5. ARMADO DE LA BASE DIARIA
# ==========================================================================
def marcar_atipicos(serie: pd.Series) -> pd.Series:
    q1, q3 = serie.quantile([0.25, 0.75])
    rango = q3 - q1
    return ((serie < q1 - FACTOR_IQR * rango) | (serie > q3 + FACTOR_IQR * rango)).astype(int)


if __name__ == "__main__":
    registrar("INICIO 03_limpieza_datos")

    # 5.1 Llave común = fecha. Solo días con datos en Yahoo y en el BCRP (sin imputar).
    precios = limpiar_yahoo()
    bcrp = limpiar_bcrp()
    base = precios.merge(bcrp, on="fecha", how="inner")
    base = base[(base["fecha"] >= FECHA_INICIO) & (base["fecha"] <= FECHA_CORTE)]
    antes = len(base)
    base = base.dropna(subset=["precio_accion_usd", "precio_cobre_usd_lb",
                               "precio_plata_usd_oz", "tipo_cambio_pen_usd"])
    registrar(f"Unión Yahoo+BCRP: {antes} días comunes; {antes - len(base)} eliminados por faltantes")

    # 5.2 Estados financieros (SEC), llevados a frecuencia diaria
    sec = cargar_sec()
    utilidad = flujo_con_respaldo(sec, ["NetIncomeLoss", "ProfitLoss"], "utilidad_neta_ttm")
    ebit = flujo_con_respaldo(sec, ["OperatingIncomeLoss"], "ebit_ttm")
    depre = flujo_con_respaldo(sec, ["DepreciationDepletionAndAmortization",
                                     "DepreciationAmortizationAndAccretionNet"], "dya_ttm")
    patrimonio = saldo(sec, "StockholdersEquity", "patrimonio")
    caja = saldo(sec, "CashAndCashEquivalentsAtCarryingValue", "caja")
    acciones = saldo(sec, "EntityCommonStockSharesOutstanding", "acciones")
    deuda = deuda_total(sec)

    base = pegar_a_diario(base, utilidad, ["utilidad_neta_ttm"])
    base = pegar_a_diario(base, ebit, ["ebit_ttm"])
    base = pegar_a_diario(base, depre, ["dya_ttm"])
    base = pegar_a_diario(base, patrimonio.rename(columns={"fin": "fecha_ultimo_reporte_sec"}),
                          ["patrimonio", "fecha_ultimo_reporte_sec"])
    base = pegar_a_diario(base, caja, ["caja"])
    base = pegar_a_diario(base, deuda, ["deuda"])
    base = pegar_a_diario(base, acciones, ["acciones"])

    # 5.3 Cálculo de los múltiplos (montos en millones de US$)
    m = 1e6
    base["cap_bursatil_musd"] = base["precio_accion_usd"] * base["acciones"] / m
    base["patrimonio_musd"] = base["patrimonio"] / m
    base["deuda_total_musd"] = base["deuda"] / m
    base["caja_musd"] = base["caja"] / m
    base["deuda_neta_musd"] = base["deuda_total_musd"] - base["caja_musd"]
    base["valor_empresa_musd"] = base["cap_bursatil_musd"] + base["deuda_neta_musd"]
    base["utilidad_neta_ttm_musd"] = base["utilidad_neta_ttm"] / m
    base["ebitda_ttm_musd"] = (base["ebit_ttm"] + base["dya_ttm"]) / m

    # Un múltiplo con denominador negativo o cero no tiene sentido económico -> faltante
    base["pe"] = np.where(base["utilidad_neta_ttm_musd"] > 0,
                          base["cap_bursatil_musd"] / base["utilidad_neta_ttm_musd"], np.nan)
    base["pb"] = np.where(base["patrimonio_musd"] > 0,
                          base["cap_bursatil_musd"] / base["patrimonio_musd"], np.nan)
    base["ev_ebitda"] = np.where(base["ebitda_ttm_musd"] > 0,
                                 base["valor_empresa_musd"] / base["ebitda_ttm_musd"], np.nan)

    # 5.4 Referencia del sector (Damodaran), llave = año de la edición
    base = pegar_a_diario(base, leer_damodaran(), ["ev_ebitda_sector_damodaran"])

    # 5.5 Valores atípicos: se MARCAN (1 = atípico), no se borran
    for col in ["pe", "pb", "ev_ebitda"]:
        base[f"atipico_{col}"] = marcar_atipicos(base[col])
        registrar(f"{col}: {base[f'atipico_{col}'].sum()} atípicos marcados; "
                  f"{base[col].isna().sum()} faltantes")

    base["ticker"] = TICKER
    base["acciones_mill"] = base["acciones"] / m
    columnas = ["fecha", "ticker", "precio_accion_usd", "acciones_mill", "cap_bursatil_musd",
                "patrimonio_musd", "deuda_total_musd", "caja_musd", "deuda_neta_musd",
                "valor_empresa_musd", "utilidad_neta_ttm_musd", "ebitda_ttm_musd",
                "pe", "pb", "ev_ebitda", "ev_ebitda_sector_damodaran",
                "precio_cobre_usd_lb", "precio_plata_usd_oz", "tipo_cambio_pen_usd",
                "fecha_ultimo_reporte_sec", "atipico_pe", "atipico_pb", "atipico_ev_ebitda"]
    base = base[columnas].sort_values("fecha").reset_index(drop=True)
    base["fecha"] = base["fecha"].dt.strftime("%Y-%m-%d")
    base["fecha_ultimo_reporte_sec"] = pd.to_datetime(
        base["fecha_ultimo_reporte_sec"]).dt.strftime("%Y-%m-%d")

    salida = PROCESADOS / f"datos_procesados_{CODIGO}.csv"
    base.to_csv(salida, index=False, encoding="utf-8", float_format="%.6f")

    # 5.6 Huella digital SHA-256 del archivo procesado
    huella = hashlib.sha256(salida.read_bytes()).hexdigest()
    (SALIDAS / "hash_sha256_datos_procesados.txt").write_text(
        f"{salida.name}  SHA-256: {huella}\n", encoding="utf-8")
    registrar(f"Guardado {salida.name}: {len(base)} filas x {base.shape[1]} columnas | SHA-256 {huella}")
    registrar("FIN 03_limpieza_datos")
