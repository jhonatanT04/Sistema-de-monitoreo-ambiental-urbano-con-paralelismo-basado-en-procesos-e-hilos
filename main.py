from __future__ import annotations

import argparse
import platform
import sys
import sysconfig
from time import perf_counter

from monitoreo.controlador import ControladorMonitoreo
from monitoreo.dominio import Estadisticas, ModoEjecucion


def _estado_gil() -> str:
    is_gil_enabled = getattr(sys, "_is_gil_enabled", None)
    if callable(is_gil_enabled):
        return "activo (free-threaded)" if is_gil_enabled() else "deshabilitado (free-threaded)"
    if sysconfig.get_config_var("Py_GIL_DISABLED"):
        return "deshabilitable (build sin GIL)"
    return "activo"


def _imprimir_entorno() -> None:
    import multiprocessing

    print("=" * 70)
    print("SISTEMA DE MONITOREO AMBIENTAL URBANO — CUENCA")
    print("=" * 70)
    print(f"Python : {platform.python_version()}  ({platform.system()} {platform.release()})")
    print(f"Núcleos: {multiprocessing.cpu_count()}    GIL: {_estado_gil()}")
    print("=" * 70)


def _mediciones_por_segundo(mediciones: int, tiempo_s: float) -> float:
    return mediciones / tiempo_s if tiempo_s else float("inf")


def _imprimir_estadisticas(stats: Estadisticas, tiempo_s: float | None = None) -> None:
    dt = tiempo_s if tiempo_s is not None else stats.tiempo_total_s
    print(f"  Mediciones procesadas : {stats.mediciones_procesadas}")
    print(f"  Mediciones/segundo    : {_mediciones_por_segundo(stats.mediciones_procesadas, dt):.1f} med/s")
    print(f"  Alertas generadas     : {stats.alertas_generadas}")
    print(f"  Zona de mayor riesgo  : {stats.zona_mayor_riesgo}")
    print(f"  Tiempo total          : {stats.tiempo_total_s:.3f} s")
    print(f"  Tiempo promedio/ciclo : {stats.tiempo_promedio_ciclo_s:.4f} s")
    print("  Por variable (prom / mín / máx):")
    for var, ev in stats.por_variable.items():
        print(
            f"    - {var.etiqueta:12} {ev.promedio:7.1f} / {ev.minimo:6.1f} / "
            f"{ev.maximo:6.1f} {var.unidad}  (n={ev.n})"
        )


def comparar(ciclos: int, carga: int, estaciones: int, repeticiones: int = 1) -> None:
    _imprimir_entorno()
    print(f"Configuración: {estaciones} estaciones × {ciclos} ciclos · "
          f"{repeticiones} repetición(es) por modo\n")
    tiempos: dict[ModoEjecucion, float] = {}
    mediciones: dict[ModoEjecucion, int] = {}
    for modo in ModoEjecucion:
        muestras: list[float] = []
        snap = None
        for _ in range(max(1, repeticiones)):
            ctrl = ControladorMonitoreo(
                ciclos=ciclos, carga_cpu=carga, n_estaciones=estaciones
            )
            t = perf_counter()
            snap = ctrl.ejecutar(modo)
            muestras.append(perf_counter() - t)
        dt = sum(muestras) / len(muestras)
        tiempos[modo] = dt
        mediciones[modo] = snap.estadisticas.mediciones_procesadas if snap else 0
        detalle = "  ".join(f"{m:.3f}s" for m in muestras)
        print(f"\n>>> MODO {modo.value.upper()}  (promedio {dt:.3f} s · muestras: {detalle})")
        if snap is not None:
            _imprimir_estadisticas(snap.estadisticas, dt)

    base = tiempos[ModoEjecucion.SECUENCIAL]
    t_hilos = tiempos[ModoEjecucion.HILOS]
    t_proc = tiempos[ModoEjecucion.PROCESOS]
    print("\n" + "=" * 70)
    print("COMPARATIVA DE RENDIMIENTO (línea base: secuencial)")
    print("=" * 70)
    print(f"  {'Modo':11} {'Tiempo':>9}   {'Mediciones/s':>13}   {'Speedup':>8}")
    for modo, dt in tiempos.items():
        speedup = base / dt if dt else float("inf")
        throughput = _mediciones_por_segundo(mediciones[modo], dt)
        print(f"  {modo.value:11} {dt:7.3f} s   {throughput:11.1f}    x{speedup:.2f}")
    print("-" * 70)
    print(f"  Sthread  = Ts / Tthread  = {base:.3f} / {t_hilos:.3f} = "
          f"x{(base / t_hilos if t_hilos else float('inf')):.2f}")
    print(f"  Sprocess = Ts / Tprocess = {base:.3f} / {t_proc:.3f} = "
          f"x{(base / t_proc if t_proc else float('inf')):.2f}")
    print("=" * 70)


def ejecutar_modo(modo_txt: str, ciclos: int, carga: int, estaciones: int) -> None:
    _imprimir_entorno()
    modo = ModoEjecucion[modo_txt.upper()]
    ctrl = ControladorMonitoreo(ciclos=ciclos, carga_cpu=carga, n_estaciones=estaciones)
    t = perf_counter()
    snap = ctrl.ejecutar(modo)
    dt = perf_counter() - t
    print(f"\n>>> MODO {modo.value.upper()}  ({dt:.3f} s)")
    _imprimir_estadisticas(snap.estadisticas)


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitoreo ambiental urbano — Cuenca")
    parser.add_argument(
        "--modo",
        choices=["secuencial", "hilos", "procesos"],
        help="Ejecuta un solo modo (por defecto compara los tres).",
    )
    parser.add_argument("--ciclos", type=int, default=12, help="Ciclos de simulación (mín. 10).")
    parser.add_argument("--estaciones", type=int, default=6, help="Número de estaciones (mín. 4).")
    parser.add_argument("--carga", type=int, default=600, help="Carga de CPU del análisis.")
    parser.add_argument(
        "--repeticiones", type=int, default=1,
        help="Repeticiones por modo para promediar tiempos (recomendado 3).",
    )
    parser.add_argument("--gui", action="store_true", help="Abre la interfaz gráfica.")
    args = parser.parse_args()

    if args.gui:
        from UserInterface.app import main as gui_main

        gui_main()
        return

    if args.modo:
        ejecutar_modo(args.modo, args.ciclos, args.carga, args.estaciones)
    else:
        comparar(args.ciclos, args.carga, args.estaciones, args.repeticiones)

if __name__ == "__main__":
    main()
