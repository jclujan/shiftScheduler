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

El coordinador solo interviene cuando un turno de un dia queda por debajo del
minimo. Para cubrirlo hay dos tipos de negociacion:

  1. Cambio de TURNO (por un dia): mover a alguien de otro turno que si trabaja
     ese dia hacia el turno corto. Solo afecta ese dia.

  2. Cambio de LIBRANZA (por una semana): cambiarle a alguien su par de dias de
     libranza por OTRO de los pares establecidos, solo por esa semana. La persona
     sigue librando dos dias consecutivos, pero otros. Consecuencia: pasa a
     trabajar los dos dias de su par original (suma cobertura ahi) y a librar los
     dos dias del par nuevo (resta cobertura ahi). Todo dentro de la misma semana
     y sin cambiar de turno.

Para decidir a quien pedirle cada cambio se usan los rankings de flexibilidad
que ordena el coordinador (el mas flexible primero).

El calculo se hace semana a semana (lunes a domingo), porque el cambio de
libranza es un fenomeno semanal.
"""

import calendar
from datetime import date, timedelta

# --------------------------------------------------------------------------- #
# Constantes de dominio
# --------------------------------------------------------------------------- #

TURNOS = ["Mañana", "Tarde", "Noche"]

# Etiquetas de los tres pares de libranza permitidos.
LIBRANZAS = ["Lunes-Martes", "Miercoles-Jueves", "Sabado-Domingo"]

# Minimo de operadores que exige la regla de negocio por turno.
MINIMO = 3

# Traduccion de cada par de libranza a numeros de dia de la semana de Python
# (lunes=0, martes=1, ..., domingo=6). El viernes (4) nunca es dia de libranza.
DIAS_LIBRES_POR_PAR = {
    "Lunes-Martes": {0, 1},
    "Miercoles-Jueves": {2, 3},
    "Sabado-Domingo": {5, 6},
}

# Nombres de los dias de la semana para mostrar en el calendario.
NOMBRES_DIA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]


# --------------------------------------------------------------------------- #
# Construccion de la lista de operadores a partir de la matriz de preferencia
# --------------------------------------------------------------------------- #

def construir_operadores(matriz_preferencia):
    """
    Convierte la matriz 3x3 de preferencia en un diccionario de operadores.

    Parametros
    ----------
    matriz_preferencia : dict
        Claves = (etiqueta_libranza, etiqueta_turno), valores = lista de nombres.

    Devuelve
    --------
    operadores : dict
        nombre -> {"turno": str, "libranza": str, "dias_libres": set[int]}
    errores : list[str]
        Lista de problemas encontrados (nombres repetidos, celdas vacias, etc.).
    """
    operadores = {}
    errores = []
    vistos = {}  # nombre -> celda donde ya aparecio (para detectar duplicados)

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
# Utilidades
# --------------------------------------------------------------------------- #

def _ordenar_por_flexibilidad(candidatos, ranking):
    """
    Ordena candidatos poniendo primero al mas flexible (posicion 0 del ranking).
    Quien no este en el ranking se trata como el menos flexible.
    """
    def posicion(op):
        try:
            return ranking.index(op)
        except ValueError:
            return 10 ** 9
    return sorted(candidatos, key=posicion)


def _lunes_de(fecha):
    """Devuelve el lunes de la semana a la que pertenece la fecha."""
    return fecha - timedelta(days=fecha.weekday())


# --------------------------------------------------------------------------- #
# Resolucion de una semana completa
# --------------------------------------------------------------------------- #

def resolver_semana(dias, operadores, vacaciones, rank_turno, rank_libranza, salida):
    """
    Asigna todos los dias (en el mes) de una misma semana y escribe el resultado
    en el diccionario 'salida' (fecha -> {turno: {...}}).

    'dias' es la lista de fechas de esa semana que caen dentro del mes.
    """
    base_turno = {op: operadores[op]["turno"] for op in operadores}
    base_pareja = {op: operadores[op]["libranza"] for op in operadores}

    # Estado mutable de la semana:
    pareja = dict(base_pareja)   # par de libranza vigente esta semana (puede cambiar)
    turno_ov = {}                # (op, fecha) -> turno asignado ese dia (cambio de turno)
    neg_turno = set()            # {(op, fecha)} con negociacion de turno
    neg_libranza = set()         # {op} con negociacion de libranza esta semana

    # ---- funciones locales que leen el estado vigente ----
    def libra(op, fecha):
        return fecha.weekday() in DIAS_LIBRES_POR_PAR[pareja[op]]

    def en_vacaciones(op, fecha):
        return fecha.day in vacaciones.get(op, set())

    def trabaja(op, fecha):
        return not en_vacaciones(op, fecha) and not libra(op, fecha)

    def turno_de(op, fecha):
        return turno_ov.get((op, fecha), base_turno[op])

    def gente(fecha, turno):
        return [op for op in operadores
                if trabaja(op, fecha) and turno_de(op, fecha) == turno]

    def cuantos(fecha, turno):
        return len(gente(fecha, turno))

    # --------------------------------------------------------------------- #
    # Paso 1: cambio de TURNO (por dia). Mover excedentes de un turno a otro
    # el mismo dia. No le cuesta descanso a nadie. Empieza por el mas flexible.
    # --------------------------------------------------------------------- #
    for fecha in dias:
        for destino in TURNOS:
            while cuantos(fecha, destino) < MINIMO:
                # buscar el turno con mayor excedente ese dia
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
                    if (op, fecha) not in neg_turno and op not in neg_libranza
                ]
                if not movibles:
                    break
                elegido = movibles[0]
                turno_ov[(elegido, fecha)] = destino
                neg_turno.add((elegido, fecha))

    # --------------------------------------------------------------------- #
    # Paso 2: cambio de LIBRANZA (por semana). Si un turno sigue corto un dia,
    # se le cambia la pareja de libranza a alguien de ese turno para que pase a
    # trabajar ese dia (y su dia hermano), librando en cambio otro par que tenga
    # holgura. Solo se aplica si no genera un nuevo incumplimiento.
    # --------------------------------------------------------------------- #
    for turno in TURNOS:
        for fecha in dias:
            while cuantos(fecha, turno) < MINIMO:
                # Candidatos: operadores de este turno, que hoy libran (por eso
                # pueden pasar a cubrir el dia), sin cambios previos esta semana,
                # y que no esten de vacaciones hoy.
                candidatos = []
                for op in operadores:
                    if base_turno[op] != turno:
                        continue
                    if op in neg_libranza:
                        continue
                    if any((op, d) in neg_turno for d in dias):
                        continue
                    if pareja[op] != base_pareja[op]:
                        continue
                    if fecha.weekday() not in DIAS_LIBRES_POR_PAR[pareja[op]]:
                        continue  # hoy no libra, no aplica
                    if en_vacaciones(op, fecha):
                        continue  # de vacaciones hoy, no puede cubrir
                    candidatos.append(op)
                candidatos = _ordenar_por_flexibilidad(candidatos, rank_libranza)

                aplicado = False
                for op in candidatos:
                    # Buscar una pareja destino que permita trabajar 'fecha' y que
                    # sea segura (no deje ningun dia del turno bajo el minimo).
                    pareja_elegida = None
                    for nueva in LIBRANZAS:
                        if nueva == pareja[op]:
                            continue
                        if fecha.weekday() in DIAS_LIBRES_POR_PAR[nueva]:
                            continue  # con esta pareja seguiria librando hoy
                        # Simular el cambio y revisar los dias que pasaria a librar.
                        anterior = pareja[op]
                        pareja[op] = nueva
                        seguro = True
                        for d in dias:
                            if d.weekday() in DIAS_LIBRES_POR_PAR[nueva]:
                                if cuantos(d, turno) < MINIMO:
                                    seguro = False
                                    break
                        pareja[op] = anterior
                        if seguro:
                            pareja_elegida = nueva
                            break
                    if pareja_elegida:
                        pareja[op] = pareja_elegida
                        neg_libranza.add(op)
                        aplicado = True
                        break
                if not aplicado:
                    break  # no hay forma segura de cubrir este dia: quedara en rojo

    # --------------------------------------------------------------------- #
    # Armar la salida de la semana.
    # --------------------------------------------------------------------- #
    for fecha in dias:
        salida[fecha] = {}
        for turno in TURNOS:
            ops = sorted(gente(fecha, turno))
            negociados = {}
            for op in ops:
                tipos = []
                if (op, fecha) in neg_turno:
                    tipos.append("turno")
                # Un operador con cambio de libranza aparece hoy trabajando porque
                # hoy era uno de sus dias de descanso base (su par original).
                if op in neg_libranza and fecha.weekday() in DIAS_LIBRES_POR_PAR[base_pareja[op]]:
                    tipos.append(f"libranza (esta semana libra {pareja[op]})")
                if tipos:
                    negociados[op] = " y ".join(tipos)
            salida[fecha][turno] = {
                "operadores": ops,
                "negociados": negociados,
                "cumple": len(ops) >= MINIMO,
            }


# --------------------------------------------------------------------------- #
# Asignacion de un mes completo
# --------------------------------------------------------------------------- #

def construir_programacion(anio, mes, operadores, vacaciones, rank_turno, rank_libranza):
    """
    Recorre el mes semana a semana y devuelve la programacion completa.

    Devuelve
    --------
    programacion : dict
        date -> {turno: {"operadores", "negociados", "cumple"}}
    """
    _, ultimo_dia = calendar.monthrange(anio, mes)
    fechas = [date(anio, mes, d) for d in range(1, ultimo_dia + 1)]

    # Agrupar las fechas del mes por semana (ancladas al lunes).
    semanas = {}
    for f in fechas:
        semanas.setdefault(_lunes_de(f), []).append(f)

    programacion = {}
    for _, dias in sorted(semanas.items()):
        resolver_semana(dias, operadores, vacaciones, rank_turno, rank_libranza, programacion)
    return programacion


# --------------------------------------------------------------------------- #
# Resumen de metricas (util para la interfaz)
# --------------------------------------------------------------------------- #

def resumen_programacion(programacion):
    """
    Cuenta negociaciones y turnos incumplidos.
    Una negociacion de libranza se cuenta una sola vez por operador y semana
    (aunque aparezca marcada en sus dos dias). Una de turno se cuenta por dia.
    """
    negoc_turno = set()      # {(op, fecha)}
    negoc_libranza = set()   # {(op, lunes_de_la_semana)}
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
