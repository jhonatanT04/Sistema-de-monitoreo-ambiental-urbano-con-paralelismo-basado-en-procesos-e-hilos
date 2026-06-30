from __future__ import annotations

import argparse
import platform

from mpi4py import MPI

from analizador import AnalizadorDatos
from config import crear_estacion

ETIQUETA_ASIGNACION = 11


class CoordinadorMPI:
    def __init__(self, comm, n_estaciones: int, ciclos: int, carga: int) -> None:
        self.comm = comm
        self.rank = comm.Get_rank()
        self.size = comm.Get_size()
        self.n_estaciones = n_estaciones
        self.ciclos = ciclos
        self.carga = carga

    def _repartir(self, total: int, partes: int) -> list[list[int]]:
        # Round-robin: la estacion i va al proceso (i % partes). Divide el trabajo
        # de forma equilibrada incluso si total no es multiplo de partes.
        asignaciones: list[list[int]] = [[] for _ in range(partes)]
        for i in range(total):
            asignaciones[i % partes].append(i)
        return asignaciones

    def _simular(self, indices: list[int], proceso: int) -> dict:
        estaciones = [crear_estacion(i) for i in indices]
        mediciones = []
        for ciclo in range(self.ciclos):
            for est in estaciones:
                mediciones.extend(est.trabajar_ciclo(ciclo, self.carga, proceso))
        return AnalizadorDatos.resumen_local(mediciones, proceso)

    # ------------------------------------------------------------------
    # Version SECUENCIAL (referencia): solo el proceso 0, todas las estaciones.
    # ------------------------------------------------------------------
    def ejecutar_secuencial(self) -> tuple[float, dict]:
        t0 = MPI.Wtime()
        resumen = self._simular(list(range(self.n_estaciones)), self.rank)
        t = MPI.Wtime() - t0
        return t, AnalizadorDatos.consolidar([resumen])

    # ------------------------------------------------------------------
    # Version PARALELA con MPI (SPMD).
    #   - Punto a punto (send/recv): el coordinador reparte las estaciones.
    #   - Colectiva (gather + reduce): consolida resultados en el proceso 0.
    # ------------------------------------------------------------------
    def ejecutar_paralelo(self):
        comm = self.comm

        # 1) COMUNICACION PUNTO A PUNTO: el coordinador (rank 0) asigna a cada
        #    proceso trabajador su lista de estaciones mediante send/recv.
        if self.rank == 0:
            asignaciones = self._repartir(self.n_estaciones, self.size)
            mis_indices = asignaciones[0]
            for r in range(1, self.size):
                comm.send(asignaciones[r], dest=r, tag=ETIQUETA_ASIGNACION)
        else:
            mis_indices = comm.recv(source=0, tag=ETIQUETA_ASIGNACION)

        comm.Barrier()
        t0 = MPI.Wtime()

        # 2) Cada proceso trabaja SOLO sus estaciones (memoria local).
        resumen_local = self._simular(mis_indices, self.rank)

        # 3) COMUNICACION COLECTIVA: gather de los resumenes locales en rank 0
        #    y reduce del total de mediciones procesadas.
        resumenes = comm.gather(resumen_local, root=0)
        total_med = comm.reduce(resumen_local["n"], op=MPI.SUM, root=0)

        local_t = MPI.Wtime() - t0
        # El tiempo paralelo es el del proceso mas lento (cuello de botella).
        tp = comm.reduce(local_t, op=MPI.MAX, root=0)

        reparto = [len(x) for x in self._repartir(self.n_estaciones, self.size)]
        if self.rank == 0:
            stats = AnalizadorDatos.consolidar(resumenes)
            return tp, stats, total_med, reparto
        return None


def _imprimir_entorno(comm) -> None:
    print("=" * 70)
    print("SISTEMA DE MONITOREO AMBIENTAL URBANO — VERSION MPI (CUENCA)")
    print("=" * 70)
    print(f"Python : {platform.python_version()}  ({platform.system()} {platform.release()})")
    version = MPI.Get_library_version().replace("\x00", "").splitlines()[0]
    print(f"MPI    : {version}")
    print(f"Procesos MPI (size): {comm.Get_size()}")
    print("=" * 70)


def _imprimir_stats(stats: dict) -> None:
    print(f"  Mediciones procesadas : {stats['mediciones_procesadas']}")
    print(f"  Alertas generadas     : {stats['alertas_generadas']}")
    print(f"  Zona de mayor riesgo  : {stats['zona_mayor_riesgo']}")
    print(f"  Procesos participantes: {stats['procesos']}")
    print("  Por variable (prom / min / max):")
    for var, d in stats["por_variable"].items():
        print(f"    - {var:12} {d['promedio']:7.1f} / {d['min']:6.1f} / {d['max']:6.1f}  (n={d['n']})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitoreo ambiental urbano — MPI")
    parser.add_argument("--estaciones", type=int, default=8, help="Numero de estaciones.")
    parser.add_argument("--ciclos", type=int, default=20, help="Ciclos de simulacion.")
    parser.add_argument("--carga", type=int, default=600, help="Carga de CPU del analisis.")
    parser.add_argument("--solo-paralelo", action="store_true",
                        help="Omite el baseline secuencial (no calcula speedup).")
    args = parser.parse_args()

    comm = MPI.COMM_WORLD
    coord = CoordinadorMPI(comm, args.estaciones, args.ciclos, args.carga)

    # Baseline secuencial: lo ejecuta SOLO el proceso 0 mientras los demas esperan.
    ts = None
    stats_seq = None
    if comm.Get_rank() == 0 and not args.solo_paralelo:
        ts, stats_seq = coord.ejecutar_secuencial()
    comm.Barrier()

    # Version paralela: la ejecutan TODOS los procesos.
    resultado = coord.ejecutar_paralelo()

    if comm.Get_rank() == 0:
        tp, stats_par, total_med, reparto = resultado
        _imprimir_entorno(comm)
        print(f"Configuracion: {args.estaciones} estaciones x {args.ciclos} ciclos "
              f"· carga {args.carga}")
        print(f"Reparto de estaciones por proceso: {reparto}\n")

        if ts is not None:
            print(f">>> SECUENCIAL (1 proceso)  Ts = {ts:.3f} s")
            _imprimir_stats(stats_seq)
            print()

        print(f">>> PARALELO MPI ({comm.Get_size()} procesos)  Tp = {tp:.3f} s")
        _imprimir_stats(stats_par)

        print("\n" + "=" * 70)
        print("RENDIMIENTO")
        print("=" * 70)
        print(f"  Procesos (p)        : {comm.Get_size()}")
        print(f"  Datos procesados    : {total_med} mediciones")
        if ts is not None and tp:
            speedup = ts / tp
            eficiencia = speedup / comm.Get_size()
            print(f"  Tiempo secuencial Ts: {ts:.3f} s")
            print(f"  Tiempo paralelo   Tp: {tp:.3f} s")
            print(f"  Aceleramiento  S=Ts/Tp : x{speedup:.2f}")
            print(f"  Eficiencia    E=S/p    : {eficiencia:.2%}")
        else:
            print(f"  Tiempo paralelo   Tp: {tp:.3f} s")
        print("=" * 70)


if __name__ == "__main__":
    main()
