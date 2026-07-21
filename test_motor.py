# -*- coding: utf-8 -*-
"""Prueba del motor contra todas las reglas de negocio."""
import random
from datetime import timedelta
from collections import defaultdict
from motor import (
    construir_operadores, construir_programacion, resumen_programacion,
    fechas_del_periodo, _lunes_de,
    TURNOS, LIBRANZAS, DIAS_LIBRES_POR_PAR, MINIMO,
)

random.seed(7)

# --- Escenario: 5 operadores por (turno, libranza) => 45 operadores ---
matriz = {}
idx = 1
for lib in LIBRANZAS:
    for tur in TURNOS:
        matriz[(lib, tur)] = [f"Op{idx + i:02d}" for i in range(5)]
        idx += 5

operadores, errores = construir_operadores(matriz)
assert not errores, errores
nombres = list(operadores.keys())
print(f"Operadores: {len(nombres)}")

rank_turno = nombres[:]; random.shuffle(rank_turno)
rank_libranza = nombres[:]; random.shuffle(rank_libranza)

anio, mes = 2026, 9
fechas = fechas_del_periodo(anio, mes)
conjunto = set(fechas)
print(f"Periodo: {fechas[0]} a {fechas[-1]} ({len(fechas)} dias)")

# Vacaciones como conjuntos de FECHAS (objetos date).
vacaciones = {op: set(random.sample(fechas, random.randint(0, 5))) for op in nombres}

prog = construir_programacion(anio, mes, operadores, vacaciones, rank_turno, rank_libranza)

parejas_validas = [frozenset(v) for v in DIAS_LIBRES_POR_PAR.values()]
errores_regla = []

# Regla: periodo empieza lunes y termina domingo
if fechas[0].weekday() != 0 or fechas[-1].weekday() != 6:
    errores_regla.append("El periodo no empieza en lunes o no termina en domingo")

# Reglas por dia
def turno_de(fecha, op):
    for t in TURNOS:
        if op in prog[fecha][t]["operadores"]:
            return t
    return None

for fecha, dia in prog.items():
    del_dia = []
    for t in TURNOS:
        for op in dia[t]["operadores"]:
            del_dia.append(op)
            # Regla 5: nadie asignado en vacaciones
            if fecha in vacaciones[op]:
                errores_regla.append(f"{op} asignado en vacaciones {fecha}")
    # Regla 3: nadie en dos turnos el mismo dia
    if len(del_dia) != len(set(del_dia)):
        errores_regla.append(f"Operador duplicado {fecha}")

# Regla nueva: nadie Noche un dia y Mañana/Tarde al dia siguiente
for fecha in fechas:
    sig = fecha + timedelta(days=1)
    if sig in conjunto:
        for op in nombres:
            if turno_de(fecha, op) == "Noche" and turno_de(sig, op) in ("Mañana", "Tarde"):
                errores_regla.append(f"{op}: noche {fecha} + dia {sig}")

# Regla 4: cada operador libra exactamente una pareja valida por semana
trabajo = defaultdict(set)
for fecha, dia in prog.items():
    for t in TURNOS:
        for op in dia[t]["operadores"]:
            trabajo[op].add(fecha)
semanas = defaultdict(list)
for fecha in fechas:
    semanas[_lunes_de(fecha)].append(fecha)
for op in nombres:
    for lunes, dias in semanas.items():
        candidatos = [d for d in dias if d not in vacaciones[op]]
        libra = [d for d in candidatos if d not in trabajo[op]]
        wds = frozenset(d.weekday() for d in libra)
        if not any(wds <= pv for pv in parejas_validas):
            errores_regla.append(f"{op} semana {lunes}: libra {sorted(wds)} (pareja invalida)")
        if 4 in wds:
            errores_regla.append(f"{op} libra viernes semana {lunes}")

print("Errores de regla:", errores_regla if errores_regla else "ninguno")
print("Resumen:", resumen_programacion(prog))

assert not errores_regla, "Se violaron reglas de negocio"
print("\nOK: sin violaciones de reglas duras.")
