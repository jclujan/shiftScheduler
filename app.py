# -*- coding: utf-8 -*-
"""
app.py
======
Aplicativo web para el coordinador de trafico: asignacion mensual de turnos.

Flujo de tres pasos:
  Paso 1: ubicar los nombres de los operadores en la matriz de preferencia 3x3.
  Paso 2: marcar vacaciones y ordenar los dos rankings de flexibilidad.
  Paso 3: ver el calendario del mes con la asignacion y descargarlo.

Se ejecuta con:  streamlit run app.py
"""

import calendar
from datetime import date

import streamlit as st
from streamlit_sortables import sort_items

from motor import (
    construir_operadores, construir_programacion, resumen_programacion,
    TURNOS, LIBRANZAS, NOMBRES_DIA, MINIMO,
)
from exportar import exportar_excel, exportar_csv


# --------------------------------------------------------------------------- #
# Configuracion general de la pagina
# --------------------------------------------------------------------------- #
st.set_page_config(page_title="Asignacion de turnos", layout="wide")

MESES_ES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

# El estado se guarda en st.session_state para no perder datos entre pasos.
if "paso" not in st.session_state:
    st.session_state.paso = 1


def reiniciar():
    """
    Vuelve al primer paso borrando TODO el estado, incluidos los estados
    internos de los widgets (rankings de arrastrar y selectores de vacaciones).
    Asi, al meter nombres nuevos, nada queda pegado de la sesion anterior.
    """
    st.session_state.clear()
    st.session_state.paso = 1


# --------------------------------------------------------------------------- #
# Barra lateral: mes y año a programar (siempre visible)
# --------------------------------------------------------------------------- #
st.sidebar.title("Asignacion de turnos")
st.sidebar.caption("Coordinacion de trafico")

hoy = date.today()
anio = st.sidebar.number_input("Año a programar", min_value=2024, max_value=2100,
                               value=st.session_state.get("anio", hoy.year), step=1)
mes_nombre = st.sidebar.selectbox(
    "Mes a programar", MESES_ES,
    index=st.session_state.get("mes", hoy.month) - 1,
)
mes = MESES_ES.index(mes_nombre) + 1
st.session_state.anio, st.session_state.mes = int(anio), mes

st.sidebar.divider()
st.sidebar.write(f"**Paso actual:** {st.session_state.paso} de 3")
if st.sidebar.button("Volver a empezar"):
    reiniciar()
    st.rerun()


# =========================================================================== #
# PASO 1: matriz de preferencia
# =========================================================================== #
def vista_paso_1():
    st.header("Paso 1. Matriz de preferencia")
    st.write(
        "Escriba los nombres de los operadores en la celda que corresponde a su "
        "**turno** (columna) y su **par de dias de libranza** (fila). "
        "Un nombre por linea. Cada operador va en una sola celda."
    )

    # Recuperar valores previos si el usuario vuelve atras.
    previa = st.session_state.get("matriz_pref", {})

    entradas = {}
    # Encabezado de columnas (turnos)
    cols = st.columns([1.2] + [2] * len(TURNOS))
    cols[0].markdown("&nbsp;")
    for i, turno in enumerate(TURNOS):
        cols[i + 1].markdown(f"### {turno}")

    # Una fila por par de libranza
    for libranza in LIBRANZAS:
        cols = st.columns([1.2] + [2] * len(TURNOS))
        cols[0].markdown(f"**Libra**\n\n**{libranza}**")
        for i, turno in enumerate(TURNOS):
            valor_previo = "\n".join(previa.get((libranza, turno), []))
            texto = cols[i + 1].text_area(
                label=f"{libranza} / {turno}",
                value=valor_previo,
                key=f"pref_{libranza}_{turno}",
                label_visibility="collapsed",
                height=120,
                placeholder="Un nombre por linea",
            )
            # Cada nombre en una linea; se limpian espacios y vacios.
            nombres = [n.strip() for n in texto.splitlines() if n.strip()]
            entradas[(libranza, turno)] = nombres

    st.divider()
    if st.button("Continuar al paso 2", type="primary"):
        operadores, errores = construir_operadores(entradas)
        if errores:
            for e in errores:
                st.error(e)
        else:
            st.session_state.matriz_pref = entradas
            st.session_state.operadores = operadores
            st.session_state.paso = 2
            st.rerun()


# =========================================================================== #
# PASO 2: vacaciones y rankings de flexibilidad
# =========================================================================== #
def vista_paso_2():
    operadores = st.session_state.operadores
    nombres = list(operadores.keys())
    anio, mes = st.session_state.anio, st.session_state.mes
    _, ultimo_dia = calendar.monthrange(anio, mes)

    # "Firma" que cambia si cambia el conjunto de nombres. Se usa en las claves
    # de los widgets para que, si el coordinador cambia los operadores, los
    # selectores y rankings se reconstruyan solos con los nombres nuevos.
    firma = str(abs(hash(tuple(sorted(nombres)))))

    st.header("Paso 2. Vacaciones y flexibilidad")
    st.caption(f"{len(nombres)} operadores | {mes_nombre} {anio}")

    # --------------------------- Vacaciones ---------------------------- #
    st.subheader("Vacaciones")
    st.write(
        "Elija los dias de vacaciones de cada operador haciendo clic en la lista. "
        "Puede dejar vacio a quien no tenga vacaciones."
    )

    dias_opciones = list(range(1, ultimo_dia + 1))
    vacaciones_sel = {}
    # Se muestran en dos columnas para que ocupen menos espacio vertical.
    columnas = st.columns(2)
    for i, op in enumerate(nombres):
        col = columnas[i % 2]
        seleccion = col.multiselect(
            op,
            options=dias_opciones,
            key=f"vac_{firma}_{op}",   # la clave incluye el nombre: no se pisa
            placeholder="Sin vacaciones",
        )
        vacaciones_sel[op] = set(seleccion)

    st.divider()

    # ------------------------ Rankings de flexibilidad ----------------- #
    st.subheader("Rankings de flexibilidad")
    st.write(
        "Arrastre los nombres para ordenarlos. **Arriba = mas flexible** "
        "(a esa persona se le pedira primero el cambio)."
    )
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Flexibilidad para cambios de TURNO**")
        rank_turno = sort_items(
            nombres,
            direction="vertical",
            key=f"sort_turno_{firma}",   # clave ligada a los nombres actuales
        )
    with col_b:
        st.markdown("**Flexibilidad para cambios de DIAS DE LIBRANZA**")
        rank_libranza = sort_items(
            nombres,
            direction="vertical",
            key=f"sort_libranza_{firma}",
        )

    st.divider()
    col1, col2 = st.columns([1, 1])
    if col1.button("Volver al paso 1"):
        st.session_state.paso = 1
        st.rerun()
    if col2.button("Generar programacion", type="primary"):
        # Solo se guardan los operadores que si tienen dias de vacaciones.
        vacaciones = {op: dias for op, dias in vacaciones_sel.items() if dias}

        st.session_state.programacion = construir_programacion(
            anio, mes, operadores, vacaciones,
            rank_turno, rank_libranza,
        )
        st.session_state.paso = 3
        st.rerun()


# =========================================================================== #
# PASO 3: calendario de salida
# =========================================================================== #
def _celda_turno_html(turno, datos):
    """Genera el HTML de un turno dentro de un dia del calendario."""
    if not datos["cumple"]:
        fondo = "#f8cbad"   # rojo suave: no se cumplio el minimo
    elif datos["negociados"]:
        fondo = "#fff2cc"   # amarillo suave: hay negociacion
    else:
        fondo = "#eef3f8"   # normal

    nombres_html = []
    for op in datos["operadores"]:
        if op in datos["negociados"]:
            tipo = datos["negociados"][op]
            # Nombre resaltado en amarillo, con el tipo de negociacion como tooltip.
            nombres_html.append(
                f"<span title='Negociar: {tipo}' "
                f"style='background:#ffe08a;border-radius:3px;padding:0 3px;'>{op}</span>"
            )
        else:
            nombres_html.append(op)

    aviso = ""
    if not datos["cumple"]:
        aviso = (f"<b style='color:#c00;'>Faltan {MINIMO - len(datos['operadores'])} "
                 f"(regla incumplida)</b><br>")

    return (
        f"<div style='background:{fondo};border-radius:4px;padding:4px;"
        f"margin-bottom:3px;font-size:11px;line-height:1.3;'>"
        f"<b>{turno}</b> ({len(datos['operadores'])})<br>{aviso}"
        f"{', '.join(nombres_html) if nombres_html else '<i>sin operadores</i>'}"
        f"</div>"
    )


def _calendario_html(programacion, anio, mes):
    """Construye el calendario completo del mes como una tabla HTML."""
    semanas = calendar.Calendar(firstweekday=0).monthdatescalendar(anio, mes)

    html = ["<table style='width:100%;border-collapse:collapse;table-layout:fixed;'>"]
    # Encabezado de dias de la semana
    html.append("<tr>")
    for nombre in NOMBRES_DIA:
        html.append(
            f"<th style='border:1px solid #ccc;padding:4px;background:#404040;"
            f"color:#fff;font-size:12px;'>{nombre}</th>"
        )
    html.append("</tr>")

    for semana in semanas:
        html.append("<tr>")
        for fecha in semana:
            # Dias que no pertenecen al mes se muestran en gris y vacios.
            if fecha.month != mes:
                html.append(
                    "<td style='border:1px solid #eee;background:#fafafa;"
                    "vertical-align:top;height:120px;'></td>"
                )
                continue
            celda = [f"<div style='font-weight:bold;font-size:12px;"
                     f"margin-bottom:3px;'>{fecha.day}</div>"]
            for turno in TURNOS:
                celda.append(_celda_turno_html(turno, programacion[fecha][turno]))
            html.append(
                "<td style='border:1px solid #ccc;padding:4px;vertical-align:top;"
                "height:120px;'>" + "".join(celda) + "</td>"
            )
        html.append("</tr>")
    html.append("</table>")
    return "".join(html)


def vista_paso_3():
    programacion = st.session_state.programacion
    anio, mes = st.session_state.anio, st.session_state.mes

    st.header(f"Paso 3. Calendario de turnos ({mes_nombre} {anio})")

    # Metricas resumidas
    res = resumen_programacion(programacion)
    c1, c2, c3 = st.columns(3)
    c1.metric("Operadores", len(st.session_state.operadores))
    c2.metric("Negociaciones a realizar", res["negociaciones"])
    c3.metric("Turnos sin cubrir (rojo)", res["incumplidos"])

    # Leyenda de colores
    st.markdown(
        "<div style='font-size:12px;'>"
        "<span style='background:#ffe08a;padding:0 4px;border-radius:3px;'>Nombre</span> "
        "operador con quien negociar (fuera de su turno o libranza) &nbsp;|&nbsp; "
        "<span style='background:#fff2cc;padding:0 4px;'>turno amarillo</span> "
        "tiene alguna negociacion &nbsp;|&nbsp; "
        "<span style='background:#f8cbad;padding:0 4px;'>turno rojo</span> "
        "no alcanzo el minimo de 3</div>",
        unsafe_allow_html=True,
    )
    st.write("")

    # Calendario
    st.markdown(_calendario_html(programacion, anio, mes), unsafe_allow_html=True)

    st.divider()

    # Descargas
    nombre_base = f"turnos_{anio}_{mes:02d}"
    col1, col2, col3 = st.columns(3)
    col1.download_button(
        "Descargar Excel (con colores)",
        data=exportar_excel(programacion, anio, mes),
        file_name=f"{nombre_base}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )
    col2.download_button(
        "Descargar CSV",
        data=exportar_csv(programacion),
        file_name=f"{nombre_base}.csv",
        mime="text/csv",
    )
    if col3.button("Volver al paso 2"):
        st.session_state.paso = 2
        st.rerun()


# =========================================================================== #
# Enrutador de pasos
# =========================================================================== #
if st.session_state.paso == 1:
    vista_paso_1()
elif st.session_state.paso == 2:
    vista_paso_2()
else:
    vista_paso_3()