# Sistema de Monitoreo Ambiental Urbano — Cuenca

Simulación de un sistema urbano de monitoreo ambiental para la ciudad de Cuenca,
desarrollado en Python con **diseño orientado a objetos** y tres modelos de
ejecución concurrente: **secuencial**, **basado en hilos** (`threading`) y
**basado en procesos** (`multiprocessing`).

El sistema simula varias estaciones ambientales que generan mediciones
periódicas (temperatura, humedad, ruido, CO₂, PM2.5, PM10). Un controlador
central recolecta las mediciones, calcula estadísticas, genera alertas cuando se
superan umbrales y registra métricas de rendimiento. Todo se visualiza en una
interfaz gráfica con **Tkinter**.

---

## Estructura del proyecto

```
.
├── main.py                     # Punto de entrada por consola (compara los 3 modos)
├── monitoreo/
│   ├── dominio.py              # Modelos: Medicion, AlertaAmbiental, Variable, Estadisticas, ...
│   ├── estacion.py             # EstacionAmbiental (unidad concurrente que genera mediciones)
│   ├── analizador.py           # AnalizadorDatos (estadísticas + cálculo CPU-bound)
│   ├── controlador.py          # ControladorMonitoreo (los 3 modos de ejecución)
│   └── config.py               # Definición de estaciones de Cuenca y parámetros
└── UserInterface/
    ├── app.py                  # GUI Tkinter
    └── models.py               # Re-exporta los modelos de dominio para la GUI
```

### Clases principales (requisito de POO)

| Clase | Responsabilidad |
|---|---|
| `EstacionAmbiental` | Representa una estación; genera mediciones simuladas de varias variables. |
| `Medicion` | Lectura individual: estación, zona, variable, valor e instante. |
| `ControladorMonitoreo` | Coordina estaciones, recibe mediciones, administra ciclos, calcula estadísticas, genera alertas y mide rendimiento. |
| `AnalizadorDatos` | Calcula promedio/máx/mín por variable, conteos, zona de riesgo, tiempos, y ejecuta el cálculo CPU-bound. |
| `AlertaAmbiental` | Alerta emitida cuando una variable supera su umbral. |

---

## Requisitos e instalación

- **Python 3.13+** (probado en 3.14).
- **Tkinter** (incluido en la mayoría de instalaciones de Python; en Linux puede
  requerir el paquete del sistema `python3-tk`).

No hay dependencias externas: el proyecto usa solo la biblioteca estándar.

```bash
# Clonar el repositorio
git clone <URL-DE-TU-REPO>
cd Sistema-de-monitoreo-ambiental-urbano-con-paralelismo-basado-en-procesos-e-hilos

# (Linux) si Tkinter no está disponible:
sudo apt install python3-tk
```

---

## Ejecución

### Interfaz gráfica (GUI)

```bash
python3 main.py --gui
# o de forma equivalente:
python3 -m UserInterface
```

En la ventana se elige el **modo** (Secuencial / Hilos / Procesos), el número de
**estaciones** (4–12) y de **ciclos** (10–30) con los selectores de la barra
superior, y se pulsa **Iniciar**. Así se pueden probar los tamaños 4×10, 8×20
y 12×30 sin tocar el código. La GUI muestra el listado de estaciones, su estado
(activa, esperando, procesando, finalizada), la última medición, las alertas
activas, las estadísticas generales, el tiempo de ejecución, el modo activo y la
información del entorno (versión de Python, sistema operativo, núcleos y estado
del GIL).

### Por consola (comparación de rendimiento)

```bash
python3 main.py                           # compara los 3 modos e imprime el speedup
python3 main.py --modo procesos           # ejecuta un solo modo
python3 main.py --ciclos 20               # cambia el número de ciclos (mín. 10)
python3 main.py --estaciones 8 --ciclos 20    # cambia el tamaño de la simulación
python3 main.py --estaciones 12 --ciclos 30 --repeticiones 3   # promedia 3 corridas
python3 main.py --ciclos 30 --carga 800   # ajusta la carga de CPU del análisis
```

Con `--repeticiones N` cada modo se ejecuta `N` veces y se promedian los tiempos
(recomendado `3`); al final se imprimen explícitamente `Sthread = Ts/Tthread` y
`Sprocess = Ts/Tprocess`.

---

## Mecanismos de concurrencia utilizados

La práctica exige **al menos 2** mecanismos por versión; este proyecto usa **3**
en la versión de hilos y **4** en la de procesos.

### Versión basada en hilos (`threading`) — `ControladorMonitoreo.ejecutar_hilos`

| Mecanismo | Uso real en el sistema |
|---|---|
| `threading.Lock` | Protege el **buffer compartido** de mediciones y la lista de alertas para evitar condiciones de carrera al escribir desde varios hilos. |
| `threading.Barrier` | Sincroniza el **fin de cada ciclo**: el controlador espera a que todas las estaciones terminen el ciclo antes de calcular estadísticas. |
| `threading.Event` | Señal de **parada anticipada** desde la GUI (botón Detener). |

Cada estación corre en su propio `threading.Thread` y todas comparten la misma
estructura de datos (el buffer del controlador), protegida por el `Lock`.

### Versión basada en procesos (`multiprocessing`) — `ControladorMonitoreo.ejecutar_procesos`

| Mecanismo | Uso real en el sistema |
|---|---|
| `multiprocessing.Queue` | **Comunicación entre procesos**: cada estación-proceso envía sus mediciones al controlador. |
| `multiprocessing.Barrier` | Sincroniza el **inicio de cada ciclo** entre todos los procesos-estación. |
| `multiprocessing.Event` | Señal de **parada** propagada a todos los procesos. |
| `multiprocessing.Semaphore` | **Limita** cuántos procesos ejecutan el análisis CPU-bound a la vez (no más que núcleos disponibles), evitando saturar la CPU. |

Las mediciones son objetos *inmutables y picklables*, por lo que viajan sin
problemas por la `Queue`.

> Nota sobre la GUI: Tkinter no es *thread-safe*, así que la interfaz vive en el
> **hilo principal** y la simulación corre en un **hilo trabajador** que solo
> publica `SnapshotMonitoreo` en una `queue.Queue`. La GUI drena esa cola con
> `after(...)` y actualiza los widgets únicamente desde el hilo principal,
> evitando actualizaciones inseguras.

---

## Carga de análisis (para que la comparación tenga sentido)

`AnalizadorDatos.indice_ambiental` calcula un **índice ambiental compuesto**
mediante una **media móvil ponderada** con un kernel trigonométrico, repetida
muchas veces. Es trabajo **CPU-bound en Python puro**, por lo que mantiene tomado
el GIL: con hilos se serializa y con procesos escala en varios núcleos. Esto es
lo que hace pedagógicamente comparable hilos vs. procesos.

---

## Resultados y análisis comparativo

**Entorno de prueba:** Python 3.14.4 · Linux 6.17 · 20 núcleos.
Se probaron **9 tamaños de simulación** (4, 8 y 12 estaciones × 10, 20 y 30
ciclos) y, en cada tamaño, **cada modo se ejecutó 3 veces** con
`--repeticiones 3`; los tiempos mostrados son el **promedio de esas 3 corridas**.
Se midieron los **dos escenarios** que permite Python 3.14 para evidenciar el
impacto del GIL:

- **Escenario A — GIL activo** (intérprete estándar: `python3 main.py ...`).
- **Escenario B — GIL desactivado** (build *free-threaded*: `python -X gil=0 main.py ...`).

#### Escenario A — GIL ACTIVO (promedio de 3 corridas por modo)

| Estaciones × Ciclos | Secuencial (Ts) | Hilos (Tthread) | Procesos (Tprocess) | Sthread = Ts/Tthread | Sprocess = Ts/Tprocess |
|---|---|---|---|---|---|
| 4 × 10  | 0.139 s | 0.215 s | 0.071 s | **x0.65** | **x1.98** |
| 4 × 20  | 0.511 s | 0.901 s | 0.180 s | **x0.57** | **x2.84** |
| 4 × 30  | 0.839 s | 1.450 s | 0.280 s | **x0.58** | **x2.99** |
| 8 × 10  | 0.273 s | 0.716 s | 0.119 s | **x0.38** | **x2.30** |
| 8 × 20  | 0.967 s | 2.248 s | 0.291 s | **x0.43** | **x3.32** |
| 8 × 30  | 1.658 s | 3.733 s | 0.441 s | **x0.44** | **x3.76** |
| 12 × 10 | 0.417 s | 1.369 s | 0.134 s | **x0.30** | **x3.12** |
| 12 × 20 | 1.557 s | 4.258 s | 0.334 s | **x0.37** | **x4.66** |
| 12 × 30 | 2.650 s | 5.014 s | 0.510 s | **x0.53** | **x5.19** |

Con el GIL activo, los **hilos son siempre más lentos que secuencial**
(speedup < 1 en los 9 casos) y los **procesos** son la mejor opción (hasta x5.19).

#### Escenario B — GIL DESACTIVADO / free-threaded (promedio de 3 corridas por modo)

| Estaciones × Ciclos | Secuencial (Ts) | Hilos (Tthread) | Procesos (Tprocess) | Sthread = Ts/Tthread | Sprocess = Ts/Tprocess |
|---|---|---|---|---|---|
| 4 × 10  | 0.151 s | 0.057 s | 0.072 s | **x2.66** | **x2.10** |
| 4 × 20  | 0.582 s | 0.170 s | 0.219 s | **x3.43** | **x2.66** |
| 4 × 30  | 0.962 s | 0.284 s | 0.336 s | **x3.39** | **x2.86** |
| 8 × 10  | 0.310 s | 0.090 s | 0.118 s | **x3.44** | **x2.63** |
| 8 × 20  | 1.090 s | 0.270 s | 0.320 s | **x4.04** | **x3.41** |
| 8 × 30  | 1.911 s | 0.412 s | 0.564 s | **x4.63** | **x3.39** |
| 12 × 10 | 0.483 s | 0.093 s | 0.119 s | **x5.22** | **x4.05** |
| 12 × 20 | 1.639 s | 0.281 s | 0.367 s | **x5.83** | **x4.46** |
| 12 × 30 | 2.981 s | 0.490 s | 0.588 s | **x6.09** | **x5.07** |

Al desactivar el GIL, los **hilos pasan a ser la versión más rápida** en los 9
casos (incluso por encima de procesos, al no pagar el coste de serializar objetos
ni de crear procesos), con speedups de **x2.66 hasta x6.09**.

#### Mediciones procesadas por segundo (throughput, promedio de 3 corridas)

| Estaciones × Ciclos | Escenario | Secuencial | Hilos | Procesos |
|---|---|---|---|---|
| 4 × 10  | GIL activo       | 1218.9 | 792.3  | 2407.9 |
| 4 × 10  | GIL desactivado  | 1125.8 | 2993.5 | 2360.7 |
| 4 × 20  | GIL activo       | 664.7  | 377.4  | 1887.7 |
| 4 × 20  | GIL desactivado  | 583.7  | 2004.4 | 1554.2 |
| 4 × 30  | GIL activo       | 607.6  | 351.6  | 1818.7 |
| 4 × 30  | GIL desactivado  | 530.1  | 1796.4 | 1517.2 |
| 8 × 10  | GIL activo       | 1245.0 | 474.6  | 2861.1 |
| 8 × 10  | GIL desactivado  | 1098.4 | 3783.8 | 2890.3 |
| 8 × 20  | GIL activo       | 703.2  | 302.5  | 2334.3 |
| 8 × 20  | GIL desactivado  | 623.6  | 2520.1 | 2124.2 |
| 8 × 30  | GIL activo       | 615.3  | 273.2  | 2311.8 |
| 8 × 30  | GIL desactivado  | 533.8  | 2474.3 | 1808.8 |
| 12 × 10 | GIL activo       | 1246.0 | 380.0  | 3891.2 |
| 12 × 10 | GIL desactivado  | 1075.9 | 5612.5 | 4353.9 |
| 12 × 20 | GIL activo       | 667.9  | 244.3  | 3113.0 |
| 12 × 20 | GIL desactivado  | 634.5  | 3699.9 | 2831.8 |
| 12 × 30 | GIL activo       | 588.7  | 311.1  | 3056.5 |
| 12 × 30 | GIL desactivado  | 523.3  | 3186.9 | 2655.1 |

> Para variar el número de estaciones se usa `--estaciones`; los ciclos con
> `--ciclos`. La cantidad de **alertas generadas** es idéntica entre los tres
> modos para un mismo tamaño (la concurrencia no cambia el resultado, solo el
> tiempo), lo que confirma que la sincronización es correcta.

### Respuestas del análisis comparativo

- **¿Qué versión fue más rápida?** Depende del GIL: con **GIL activo**, los **procesos**; con **GIL desactivado**, los **hilos** (que además superan a procesos).
- **¿Los hilos mejoraron respecto a secuencial?** Con **GIL activo: no** (speedup < 1, hasta x0.43), porque el GIL serializa el cálculo CPU-bound. Con **GIL desactivado: sí**, de forma notable (hasta x6.09).
- **¿Los procesos mejoraron respecto a secuencial?** **Sí en ambos escenarios** (de ~2x a ~5x), porque cada proceso tiene su propio intérprete y aprovecha varios núcleos, exista o no el GIL.
- **¿Qué impacto tuvo el GIL?** Es el factor decisivo de la versión con hilos, demostrado empíricamente: el **mismo código y la misma máquina** pasan de **x0.43–0.65 (GIL activo)** a **x2.66–6.09 (GIL desactivado)**. Con GIL, los hilos no logran paralelismo real en tareas CPU-bound; sin GIL, sí.
- **¿Qué mecanismo de sincronización fue más importante?** El `Lock`, porque protege el buffer compartido de mediciones y evita condiciones de carrera; sin él, dos hilos podrían corromper la lista o el conteo de alertas. (Su importancia crece justo en el escenario sin GIL, donde los hilos sí corren en paralelo de verdad.)
- **¿Qué mecanismo de comunicación entre procesos se usó y por qué?** La `Queue`, porque los procesos no comparten memoria: es la forma segura y simple de enviar las mediciones (objetos picklables) desde las estaciones hacia el controlador.
- **¿Qué problemas de concurrencia aparecieron y cómo se resolvieron?** Condiciones de carrera en el buffer (resueltas con `Lock`); desincronización de ciclos (resuelta con `Barrier`); parada ordenada de hilos/procesos (resuelta con `Event` + `join()`); sobrecarga de creación de procesos y de serialización, visible al comparar el throughput de procesos vs. hilos sin GIL.
- **¿Cuándo conviene usar hilos?** En tareas **I/O-bound** (espera de red, disco, BD), donde el GIL se libera; y, con Python free-threaded, también en tareas **CPU-bound** que comparten mucha memoria.
- **¿Cuándo conviene usar procesos?** En tareas **CPU-bound** sobre el intérprete estándar (con GIL), donde es la única forma de lograr paralelismo real en varios núcleos.
- **¿Qué versión fue más compleja de implementar?** La de **procesos**, por la necesidad de objetos picklables, comunicación explícita por `Queue` y mayor cuidado en el arranque/cierre de procesos.

---

## Reproducir las pruebas

```bash
# Escenario A — GIL activo (intérprete estándar)
python3 main.py --estaciones 4  --ciclos 10 --repeticiones 3
python3 main.py --estaciones 8  --ciclos 20 --repeticiones 3
python3 main.py --estaciones 12 --ciclos 30 --repeticiones 3

# Escenario B — GIL desactivado (build free-threaded de Python 3.14)
python -X gil=0 main.py --estaciones 4  --ciclos 10 --repeticiones 3
python -X gil=0 main.py --estaciones 8  --ciclos 20 --repeticiones 3
python -X gil=0 main.py --estaciones 12 --ciclos 30 --repeticiones 3
```

La GUI confirma en el panel "Entorno de ejecución" si el GIL está activo o
desactivado, por lo que ambos escenarios pueden capturarse para el informe.

---

## Entregables de la práctica

- [x] Código en GitHub (este repositorio).
- [x] README con instrucciones de instalación y ejecución.
- [x] Tabla comparativa de resultados (arriba).
- [ ] Capturas de pantalla de la GUI *(ejecutar `python3 main.py --gui` y capturar)*.
- [ ] Informe técnico en PDF *(puede basarse en la sección de análisis comparativo)*.
