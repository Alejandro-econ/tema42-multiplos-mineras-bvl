# Nombres y apellidos: Alejandro Soto Antezana
# Código de matrícula: 2024200531K
# Tema del temario: N.º 42 — Múltiplos de valoración de las mineras listadas en la BVL: P/E, P/B y EV/EBITDA
# Fecha de extracción: 2026-09-26
"""
01_extraccion_api.py  —  VÍA 1: CONSUMO DE API

Qué hace este script (en orden):
  1. BCRPData (API REST del Banco Central de Reserva del Perú): descarga las
     series DIARIAS del precio del cobre, de la plata y del tipo de cambio.
  2. Yahoo Finance (librería yfinance): descarga el precio DIARIO de la acción
     de Southern Copper Corporation (SCCO), emisor listado en la BVL.
  3. SEC EDGAR (API XBRL de la Securities and Exchange Commission de EE. UU.):
     descarga los estados financieros TRIMESTRALES que Southern Copper reporta
     (utilidad, EBIT, depreciación, patrimonio, deuda, caja y acciones).

Todo se guarda SIN EDITAR en /datos_crudos y cada descarga queda anotada en
log_ejecucion.txt (fecha y hora, filas descargadas y código HTTP).
"""

import os
import json
import time
import datetime as dt
from pathlib import Path

import requests
import pandas as pd
import yfinance as yf

# --------------------------------------------------------------------------
# 0. PARÁMETROS CONGELADOS (no usar fechas dinámicas como "hoy")
# --------------------------------------------------------------------------
FECHA_INICIO = "2015-01-01"
FECHA_CORTE = "2025-12-31"
CODIGO = "2024200531K"

TICKER = "SCCO"            # Southern Copper Corporation
CIK_SEC = "0001001838"     # Identificador de Southern Copper en la SEC

# Series diarias del BCRP (código -> palabra que debe aparecer en su nombre)
SERIES_BCRP = {
    "PD04701XD": "Cobre",            # Cobre (Londres, centavos de US$ por libra)
    "PD04702XD": "Plata",            # Plata (H. Harman, US$ por onza troy)
    "PD04638PD": "Tipo de cambio",   # TC interbancario venta (S/ por US$)
}

# Cuentas contables (etiquetas XBRL) que se piden a la SEC
ETIQUETAS_SEC = [
    ("us-gaap", "NetIncomeLoss"),                           # utilidad neta
    ("us-gaap", "ProfitLoss"),                              # utilidad neta (respaldo)
    ("us-gaap", "OperatingIncomeLoss"),                     # utilidad operativa (EBIT)
    ("us-gaap", "DepreciationDepletionAndAmortization"),    # depreciación y amortización
    ("us-gaap", "DepreciationAmortizationAndAccretionNet"), # depreciación (respaldo)
    ("us-gaap", "StockholdersEquity"),                      # patrimonio
    ("us-gaap", "LongTermDebt"),                            # deuda financiera total
    ("us-gaap", "LongTermDebtNoncurrent"),                  # deuda (respaldo)
    ("us-gaap", "LongTermDebtCurrent"),                     # deuda (respaldo)
    ("us-gaap", "CashAndCashEquivalentsAtCarryingValue"),   # caja
    ("dei", "EntityCommonStockSharesOutstanding"),          # acciones en circulación
]

PAUSA_SEGUNDOS = 1.0   # pausa mínima entre solicitudes (numeral 2.4.8)

# --------------------------------------------------------------------------
# 1. RUTAS RELATIVAS A LA CARPETA DEL PROYECTO (nunca C:\Users\...)
# --------------------------------------------------------------------------
RAIZ = Path(__file__).resolve().parent.parent
CRUDOS = RAIZ / "datos_crudos"
CRUDOS.mkdir(exist_ok=True)
ARCHIVO_LOG = RAIZ / "log_ejecucion.txt"

# La SEC exige un User-Agent con nombre y correo. Se lee del archivo .env
try:
    from dotenv import load_dotenv
    load_dotenv(RAIZ / ".env")
except ImportError:
    pass
USER_AGENT = os.getenv("SEC_USER_AGENT", "").strip()
if not USER_AGENT:
    raise SystemExit(
        "Falta la variable SEC_USER_AGENT. Copie .env.example como .env y "
        "escriba su nombre y correo (ver README.md)."
    )
CABECERAS = {"User-Agent": USER_AGENT}


def registrar(mensaje: str) -> None:
    """Escribe un mensaje en pantalla y en log_ejecucion.txt con fecha y hora."""
    linea = f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] 01_extraccion_api | {mensaje}"
    print(linea)
    with ARCHIVO_LOG.open("a", encoding="utf-8") as f:
        f.write(linea + "\n")


def descargar(url: str, intentos: int = 3) -> requests.Response:
    """Hace una solicitud GET con reintentos. Devuelve la respuesta si el código es 200."""
    for intento in range(1, intentos + 1):
        try:
            resp = requests.get(url, headers=CABECERAS, timeout=90)
            registrar(f"GET {url} -> HTTP {resp.status_code}")
            if resp.status_code == 200:
                return resp
        except requests.RequestException as error:
            registrar(f"Intento {intento} fallido en {url}: {error}")
        time.sleep(PAUSA_SEGUNDOS * 2 * intento)   # espera cada vez más larga
    raise RuntimeError(f"No se pudo descargar {url} tras {intentos} intentos.")


# --------------------------------------------------------------------------
# 2. BCRPData: una solicitud por serie (así no hay confusión en el orden)
# --------------------------------------------------------------------------
def extraer_bcrp() -> None:
    filas = []
    for codigo, palabra in SERIES_BCRP.items():
        url = (
            "https://estadisticas.bcrp.gob.pe/estadisticas/series/api/"
            f"{codigo}/json/{FECHA_INICIO}/{FECHA_CORTE}"
        )
        resp = descargar(url)
        datos = resp.json()
        nombre = datos["config"]["series"][0]["name"]
        if palabra.lower() not in nombre.lower():
            raise ValueError(f"La serie {codigo} no es la esperada: '{nombre}'")
        for periodo in datos["periods"]:
            filas.append({
                "codigo_serie": codigo,
                "nombre_serie": nombre,
                "fecha_bcrp": periodo["name"],      # formato del BCRP: 02.Ene.15
                "valor": periodo["values"][0],      # texto tal como llega ("n.d." = sin dato)
            })
        registrar(f"BCRP {codigo} ({nombre}): {len(datos['periods'])} filas")
        time.sleep(PAUSA_SEGUNDOS)

    salida = CRUDOS / f"datos_crudos_bcrp_{CODIGO}.csv"
    pd.DataFrame(filas).to_csv(salida, index=False, encoding="utf-8")
    registrar(f"Guardado {salida.name} ({len(filas)} filas)")


# --------------------------------------------------------------------------
# 3. Yahoo Finance: precio diario de SCCO
# --------------------------------------------------------------------------
def extraer_yahoo() -> None:
    # En yfinance la fecha 'end' no se incluye; por eso se suma un día.
    fin = (pd.Timestamp(FECHA_CORTE) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    historia = pd.DataFrame()
    for intento in range(1, 4):   # Yahoo a veces limita solicitudes: se reintenta
        try:
            historia = yf.Ticker(TICKER).history(
                start=FECHA_INICIO, end=fin, auto_adjust=False, actions=True
            )
        except Exception as error:
            registrar(f"Yahoo intento {intento} fallido: {error}")
        if not historia.empty:
            break
        time.sleep(10 * intento)
    if historia.empty:
        raise RuntimeError("Yahoo Finance no devolvió datos para " + TICKER)
    historia.index.name = "Date"
    salida = CRUDOS / f"datos_crudos_yahoo_{CODIGO}.csv"
    historia.to_csv(salida, encoding="utf-8")
    registrar(f"Yahoo Finance {TICKER}: {len(historia)} filas (HTTP n/d: la librería no lo expone) -> {salida.name}")
    time.sleep(PAUSA_SEGUNDOS)


# --------------------------------------------------------------------------
# 4. SEC EDGAR: estados financieros en formato XBRL
# --------------------------------------------------------------------------
def extraer_sec() -> None:
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{CIK_SEC}.json"
    resp = descargar(url)

    # 4.1 Se guarda el JSON completo, tal cual lo entrega la SEC (evidencia primaria)
    salida_json = CRUDOS / f"datos_crudos_sec_companyfacts_{CODIGO}.json"
    salida_json.write_bytes(resp.content)

    # 4.2 Se pasa a tabla solo las cuentas que usará el estudio (sin modificar valores)
    datos = json.loads(resp.content)
    filas = []
    for taxonomia, etiqueta in ETIQUETAS_SEC:
        concepto = datos["facts"].get(taxonomia, {}).get(etiqueta)
        if concepto is None:
            registrar(f"SEC: etiqueta no disponible {taxonomia}:{etiqueta}")
            continue
        for unidad, registros in concepto["units"].items():
            for r in registros:
                filas.append({
                    "taxonomia": taxonomia,
                    "etiqueta": etiqueta,
                    "unidad": unidad,
                    "inicio": r.get("start"),          # vacío en cuentas de saldo
                    "fin": r.get("end"),
                    "valor": r.get("val"),
                    "anio_fiscal": r.get("fy"),
                    "periodo_fiscal": r.get("fp"),
                    "formulario": r.get("form"),
                    "fecha_presentacion": r.get("filed"),
                    "numero_acceso": r.get("accn"),
                })
    salida_csv = CRUDOS / f"datos_crudos_sec_{CODIGO}.csv"
    pd.DataFrame(filas).to_csv(salida_csv, index=False, encoding="utf-8")
    registrar(f"SEC {datos.get('entityName')}: {len(filas)} registros -> {salida_csv.name}")


if __name__ == "__main__":
    registrar(f"INICIO | FECHA_INICIO={FECHA_INICIO} FECHA_CORTE={FECHA_CORTE}")
    extraer_bcrp()
    extraer_yahoo()
    extraer_sec()
    registrar("FIN 01_extraccion_api")
