#!/usr/bin/env bash
# Pruebas de rendimiento MPI con 1, 2 y 4 procesos.
# Uso:  bash benchmark.sh [estaciones] [ciclos]
# En un solo nodo:        bash benchmark.sh 8 20
# En un cluster:          añade  -hostfile hosts.txt  a cada mpiexec.

EST=${1:-8}
CIC=${2:-20}

echo "Benchmark MPI — $EST estaciones x $CIC ciclos"
for n in 1 2 4; do
  echo "----- $n proceso(s) -----"
  mpiexec -n "$n" python3 mpi_app.py --estaciones "$EST" --ciclos "$CIC" \
    | grep -E "Aceleramiento|Tiempo (secuencial|paralelo)|Eficiencia|Datos procesados"
done
