# -*- coding: utf-8 -*-
"""Prueba rapida del motor contra las reglas de negocio."""
import random
from datetime import date
from motor import (
    construir_operadores, construir_programacion, resumen_programacion,
    TURNOS, LIBRANZAS, MINIMO,
)

random.seed(7)

# --- Escenario: 4 operadores por (turno, libranza) => 36 operadores ---
matriz = {}
idx = 1
for lib in LIBRANZAS:
    for tur in TURNOS:
        nombres = [f"Op{idx+i:02d}" for i in range(4)]
        matriz[(lib, tur)] = nombres
        idx += 4

operadores, errores = construir_operadores(matriz)
assert not errores, errores
print(f"Operadores construidos: {len(operadores)}")

nombres = list(operadores.keys())

# Rankings de flexibilidad aleatorios (mas flexible primero).
rank_turno = nombres[:]; random.shuffle(rank_turno)
rank_libranza = nombres[:]; random.shuffle(rank_libranza)

# Vacaciones: a cada operador le ponemos ~5 dias aleatorios de vacaciones.
vacaciones = {op: set(random.sample(range(1, 31), 5)) for op in nombres}

prog = construir_programacion(2026, 9, operadores, vacaciones, rank_turno, rank_libranza)

# --- Validaciones de reglas ---
errores_regla = []
for fecha, dia in prog.items():
    asignados_del_dia = []
    for turno in TURNOS:
        datos = dia[turno]
        ops = datos["operadores"]
        asignados_del_dia += ops
        # Regla: nadie asignado estando en vacaciones ese dia
        for op in ops:
            if fecha.day in vacaciones[op]:
                errores_regla.append(f"{op} asignado el {fecha} estando en vacaciones")
    # Regla: nadie en dos turnos el mismo dia
    if len(asignados_del_dia) != len(set(asignados_del_dia)):
        errores_regla.append(f"Operador duplicado en varios turnos el {fecha}")

print("Errores de regla:", errores_regla if errores_regla else "ninguno")

res = resumen_programacion(prog)
print("Resumen:", res)

# Muestra de un dia
f = date(2026, 9, 1)
print(f"\nEjemplo {f} ({f.strftime('%A')}):")
for t in TURNOS:
    d = prog[f][t]
    print(f"  {t}: {len(d['operadores'])} ops, cumple={d['cumple']}, "
          f"negociados={d['negociados']}")

assert not errores_regla, "Se violaron reglas de negocio"
print("\nOK: sin violaciones de reglas duras.")
