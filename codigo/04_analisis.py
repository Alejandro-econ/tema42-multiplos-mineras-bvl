# Nombres y apellidos: Alejandro Soto Antezana
# Código de matrícula: 2024200531K
# Tema del temario: N.º 42 — Múltiplos de valoración de las mineras listadas en la BVL: P/E, P/B y EV/EBITDA
# Fecha de extracción: 2026-09-26
"""
04_analisis.py  —  TABLAS, FIGURAS Y ESTIMACIONES DEL ARTÍCULO

Lee SOLO los archivos de /datos_procesados y guarda todo en /salidas.

Modelo principal (4 variables: 1 endógena y 3 exógenas), en logaritmos:
    ln(EV/EBITDA)_t = b0 + b1 ln(Cobre)_t + b2 ln(Plata)_t + b3 ln(TipoCambio)_t + u_t
Se estima por Mínimos Cuadrados Ordinarios con errores estándar de Newey-West
(robustos a autocorrelación y heterocedasticidad), más dos pruebas de robustez:
  (B) sin los días marcados como atípicos, y
  (C) en primeras diferencias (variaciones diarias), por si las series en niveles
      no son estacionarias (se verifica con la prueba ADF).
"""

import warnings
import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller, coint

CODIGO = "2024200531K"
RAIZ = Path(__file__).resolve().parent.parent
PROCESADOS = RAIZ / "datos_procesados"
SALIDAS = RAIZ / "salidas"
SALIDAS.mkdir(exist_ok=True)
ARCHIVO_LOG = RAIZ / "log_ejecucion.txt"

ENDOGENA = "ev_ebitda"
EXOGENAS = ["precio_cobre_usd_lb", "precio_plata_usd_oz", "tipo_cambio_pen_usd"]
ETIQUETAS = {
    "pe": "P/E", "pb": "P/B", "ev_ebitda": "EV/EBITDA",
    "ev_ebitda_sector_damodaran": "EV/EBITDA sector (Damodaran)",
    "precio_cobre_usd_lb": "Cobre (US$/lb)", "precio_plata_usd_oz": "Plata (US$/oz)",
    "tipo_cambio_pen_usd": "Tipo de cambio (S/ por US$)",
    "cap_bursatil_musd": "Capitalización (millones US$)",
    "deuda_neta_musd": "Deuda neta (millones US$)",
}


def registrar(mensaje: str) -> None:
    linea = f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] 04_analisis | {mensaje}"
    print(linea)
    with ARCHIVO_LOG.open("a", encoding="utf-8") as f:
        f.write(linea + "\n")


def estimar(datos: pd.DataFrame, y: str, xs: list, nombre: str) -> pd.DataFrame:
    """MCO con errores Newey-West. Devuelve tabla de coeficientes y guarda el resumen."""
    d = datos[[y] + xs].dropna()
    rezagos = int(4 * (len(d) / 100) ** (2 / 9))       # regla de Newey-West
    modelo = sm.OLS(d[y], sm.add_constant(d[xs])).fit(
        cov_type="HAC", cov_kwds={"maxlags": rezagos})
    (SALIDAS / f"modelo_{nombre}.txt").write_text(modelo.summary().as_text(), encoding="utf-8")
    tabla = pd.DataFrame({"modelo": nombre, "variable": modelo.params.index,
                          "coeficiente": modelo.params.values,
                          "error_estandar_HAC": modelo.bse.values,
                          "p_valor": modelo.pvalues.values})
    tabla["n_obs"] = int(modelo.nobs)
    tabla["r2"] = modelo.rsquared
    tabla["rezagos_newey_west"] = rezagos
    registrar(f"Modelo {nombre}: n={int(modelo.nobs)}, R2={modelo.rsquared:.3f}")
    return tabla


if __name__ == "__main__":
    registrar("INICIO 04_analisis")
    df = pd.read_csv(PROCESADOS / f"datos_procesados_{CODIGO}.csv", parse_dates=["fecha"])
    sector = pd.read_csv(PROCESADOS / f"benchmark_actual_damodaran_{CODIGO}.csv")
    df["anio"] = df["fecha"].dt.year

    # ---------- Tabla 0: observaciones por variable (regla de mínimo 1 000) ----------
    variables = ["pe", "pb", "ev_ebitda", "cap_bursatil_musd", "deuda_neta_musd",
                 "precio_cobre_usd_lb", "precio_plata_usd_oz", "tipo_cambio_pen_usd"]
    t0 = df[variables].notna().sum().rename("observaciones").to_frame()
    t0["cumple_minimo_1000"] = np.where(t0["observaciones"] >= 1000, "Sí", "No")
    t0.index = [ETIQUETAS.get(v, v) for v in t0.index]
    t0.to_csv(SALIDAS / "tabla0_observaciones.csv", encoding="utf-8-sig")

    # ---------- Tabla 1: estadísticos descriptivos ----------
    t1 = df[variables].describe().T
    t1.index = [ETIQUETAS.get(v, v) for v in t1.index]
    t1.round(3).to_csv(SALIDAS / "tabla1_descriptivos.csv", encoding="utf-8-sig")

    # ---------- Tabla 2: múltiplos promedio por año ----------
    t2 = df.groupby("anio")[["pe", "pb", "ev_ebitda", "ev_ebitda_sector_damodaran",
                             "precio_cobre_usd_lb"]].mean()
    t2.columns = [ETIQUETAS[c] for c in t2.columns]
    t2.round(2).to_csv(SALIDAS / "tabla2_multiplos_por_anio.csv", encoding="utf-8-sig")

    # ---------- Tabla 3: SCCO al cierre vs. sector (Damodaran, enero 2026) ----------
    cierre = df.dropna(subset=["pe", "pb", "ev_ebitda"]).iloc[-1]
    t3 = pd.DataFrame({
        "Múltiplo": ["P/E", "P/B", "EV/EBITDA"],
        f"Southern Copper ({cierre['fecha']:%d/%m/%Y})": [cierre["pe"], cierre["pb"], cierre["ev_ebitda"]],
        "Metals & Mining, mercados emergentes (Damodaran)": [
            sector.loc[0, "pe_sector"], sector.loc[0, "pb_sector"], sector.loc[0, "ev_ebitda_sector"]],
    })
    t3["Prima (+) o descuento (-) de SCCO, %"] = (
        t3.iloc[:, 1] / t3.iloc[:, 2] - 1) * 100
    t3.round(2).to_csv(SALIDAS / "tabla3_scco_vs_sector.csv", index=False, encoding="utf-8-sig")

    # ---------- Variables en logaritmos ----------
    for v in [ENDOGENA] + EXOGENAS:
        df[f"ln_{v}"] = np.log(df[v])
        df[f"d_ln_{v}"] = df[f"ln_{v}"].diff()
    y, xs = f"ln_{ENDOGENA}", [f"ln_{v}" for v in EXOGENAS]

    # ---------- Tabla 4: correlaciones ----------
    df[[y] + xs].corr().round(3).to_csv(SALIDAS / "tabla4_correlaciones.csv", encoding="utf-8-sig")

    # ---------- Tabla 5: prueba de raíz unitaria (ADF) ----------
    filas = []
    for v in [y] + xs:
        for forma, serie in [("niveles", df[v]), ("primeras diferencias", df[v].diff())]:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                resultado = adfuller(serie.dropna(), autolag="AIC")
            est, p = resultado[0], resultado[1]
            filas.append({"variable": v, "forma": forma, "estadistico_ADF": est, "p_valor": p,
                          "conclusion_5%": "Estacionaria" if p < 0.05 else "No estacionaria"})
    pd.DataFrame(filas).round(4).to_csv(SALIDAS / "tabla5_prueba_adf.csv", index=False,
                                        encoding="utf-8-sig")

    # ---------- Tabla 7: prueba de cointegración de Engle-Granger ----------
    # Si las series no son estacionarias en niveles (Tabla 5), el Modelo A solo es
    # válido si existe una relación de largo plazo estable entre ellas
    # (cointegración). Si no la hay, el Modelo A podría ser una regresión espuria.
    d_coint = df[[y] + xs].dropna()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        est_c, p_c, criticos = coint(d_coint[y], d_coint[xs], trend="c", autolag="aic")
    pd.DataFrame([{
        "prueba": "Engle-Granger (ln EV/EBITDA sobre ln cobre, ln plata, ln tipo de cambio)",
        "estadistico": est_c, "p_valor": p_c,
        "valor_critico_1%": criticos[0], "valor_critico_5%": criticos[1],
        "valor_critico_10%": criticos[2],
        "conclusion_5%": "Hay cointegración (relación de largo plazo)" if p_c < 0.05
                         else "No hay cointegración (Modelo A podría ser espurio)",
    }]).round(4).to_csv(SALIDAS / "tabla7_cointegracion.csv", index=False, encoding="utf-8-sig")
    registrar(f"Cointegración Engle-Granger: estadístico={est_c:.3f}, p-valor={p_c:.4f}")

    # ---------- Tabla 6: modelos econométricos ----------
    sin_atipicos = df[df["atipico_ev_ebitda"] == 0]
    t6 = pd.concat([
        estimar(df, y, xs, "A_niveles_log"),
        estimar(sin_atipicos, y, xs, "B_niveles_log_sin_atipicos"),
        estimar(df, f"d_{y}", [f"d_{x}" for x in xs], "C_primeras_diferencias"),
    ])
    t6.round(4).to_csv(SALIDAS / "tabla6_modelos.csv", index=False, encoding="utf-8-sig")

    # ---------- Figura 1: evolución de los tres múltiplos ----------
    fig, ejes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)
    for eje, col in zip(ejes, ["pe", "pb", "ev_ebitda"]):
        eje.plot(df["fecha"], df[col], linewidth=0.8, label="Southern Copper")
        if col == "ev_ebitda":
            eje.step(df["fecha"], df["ev_ebitda_sector_damodaran"], where="post",
                     linewidth=1.2, linestyle="--", label="Sector Metals & Mining (Damodaran)")
            eje.legend(loc="upper left", fontsize=8)
        eje.set_ylabel(ETIQUETAS[col])
        eje.grid(alpha=0.3)
    ejes[0].set_title("Figura 1. Múltiplos de valoración diarios de Southern Copper, 2015-2025")
    fig.tight_layout()
    fig.savefig(SALIDAS / "figura1_multiplos.png", dpi=200)
    plt.close(fig)

    # ---------- Figura 2: EV/EBITDA frente al precio del cobre ----------
    fig, eje = plt.subplots(figsize=(8, 6))
    eje.scatter(df["precio_cobre_usd_lb"], df["ev_ebitda"], s=4, alpha=0.4)
    eje.set_xlabel(ETIQUETAS["precio_cobre_usd_lb"])
    eje.set_ylabel(ETIQUETAS["ev_ebitda"])
    eje.set_title("Figura 2. EV/EBITDA de Southern Copper y precio del cobre")
    eje.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(SALIDAS / "figura2_ev_ebitda_vs_cobre.png", dpi=200)
    plt.close(fig)

    # ---------- Figura 3: capitalización y deuda neta ----------
    fig, eje = plt.subplots(figsize=(10, 5))
    eje.plot(df["fecha"], df["cap_bursatil_musd"], linewidth=0.8, label=ETIQUETAS["cap_bursatil_musd"])
    eje.plot(df["fecha"], df["deuda_neta_musd"], linewidth=1.2, label=ETIQUETAS["deuda_neta_musd"])
    eje.set_title("Figura 3. Capitalización bursátil y deuda neta de Southern Copper")
    eje.legend()
    eje.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(SALIDAS / "figura3_capitalizacion_deuda.png", dpi=200)
    plt.close(fig)

    registrar("Tablas 0-7 y figuras 1-3 guardadas en /salidas")
    registrar("FIN 04_analisis")
