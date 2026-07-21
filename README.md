# Asignacion mensual de turnos (Coordinacion de trafico)

Aplicativo web para que el coordinador asigne los turnos de los operadores mes a mes,
respetando las reglas de negocio, las preferencias y las vacaciones.

## Archivos

| Archivo | Que hace |
|---|---|
| `app.py` | Interfaz web (Streamlit) con el flujo de 3 pasos. |
| `motor.py` | Logica de negocio pura (construccion de operadores y asignacion). |
| `exportar.py` | Genera el Excel con colores y el CSV. |
| `test_motor.py` | Prueba que valida las reglas duras. Opcional. |
| `requirements.txt` | Dependencias. |

La logica esta separada de la interfaz a proposito: si algun dia se cambia
Streamlit por otra cosa, `motor.py` se reutiliza tal cual.

## Como ejecutarlo en su computador

1. Instalar Python 3.10 o superior.
2. En una terminal, dentro de la carpeta del proyecto:

   ```
   pip install -r requirements.txt
   streamlit run app.py
   ```

3. Se abre solo en el navegador (normalmente en http://localhost:8501).

## Como publicarlo para que el coordinador solo abra un link (recomendado)

1. Suba estos archivos a un repositorio en GitHub.
2. Entre a https://share.streamlit.io , conecte el repo y elija `app.py`.
3. Streamlit Community Cloud da un link publico. El coordinador no instala nada.

## Uso (3 pasos)

1. **Matriz de preferencia.** Escriba los nombres en la celda de su turno (columna)
   y su par de dias de libranza (fila). Un nombre por linea.
2. **Vacaciones y flexibilidad.** Marque los dias de vacaciones de cada operador y
   ordene los dos rankings arrastrando (arriba = mas flexible).
3. **Calendario.** Se genera el mes con los tres turnos por dia y se descarga en
   Excel o CSV.

## Como leer el calendario

- **Nombre resaltado en amarillo:** hay que negociar con esa persona. Al pasar el
  mouse se ve el tipo de negociacion (turno o libranza, con la pareja nueva).
- **Turno en amarillo:** ese turno tiene al menos una negociacion.
- **Turno en rojo:** no se alcanzo el minimo de 3 operadores. Regla incumplida.

## Como decide el sistema (resumen)

Todos trabajan su turno fijo todos los dias, salvo su libranza o sus vacaciones.
El calculo se hace semana a semana. Cuando un turno de un dia queda por debajo de 3,
el sistema lo cubre asi, en orden:

1. **Cambio de turno (un dia).** Mueve gente de un turno con excedente a ese turno,
   solo por ese dia. No le cuesta descanso a nadie.

2. **Cambio de libranza (una semana).** Le cambia a alguien de ese turno su pareja
   de dias de libranza por OTRA de las tres parejas establecidas, solo por esa
   semana. La persona sigue librando dos dias consecutivos, pero otros: pasa a
   trabajar los dos dias de su par original y a librar los dos del par nuevo. Solo
   se hace si el par nuevo tiene holgura y no genera un nuevo rojo.

En cada paso empieza por el mas flexible segun el ranking correspondiente. Si aun
asi un turno no llega a 3, lo marca en rojo.

Nota: una misma negociacion de libranza aparece marcada en los dos dias que la
persona pasa a trabajar esa semana, a proposito, para que el coordinador vea el
efecto completo. En el resumen se cuenta una sola vez por persona y semana.
