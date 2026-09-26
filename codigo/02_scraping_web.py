# Nombres y apellidos: Alejandro Soto Antezana
# Código de matrícula: 2024200531K
# Tema del temario: N.º 42 — Múltiplos de valoración de las mineras listadas en la BVL: P/E, P/B y EV/EBITDA
# Fecha de extracción: 2026-09-26
"""
02_scraping_web.py  —  VÍA 2: DESCARGA PROGRAMÁTICA (numeral 2.4.3)

Fuente: base de datos de múltiplos por industria del profesor Aswath Damodaran
(NYU Stern School of Business), sección "Emerging Markets".

Qué hace este script (en orden):
  1. Revisa el archivo robots.txt del portal para confirmar que la descarga está permitida.
  2. Descarga, desde su URL oficial, los archivos Excel (.xls):
       - EV/EBITDA por industria, ediciones históricas de enero 2015 a enero 2025
         (se usan para tener la referencia del sector año por año);
       - EV/EBITDA, P/B y P/E de la edición vigente (enero 2026, datos al cierre de 2025).
  3. Guarda cada archivo ORIGINAL intacto en /datos_crudos/damodaran.
  4. Lee (parsea) cada archivo con código y extrae la fila de la industria
     "Metals & Mining", guardándola en formato largo en /datos_crudos.

Si un archivo no existe (error 404), se anota en el log y se continúa.
"""

import time
import datetime as dt
from pathlib import Path
from urllib import robotparser

import requests
import pandas as pd

# --------------------------------------------------------------------------
# 0. PARÁMETROS CONGELADOS
# --------------------------------------------------------------------------
CODIGO = "2024200531K"
ANIO_INICIO = 2015
ANIO_FIN = 2025
INDUSTRIA = "Metals & Mining"
USER_AGENT = "Alejandro Soto Antezana - UNCP Finanzas I (fines academicos) e_2024200531K@uncp.edu.pe"
PAUSA_SEGUNDOS = 1.0

URL_BASE = "https://pages.stern.nyu.edu/~adamodar/pc/"
# Ediciones históricas: el archivo "vebitdaemergAA.xls" es la edición de enero del año 20AA
ARCHIVOS = [
    {"edicion": anio, "multiplo": "ev_ebitda",
     "ruta": f"archives/vebitdaemerg{str(anio)[2:]}.xls"}
    for anio in range(ANIO_INICIO, ANIO_FIN + 1)
]
# Edición vigente (enero 2026)
ARCHIVOS += [
    {"edicion": 2026, "multiplo": "ev_ebitda", "ruta": "datasets/vebitdaemerg.xls"},
    {"edicion": 2026, "multiplo": "pbv", "ruta": "datasets/pbvemerg.xls"},
    {"edicion": 2026, "multiplo": "pe", "ruta": "datasets/peemerg.xls"},
]

# --------------------------------------------------------------------------
# 1. RUTAS RELATIVAS
# --------------------------------------------------------------------------
RAIZ = Path(__file__).resolve().parent.parent
CARPETA_XLS = RAIZ / "datos_crudos" / "damodaran"
CARPETA_XLS.mkdir(parents=True, exist_ok=True)
ARCHIVO_LOG = RAIZ / "log_ejecucion.txt"


def registrar(mensaje: str) -> None:
    linea = f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] 02_scraping_web | {mensaje}"
    print(linea)
    with ARCHIVO_LOG.open("a", encoding="utf-8") as f:
        f.write(linea + "\n")


def normalizar(texto) -> str:
    """Quita saltos de línea y espacios dobles para comparar textos."""
    return " ".join(str(texto).split())


def permitido_por_robots(url: str) -> bool:
    """Lee robots.txt y responde si la URL puede descargarse."""
    lector = robotparser.RobotFileParser()
    lector.set_url("https://pages.stern.nyu.edu/robots.txt")
    lector.read()
    return lector.can_fetch(USER_AGENT, url)


def descargar_archivo(url: str, destino: Path) -> bool:
    """Descarga un archivo binario. Devuelve True si se guardó."""
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=90)
    registrar(f"GET {url} -> HTTP {resp.status_code}")
    if resp.status_code != 200:
        return False
    destino.write_bytes(resp.content)
    return True


def es_titulo_industria(texto: str) -> bool:
    """
    Reconoce la celda de título de la columna de industrias.
    Normalmente dice 'Industry Name', pero en la edición 2018 la fuente la
    escribió con una errata ('Induistry Name'). Por eso se acepta cualquier
    texto que empiece con 'Ind' y termine con 'Name'.
    """
    t = texto.lower()
    return t.startswith("ind") and t.endswith("name")


def extraer_fila_industria(ruta_xls: Path) -> list:
    """
    Recorre todas las hojas del Excel, busca la fila de encabezados
    (la que contiene el título de industrias) y devuelve la fila de la industria
    buscada como lista de (hoja, grupo, columna, valor). No se modifica ningún valor.
    'grupo' es el rótulo que Damodaran pone encima de las columnas
    (por ejemplo 'Only positive EBITDA firms' o 'All firms'); vacío si no hay.
    """
    hojas = pd.read_excel(ruta_xls, sheet_name=None, header=None)
    for nombre_hoja, tabla in hojas.items():
        for i in range(min(len(tabla), 30)):
            fila = [normalizar(x) for x in tabla.iloc[i].tolist()]
            titulos = [j for j, c in enumerate(fila) if es_titulo_industria(c)]
            if not titulos:
                continue
            encabezados = fila
            col_ind = titulos[0]
            # Rótulos de grupo: fila de arriba, "arrastrados" hacia la derecha
            grupos, actual = [], ""
            arriba = [normalizar(x) for x in tabla.iloc[i - 1].tolist()] if i > 0 else []
            for j in range(len(encabezados)):
                valor = arriba[j] if j < len(arriba) else "nan"
                if valor not in ("nan", ""):
                    actual = valor
                grupos.append(actual)
            for _, registro in tabla.iloc[i + 1:].iterrows():
                if normalizar(registro.iloc[col_ind]).lower() == INDUSTRIA.lower():
                    return [
                        (nombre_hoja, grupos[j], encabezados[j], registro.iloc[j])
                        for j in range(len(encabezados))
                        if encabezados[j] not in ("nan", "")
                    ]
    return []


if __name__ == "__main__":
    registrar("INICIO 02_scraping_web")
    filas = []
    for archivo in ARCHIVOS:
        url = URL_BASE + archivo["ruta"]
        destino = CARPETA_XLS / f"{archivo['edicion']}_{Path(archivo['ruta']).name}"

        if not permitido_por_robots(url):
            registrar(f"robots.txt NO permite {url}; se omite")
            continue
        if not descargar_archivo(url, destino):
            registrar(f"Archivo no disponible (se registra y se continúa): {url}")
            time.sleep(PAUSA_SEGUNDOS)
            continue

        pares = extraer_fila_industria(destino)
        if not pares:
            registrar(f"No se encontró '{INDUSTRIA}' en {destino.name}")
        for hoja, grupo, columna, valor in pares:
            filas.append({
                "edicion": archivo["edicion"],
                "multiplo_archivo": archivo["multiplo"],
                "archivo": destino.name,
                "url": url,
                "hoja": hoja,
                "grupo": grupo,
                "columna": columna,
                "valor": valor,
            })
        registrar(f"{destino.name}: {len(pares)} columnas extraídas de '{INDUSTRIA}'")
        time.sleep(PAUSA_SEGUNDOS)

    salida = RAIZ / "datos_crudos" / f"datos_crudos_damodaran_{CODIGO}.csv"
    pd.DataFrame(filas).to_csv(salida, index=False, encoding="utf-8")
    registrar(f"Guardado {salida.name} ({len(filas)} filas)")
    registrar("FIN 02_scraping_web")
