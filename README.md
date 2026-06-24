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

**Entorno de prueba:** Python 3.14 · Linux 6.17 · 20 núcleos · GIL activo.
Cada configuración se ejecutó **3 veces**; los valores son el promedio.

| Estaciones × Ciclos | Secuencial (Ts) | Hilos (Tthread) | Procesos (Tprocess) | Sthread = Ts/Tthread | Sprocess = Ts/Tprocess |
|---|---|---|---|---|---|
| 6 × 10 | 0.210 s | 0.494 s | 0.097 s | **x0.43** | **x2.16** |
| 6 × 20 | 0.739 s | 1.505 s | 0.215 s | **x0.49** | **x3.44** |
| 6 × 30 | 1.301 s | 2.671 s | 0.339 s | **x0.49** | **x3.84** |

> Para variar el número de estaciones se edita la lista `DEFINICION_ESTACIONES`
> en [monitoreo/config.py](monitoreo/config.py); el número de ciclos se pasa con
> `--ciclos`.

### Respuestas del análisis comparativo

- **¿Qué versión fue más rápida?** La versión basada en **procesos**, en todos los tamaños.
- **¿Los hilos mejoraron respecto a secuencial?** **No.** Fueron más lentos (speedup < 1). El trabajo es CPU-bound y el GIL impide que los hilos ejecuten bytecode en paralelo; además se suma la sobrecarga de cambio de contexto y sincronización.
- **¿Los procesos mejoraron respecto a secuencial?** **Sí**, con speedup de ~2x a ~4x, porque cada proceso tiene su propio intérprete y GIL, aprovechando varios núcleos.
- **¿Qué impacto tuvo el GIL?** Decisivo en la versión con hilos: serializa la ejecución del cálculo del índice ambiental, de modo que añadir hilos no aporta paralelismo real y sí sobrecarga.
- **¿Qué mecanismo de sincronización fue más importante?** El `Lock`, porque protege el buffer compartido de mediciones y evita condiciones de carrera; sin él, dos hilos podrían corromper la lista o el conteo de alertas.
- **¿Qué mecanismo de comunicación entre procesos se usó y por qué?** La `Queue`, porque los procesos no comparten memoria: es la forma segura y simple de enviar las mediciones (objetos picklables) desde las estaciones hacia el controlador.
- **¿Qué problemas de concurrencia aparecieron y cómo se resolvieron?** Condiciones de carrera en el buffer (resueltas con `Lock`); desincronización de ciclos (resuelta con `Barrier`); parada ordenada de hilos/procesos (resuelta con `Event` + `join()`).
- **¿Cuándo conviene usar hilos?** En tareas **I/O-bound** (espera de red, disco, BD), donde el GIL se libera durante la espera.
- **¿Cuándo conviene usar procesos?** En tareas **CPU-bound** (cálculo intensivo), donde se necesita paralelismo real en varios núcleos.
- **¿Qué versión fue más compleja de implementar?** La de **procesos**, por la necesidad de objetos picklables, comunicación explícita por `Queue` y mayor cuidado en el arranque/cierre de procesos.

---

## Reproducir las pruebas

```bash
# Los tres tamaños pedidos, cada uno promediando 3 corridas por modo
python3 main.py --estaciones 4  --ciclos 10 --repeticiones 3
python3 main.py --estaciones 8  --ciclos 20 --repeticiones 3
python3 main.py --estaciones 12 --ciclos 30 --repeticiones 3
```

---

## Entregables de la práctica

- [x] Código en GitHub (este repositorio).
- [x] README con instrucciones de instalación y ejecución.
- [x] Tabla comparativa de resultados (arriba).
- [ ] Capturas de pantalla de la GUI *(ejecutar `python3 main.py --gui` y capturar)*.
- [ ] Informe técnico en PDF *(puede basarse en la sección de análisis comparativo)*.
