# -*- coding: utf-8 -*-
"""
configuracion.py
================
Guardar y recuperar la CONFIGURACION (los datos de entrada) en un CSV, para no
tener que recapturar todo si a mitad de mes cambia una vacacion o una prioridad.

El CSV tiene una fila por operador y estas columnas:
  Anio, Mes, Operador, Turno, Libranza, RankTurno, RankLibranza, Vacaciones

  - RankTurno / RankLibranza: posicion en el ranking (1 = mas flexible).
  - Vacaciones: fechas en formato AAAA-MM-DD separadas por ';' (vacio si no tiene).

El coordinador puede abrir este CSV en Excel, editar las vacaciones o los rankings
y volver a subirlo en el paso 1.
"""

import csv
import io
from datetime import date
from collections import defaultdict

from motor import TURNOS, LIBRANZAS

ENCABEZADOS = ["Anio", "Mes", "Operador", "Turno", "Libranza",
               "RankTurno", "RankLibranza", "Vacaciones"]


def exportar_config_csv(anio, mes, operadores, vacaciones, rank_turno, rank_libranza):
    """Devuelve los bytes de un CSV con toda la configuracion (los inputs)."""
    buffer = io.StringIO()
    escritor = csv.writer(buffer)
    escritor.writerow(ENCABEZADOS)

    # Posicion de cada operador en cada ranking (1 = mas flexible).
    pos_turno = {op: i + 1 for i, op in enumerate(rank_turno)}
    pos_libranza = {op: i + 1 for i, op in enumerate(rank_libranza)}

    for op, info in operadores.items():
        dias = sorted(vacaciones.get(op, set()))
        vac_txt = ";".join(d.isoformat() for d in dias)
        escritor.writerow([
            anio, mes, op, info["turno"], info["libranza"],
            pos_turno.get(op, ""), pos_libranza.get(op, ""), vac_txt,
        ])

    return buffer.getvalue().encode("utf-8-sig")


def importar_config_csv(texto):
    """
    Lee el texto de un CSV de configuracion y reconstruye los inputs.

    Devuelve un dict con:
      anio, mes, matriz_preferencia, vacaciones, rank_turno, rank_libranza,
      nombres, errores
    """
    errores = []
    matriz = defaultdict(list)
    vacaciones = {}
    pos_turno = {}
    pos_libranza = {}
    anio = mes = None

    try:
        filas = list(csv.DictReader(io.StringIO(texto)))
    except Exception as e:
        return {"errores": [f"No se pudo leer el CSV: {e}"]}

    if not filas:
        return {"errores": ["El archivo esta vacio o no tiene el formato esperado."]}

    # Validar que existan las columnas minimas.
    faltantes = [c for c in ["Operador", "Turno", "Libranza"] if c not in filas[0]]
    if faltantes:
        return {"errores": [f"Al CSV le faltan columnas: {', '.join(faltantes)}."]}

    for numero, fila in enumerate(filas, start=2):  # fila 1 es el encabezado
        op = (fila.get("Operador") or "").strip()
        if not op:
            continue

        turno = (fila.get("Turno") or "").strip()
        libranza = (fila.get("Libranza") or "").strip()
        if turno not in TURNOS:
            errores.append(f"Fila {numero}: turno invalido '{turno}'.")
            continue
        if libranza not in LIBRANZAS:
            errores.append(f"Fila {numero}: libranza invalida '{libranza}'.")
            continue
        matriz[(libranza, turno)].append(op)

        # Anio y mes (se toman de las filas; deberian ser iguales en todas).
        try:
            anio = int(fila.get("Anio"))
            mes = int(fila.get("Mes"))
        except (TypeError, ValueError):
            errores.append(f"Fila {numero}: año o mes invalido.")

        # Posiciones en los rankings.
        try:
            pos_turno[op] = int(fila.get("RankTurno"))
        except (TypeError, ValueError):
            pos_turno[op] = 10 ** 9
        try:
            pos_libranza[op] = int(fila.get("RankLibranza"))
        except (TypeError, ValueError):
            pos_libranza[op] = 10 ** 9

        # Vacaciones (acepta ';' o ',' como separador).
        texto_vac = (fila.get("Vacaciones") or "").strip()
        fechas = set()
        if texto_vac:
            for token in texto_vac.replace(",", ";").split(";"):
                token = token.strip()
                if not token:
                    continue
                try:
                    fechas.add(date.fromisoformat(token))
                except ValueError:
                    errores.append(f"Fila {numero}: fecha invalida '{token}'.")
        if fechas:
            vacaciones[op] = fechas

    nombres = [op for pares in matriz.values() for op in pares]
    rank_turno = sorted(nombres, key=lambda o: pos_turno.get(o, 10 ** 9))
    rank_libranza = sorted(nombres, key=lambda o: pos_libranza.get(o, 10 ** 9))

    return {
        "anio": anio,
        "mes": mes,
        "matriz_preferencia": dict(matriz),
        "vacaciones": vacaciones,
        "rank_turno": rank_turno,
        "rank_libranza": rank_libranza,
        "nombres": nombres,
        "errores": errores,
    }
