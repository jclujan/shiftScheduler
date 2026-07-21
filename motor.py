# -*- coding: utf-8 -*-
"""
motor.py
========
Logica de negocio pura para la asignacion mensual de turnos.
No depende de Streamlit, asi que se puede probar de forma aislada.

Modelo mental
-------------
Cada operador tiene un turno asignado (Mañana, Tarde o Noche) y un par de dias
de libranza fijo. Por defecto trabaja SIEMPRE su turno, todos los dias, salvo:
  - sus dos dias de libranza (segun su par), y
  - los dias que tenga vacaciones.

Definicion del "mes" (periodo)
------------------------------
El periodo NO va del dia 1 al 31. Se compone de semanas completas de lunes a
domingo. Una semana de borde pertenece al mes que contiene su JUEVES:
si de lunes a jueves la semana cae en el mes anterior, la semana es del mes
anterior. Por eso el periodo empieza siempre un lunes y termina un domingo,
e incluye unos pocos dias del mes vecino en los extremos.

Negociaciones
-------------
El coordinador solo interviene cuando un turno de un dia queda por debajo del
minimo. Hay dos tipos de negociacion:

  1. Cambio de TURNO (por un dia): mover a alguien de otro turno que si trabaja
     ese dia hacia el turno corto. Solo afecta ese dia.

  2. Cambio de LIBRANZA (por una semana): cambiarle a alguien su par de dias de
     libranza por OTRO de los pares establecidos, solo por esa semana. Sigue
     librando dos dias consecutivos, pero otros. Pasa a trabajar los dos dias de
     su par original y a librar los dos del par nuevo. No cambia de turno.

Regla de descanso entre noche y dia
-----------------------------------
Nadie puede trabajar el turno de Noche un dia y ademas Mañana o Tarde al dia
siguiente. Esto restringe las negociaciones de turno (la libranza no cambia de
turno, asi que nunca genera este conflicto).

Para decidir a quien pedirle cada cambio se usan los rankings de flexibilidad
que ordena el coordinador (el mas flexible primero).
"""

import calendar
from datetime import date, timedelta

# --------------------------------------------------------------------------- #
# Constantes de dominio
# --------------------------------------------------------------------------- #

TURNOS = ["Mañana", "Tarde", "Noche"]

LIBRANZAS = ["Lunes-Martes", "Miercoles-Jueves", "Sabado-Domingo"]

MINIMO = 3

# lunes=0, martes=1, ..., domingo=6. El viernes (4) nunca es dia de libranza.
DIAS_LIBRES_POR_PAR = {
    "Lunes-Martes": {0, 1},
    "Miercoles-Jueves": {2, 3},
    "Sabado-Domingo": {5, 6},
}

NOMBRES_DIA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
MESES_ABREV = ["ene", "feb", "mar", "abr", "may", "jun",
               "jul", "ago", "sep", "oct", "nov", "dic"]

JUEVES = 3  # indice de dia de la semana para el jueves


# --------------------------------------------------------------------------- #
# Construccion de la lista de operadores a partir de la matriz de preferencia
# --------------------------------------------------------------------------- #

def construir_operadores(matriz_preferencia):
    """
    Convierte la matriz 3x3 de preferencia en un diccionario de operadores.

    matriz_preferencia : dict con claves (etiqueta_libranza, etiqueta_turno) y
                         valores = lista de nombres.
    Devuelve (operadores, errores).
    """
    operadores = {}
    errores = []
    vistos = {}

    for (libranza, turno), nombres in matriz_preferencia.items():
        for nombre in nombres:
            nombre = nombre.strip()
            if not nombre:
                continue
            if nombre in vistos:
                errores.append(
                    f"El operador '{nombre}' aparece dos veces "
                    f"({vistos[nombre]} y {libranza} / {turno})."
                )
                continue
            vistos[nombre] = f"{libranza} / {turno}"
            operadores[nombre] = {
                "turno": turno,
                "libranza": libranza,
                "dias_libres": DIAS_LIBRES_POR_PAR[libranza],
            }

    if not operadores:
        errores.append("No se ingreso ningun operador en la matriz de preferencia.")

    return operadores, errores


# --------------------------------------------------------------------------- #
# Utilidades de fechas y periodo
# --------------------------------------------------------------------------- #

def _lunes_de(fecha):
    """Devuelve el lunes de la semana a la que pertenece la fecha."""
    return fecha - timedelta(days=fecha.weekday())


def fechas_del_periodo(anio, mes):
    """
    Devuelve la lista ordenada de fechas del periodo del mes indicado.
    El periodo son las semanas (lunes a domingo) cuyo JUEVES cae en el mes.
    Incluye dias del mes vecino en los bordes.
    """
    # Primer jueves del mes.
    primer_jueves = date(anio, mes, 1)
    while primer_jueves.weekday() != JUEVES:
        primer_jueves += timedelta(days=1)
    # Ultimo jueves del mes.
    ultimo_jueves = date(anio, mes, calendar.monthrange(anio, mes)[1])
    while ultimo_jueves.weekday() != JUEVES:
        ultimo_jueves -= timedelta(days=1)

    fechas = []
    jueves = primer_jueves
    while jueves <= ultimo_jueves:
        lunes = jueves - timedelta(days=JUEVES)
        for i in range(7):
            fechas.append(lunes + timedelta(days=i))
        jueves += timedelta(days=7)
    return fechas


def etiqueta_fecha(fecha):
    """Etiqueta corta en español para mostrar una fecha, ej. 'Lun 31 ago'."""
    return f"{NOMBRES_DIA[fecha.weekday()][:3]} {fecha.day:02d} {MESES_ABREV[fecha.month - 1]}"


def _ordenar_por_flexibilidad(candidatos, ranking):
    """Ordena candidatos poniendo primero al mas flexible (posicion 0 del ranking)."""
    def posicion(op):
        try:
            return ranking.index(op)
        except ValueError:
            return 10 ** 9
    return sorted(candidatos, key=posicion)


# --------------------------------------------------------------------------- #
# Asignacion de todo el periodo (mes completo)
# --------------------------------------------------------------------------- #

def construir_programacion(anio, mes, operadores, vacaciones, rank_turno, rank_libranza):
    """
    Calcula la programacion de todo el periodo del mes.

    Parametros
    ----------
    vacaciones : dict  op -> set de fechas (objetos date) con vacaciones.
    rank_turno, rank_libranza : listas de nombres, mas flexible primero.

    Devuelve
    --------
    programacion : dict  date -> {turno: {"operadores", "negociados", "cumple"}}
    """
    fechas = fechas_del_periodo(anio, mes)
    conjunto_fechas = set(fechas)

    base_turno = {op: operadores[op]["turno"] for op in operadores}
    base_pareja = {op: operadores[op]["libranza"] for op in operadores}

    # Estado mutable (a nivel de todo el periodo):
    pareja_semana = {}   # (op, lunes) -> par de libranza vigente esa semana
    turno_ov = {}        # (op, fecha) -> turno asignado ese dia (cambio de turno)
    neg_turno = set()    # {(op, fecha)}
    neg_libranza = set() # {(op, lunes)}

    # ---- funciones que leen el estado vigente ----
    def pareja(op, fecha):
        return pareja_semana.get((op, _lunes_de(fecha)), base_pareja[op])

    def libra(op, fecha):
        return fecha.weekday() in DIAS_LIBRES_POR_PAR[pareja(op, fecha)]

    def en_vacaciones(op, fecha):
        return fecha in vacaciones.get(op, set())

    def trabaja(op, fecha):
        return not en_vacaciones(op, fecha) and not libra(op, fecha)

    def turno_de(op, fecha):
        return turno_ov.get((op, fecha), base_turno[op])

    def gente(fecha, turno):
        return [op for op in operadores
                if trabaja(op, fecha) and turno_de(op, fecha) == turno]

    def cuantos(fecha, turno):
        return len(gente(fecha, turno))

    def viola_regla_noche(op, fecha, turno_destino):
        """
        True si asignar a 'op' al 'turno_destino' el dia 'fecha' rompe la regla:
        nadie trabaja Noche un dia y Mañana/Tarde al dia siguiente.
        """
        if turno_destino == "Noche":
            siguiente = fecha + timedelta(days=1)
            if (siguiente in conjunto_fechas and trabaja(op, siguiente)
                    and turno_de(op, siguiente) in ("Mañana", "Tarde")):
                return True
        if turno_destino in ("Mañana", "Tarde"):
            anterior = fecha - timedelta(days=1)
            if (anterior in conjunto_fechas and trabaja(op, anterior)
                    and turno_de(op, anterior) == "Noche"):
                return True
        return False

    # --------------------------------------------------------------------- #
    # Paso 1: cambio de TURNO (por dia). Mover excedentes de un turno a otro el
    # mismo dia, respetando la regla de noche. Empieza por el mas flexible.
    # --------------------------------------------------------------------- #
    for fecha in fechas:
        for destino in TURNOS:
            while cuantos(fecha, destino) < MINIMO:
                origen, mejor = None, 0
                for cand in TURNOS:
                    if cand == destino:
                        continue
                    exc = cuantos(fecha, cand) - MINIMO
                    if exc > 0 and exc > mejor:
                        origen, mejor = cand, exc
                if origen is None:
                    break
                movibles = [
                    op for op in _ordenar_por_flexibilidad(gente(fecha, origen), rank_turno)
                    if (op, fecha) not in neg_turno
                    and (op, _lunes_de(fecha)) not in neg_libranza
                    and not viola_regla_noche(op, fecha, destino)
                ]
                if not movibles:
                    break
                elegido = movibles[0]
                turno_ov[(elegido, fecha)] = destino
                neg_turno.add((elegido, fecha))

    # --------------------------------------------------------------------- #
    # Paso 2: cambio de LIBRANZA (por semana). Cubrir dias cortos cambiando la
    # pareja de libranza a alguien de ese turno, sin generar nuevos rojos.
    # Se agrupan las fechas del periodo por semana.
    # --------------------------------------------------------------------- #
    semanas = {}
    for f in fechas:
        semanas.setdefault(_lunes_de(f), []).append(f)

    for lunes, dias in sorted(semanas.items()):
        for turno in TURNOS:
            for fecha in dias:
                while cuantos(fecha, turno) < MINIMO:
                    candidatos = []
                    for op in operadores:
                        if base_turno[op] != turno:
                            continue
                        if (op, lunes) in neg_libranza:
                            continue
                        if any((op, d) in neg_turno for d in dias):
                            continue
                        if pareja(op, fecha) != base_pareja[op]:
                            continue
                        if fecha.weekday() not in DIAS_LIBRES_POR_PAR[pareja(op, fecha)]:
                            continue  # hoy no libra, no aplica
                        if en_vacaciones(op, fecha):
                            continue  # de vacaciones hoy, no puede cubrir
                        candidatos.append(op)
                    candidatos = _ordenar_por_flexibilidad(candidatos, rank_libranza)

                    aplicado = False
                    for op in candidatos:
                        pareja_elegida = None
                        for nueva in LIBRANZAS:
                            if nueva == pareja(op, fecha):
                                continue
                            if fecha.weekday() in DIAS_LIBRES_POR_PAR[nueva]:
                                continue  # con esta pareja seguiria librando hoy
                            # Simular y revisar los dias que pasaria a librar.
                            pareja_semana[(op, lunes)] = nueva
                            seguro = True
                            for d in dias:
                                if d.weekday() in DIAS_LIBRES_POR_PAR[nueva]:
                                    if cuantos(d, turno) < MINIMO:
                                        seguro = False
                                        break
                            del pareja_semana[(op, lunes)]
                            if seguro:
                                pareja_elegida = nueva
                                break
                        if pareja_elegida:
                            pareja_semana[(op, lunes)] = pareja_elegida
                            neg_libranza.add((op, lunes))
                            aplicado = True
                            break
                    if not aplicado:
                        break  # no hay forma segura de cubrir: quedara en rojo

    # --------------------------------------------------------------------- #
    # Armar la salida.
    # --------------------------------------------------------------------- #
    programacion = {}
    for fecha in fechas:
        lunes = _lunes_de(fecha)
        programacion[fecha] = {}
        for turno in TURNOS:
            ops = sorted(gente(fecha, turno))
            negociados = {}
            for op in ops:
                tipos = []
                if (op, fecha) in neg_turno:
                    tipos.append("turno")
                if ((op, lunes) in neg_libranza
                        and fecha.weekday() in DIAS_LIBRES_POR_PAR[base_pareja[op]]):
                    tipos.append(f"libranza (esta semana libra {pareja(op, fecha)})")
                if tipos:
                    negociados[op] = " y ".join(tipos)
            programacion[fecha][turno] = {
                "operadores": ops,
                "negociados": negociados,
                "cumple": len(ops) >= MINIMO,
            }
    return programacion


# --------------------------------------------------------------------------- #
# Resumen de metricas
# --------------------------------------------------------------------------- #

def resumen_programacion(programacion):
    """
    Cuenta negociaciones y turnos incumplidos.
    La libranza se cuenta una vez por operador y semana; el turno, por dia.
    """
    negoc_turno = set()
    negoc_libranza = set()
    incumplidos = 0

    for fecha, dia in programacion.items():
        lunes = _lunes_de(fecha)
        for datos in dia.values():
            if not datos["cumple"]:
                incumplidos += 1
            for op, tipo in datos["negociados"].items():
                if "turno" in tipo:
                    negoc_turno.add((op, fecha))
                if "libranza" in tipo:
                    negoc_libranza.add((op, lunes))

    return {
        "negociaciones": len(negoc_turno) + len(negoc_libranza),
        "negoc_turno": len(negoc_turno),
        "negoc_libranza": len(negoc_libranza),
        "incumplidos": incumplidos,
    }
