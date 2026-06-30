# Sistema de Monitoreo Ambiental Urbano — Versión MPI (Cuenca)

Versión **paralela con paso de mensajes (MPI / mpi4py)** del sistema de monitoreo
ambiental, pensada para ejecutarse en un **clúster** de computadoras. Distribuye
las estaciones ambientales entre varios procesos MPI, cada uno con su **memoria
local**, que se comunican mediante paso de mensajes para consolidar los
resultados en un proceso coordinador.

Incluye una **versión secuencial de referencia** y una **versión paralela MPI**
bajo el modelo **SPMD** (el mismo programa lo ejecutan todos los procesos).

---

## Diseño de la solución (POO)

El sistema reutiliza las clases de la práctica de hilos/procesos y añade un
coordinador MPI. Clases:

| Clase | Responsabilidad |
|---|---|
| `Variable` | Variable ambiental con su unidad y **umbral** de alerta. |
| `Medicion` | Lectura individual. Incluye estación, zona, variable, valor, **ciclo** y **proceso MPI** que la generó. |
| `EstacionAmbiental` | Genera las mediciones simuladas y ejecuta el cálculo CPU-bound. |
| `AnalizadorDatos` | Calcula el resumen local de un proceso y **consolida** los resúmenes de todos. |
| `AlertaAmbiental` | Alerta cuando una variable supera su umbral. |
| `CoordinadorMPI` | Reparte estaciones, coordina la comunicación MPI y mide el rendimiento. |

### Estrategia de paralelización

- **Modelo SPMD:** todos los procesos ejecutan `mpi_app.py`. El **rank 0** actúa
  de **coordinador**; los demás son **trabajadores**.
- **División de datos:** las estaciones se reparten entre los procesos con un
  esquema *round-robin* (la estación `i` va al proceso `i % size`). Así cada
  proceso trabaja **solo con sus estaciones** (memoria local), nunca todos hacen
  el mismo trabajo.
- **Consolidación:** cada proceso calcula un **resumen local** (sumas, mín/máx,
  alertas por zona) y el coordinador los une en un **resultado global**.

---

## Comunicación MPI utilizada

La rúbrica exige al menos una comunicación **punto a punto** y una **colectiva**.
Este proyecto usa ambas:

| Tipo | Operación | Dónde y por qué |
|---|---|---|
| **Punto a punto** | `comm.send` / `comm.recv` | El coordinador (rank 0) **asigna a cada trabajador** su lista de estaciones, enviándosela individualmente. Es una comunicación dirigida de un proceso a otro. |
| **Colectiva** | `comm.gather` | Recoge en el rank 0 el **resumen local de todos** los procesos en una sola operación. |
| **Colectiva** | `comm.reduce` (SUM y MAX) | Suma el **total de mediciones** procesadas y toma el **tiempo del proceso más lento** (Tp). |

> **Por qué estas operaciones:** el reparto de trabajo es dirigido (cada
> trabajador recibe algo distinto), por eso encaja `send/recv` punto a punto. La
> consolidación necesita juntar datos de **todos** los procesos a la vez, que es
> exactamente lo que hacen `gather` y `reduce` (colectivas), más eficientes y
> claras que hacerlo con muchos `send/recv`.

---

## Requisitos e instalación

- **Python 3.10+** y una implementación de **MPI** (Open MPI o MPICH).
- **mpi4py**.

```bash
# MPI (Debian/Ubuntu)
sudo apt install openmpi-bin libopenmpi-dev

# mpi4py
pip3 install --user mpi4py
```

---

## Ejecución

### En una sola computadora (consola)

```bash
# Secuencial + paralelo (calcula el speedup automáticamente)
mpiexec -n 1 python3 mpi_app.py --estaciones 8 --ciclos 20
mpiexec -n 2 python3 mpi_app.py --estaciones 8 --ciclos 20
mpiexec -n 4 python3 mpi_app.py --estaciones 8 --ciclos 20

# Solo la parte paralela (sin baseline secuencial)
mpiexec -n 4 python3 mpi_app.py --estaciones 8 --ciclos 20 --solo-paralelo
```

### Con interfaz gráfica (GUI + MPI)

El proceso 0 abre la ventana Tkinter y coordina; los demás procesos son
trabajadores que calculan y le envían resultados por MPI:

```bash
mpiexec -n 4 python3 gui_mpi.py --gui --estaciones 8 --ciclos 20
```

La GUI muestra cada estación con el **proceso MPI** que la atiende, su última
medición, las estadísticas globales, las alertas y el entorno (Python, SO, nº de
procesos MPI, librería MPI). El botón **Iniciar** lanza la simulación distribuida
y la ventana se actualiza ciclo a ciclo. Para verificar el protocolo sin pantalla:

```bash
mpiexec -n 4 python3 gui_mpi.py --selftest --estaciones 8 --ciclos 20
```

Cada ejecución imprime: el reparto de estaciones por proceso, las estadísticas
globales (idénticas sin importar el nº de procesos, lo que valida la
consolidación), y el bloque de rendimiento con **Ts, Tp, aceleramiento S y
eficiencia E**.

### En un clúster (varios nodos)

```bash
mpiexec -n 4 -hostfile hosts.txt python3 mpi_app.py --estaciones 8 --ciclos 20
```

Ver [hosts.txt](hosts.txt) para el formato del archivo de nodos. Requisitos del
clúster: **SSH sin contraseña** entre nodos, **misma ruta** del proyecto en
todos, y **mpi4py instalado** en cada nodo.

---

## Cómo montar el clúster (tu máquina = host + otra máquina)

Supongamos dos computadoras en la misma red (Wi-Fi o cable):

| Nodo | Rol | IP de ejemplo |
|---|---|---|
| `maestro` (tu máquina) | host / coordinador | 192.168.1.10 |
| `nodo2` (otra máquina) | trabajador | 192.168.1.11 |

### 1. Mismo usuario y red

Ambas máquinas deben verse en la red. Comprueba la IP con `ip a` (Linux) y que se
hacen ping: `ping 192.168.1.11`.

### 2. Instalar lo mismo en las dos máquinas

```bash
sudo apt update
sudo apt install openmpi-bin libopenmpi-dev openssh-server
pip3 install --user mpi4py
```

> Importante: la **misma versión de Python y de Open MPI** en ambas, y la carpeta
> `Practica-MPI/` en la **misma ruta** en las dos (p. ej. `/home/justin/Practica-MPI`).
> Lo más cómodo es compartirla por NFS o copiarla con `scp -r`.

### 3. SSH sin contraseña (del maestro hacia el nodo2)

MPI arranca los procesos remotos por SSH, así que el maestro debe entrar al nodo2
sin pedir contraseña:

```bash
# En el MAESTRO: generar la llave (si no existe) y copiarla al nodo2
ssh-keygen -t rsa            # Enter en todo
ssh-copy-id justin@192.168.1.11

# Probar: debe entrar sin pedir contraseña
ssh justin@192.168.1.11 hostname
```

### 4. Archivo de hosts

Edita [hosts.txt](hosts.txt) con las IP reales y los *slots* (procesos por nodo):

```
192.168.1.10 slots=2
192.168.1.11 slots=2
```

### 5. Ejecutar en el clúster (desde el maestro)

```bash
# 4 procesos repartidos entre las dos máquinas
mpiexec -n 4 -hostfile hosts.txt python3 mpi_app.py --estaciones 8 --ciclos 20
```

Para confirmar que de verdad corre en las dos máquinas, añade un test rápido:

```bash
mpiexec -n 4 -hostfile hosts.txt hostname
# debe imprimir el nombre de las DOS computadoras
```

### Problemas frecuentes (documéntalos en el informe)

- **Pide contraseña SSH** → no copiaste la llave con `ssh-copy-id`, repite el paso 3.
- **`mpiexec: command not found` en el nodo2** → falta instalar `openmpi-bin` allí.
- **`ModuleNotFoundError: mpi4py`** → falta `pip3 install --user mpi4py` en ese nodo.
- **No encuentra `mpi_app.py`** → la carpeta no está en la misma ruta en ambos nodos.
- **Firewall bloquea** → abre los puertos o desactiva el firewall en la red local.
- **Versiones distintas de Open MPI** → instala la misma versión en las dos máquinas.

### Script de pruebas

```bash
bash benchmark.sh 8 20      # corre 1, 2 y 4 procesos automáticamente
```

---

## Resultados (1 nodo, 20 núcleos, Open MPI 4.1.6)

Métricas: `S = Ts / Tp` (aceleramiento) y `E = S / p` (eficiencia).

### 8 estaciones × 20 ciclos (680 mediciones)

| Procesos (p) | Tp (paralelo) | S = Ts/Tp | Eficiencia |
|---|---|---|---|
| 1 | 0.969 s | x1.01 | 101 % |
| 2 | 0.490 s | x2.01 | 100 % |
| 4 | 0.275 s | x3.66 | 91 % |

(Ts ≈ 0.98 s)

### 12 estaciones × 30 ciclos (1560 mediciones)

| Procesos (p) | Tp (paralelo) | S = Ts/Tp | Eficiencia |
|---|---|---|---|
| 1 | 2.564 s | x1.01 | 100 % |
| 2 | 1.299 s | x2.00 | 99 % |
| 4 | 0.726 s | x3.67 | 91 % |

(Ts ≈ 2.6 s)

**Análisis:** el aceleramiento es **casi lineal** (x2 con 2 procesos, ~x3.7 con
4). La eficiencia baja un poco con 4 procesos por el coste de comunicación
(reparto + gather) y porque el trabajo total es fijo (más procesos = menos
trabajo por proceso, más peso relativo de la comunicación). Las estadísticas
globales son idénticas en todos los casos, lo que confirma que la **distribución
del trabajo y la consolidación son correctas**.

---

## Métricas de rendimiento (fórmulas)

- **Ts** = tiempo secuencial (1 proceso, todas las estaciones).
- **Tp** = tiempo paralelo (el del proceso más lento, vía `reduce` con MAX).
- **Aceleramiento:** `S = Ts / Tp`.
- **Eficiencia:** `E = S / p`.

---

## Estructura

```
Practica-MPI/
├── dominio.py        # Variable, Medicion (con ciclo y proceso MPI), AlertaAmbiental
├── estacion.py       # EstacionAmbiental (genera mediciones + carga CPU)
├── analizador.py     # AnalizadorDatos: resumen local + consolidación global
├── config.py         # Definición de estaciones de Cuenca
├── mpi_app.py        # Programa SPMD: CoordinadorMPI (secuencial + MPI)
├── benchmark.sh      # Pruebas con 1, 2 y 4 procesos
├── hosts.txt         # Hostfile de ejemplo para el clúster
└── README.md
```

---

## Entregables

- [x] Código fuente (esta carpeta).
- [x] README con instalación y ejecución.
- [x] Tabla de resultados experimentales (arriba).
- [ ] Evidencia de ejecución en el clúster *(capturas de `mpiexec -hostfile`)*.
- [ ] Archivo de configuración de nodos → [hosts.txt](hosts.txt) (ajustar IPs reales).
- [ ] Informe técnico en PDF.
