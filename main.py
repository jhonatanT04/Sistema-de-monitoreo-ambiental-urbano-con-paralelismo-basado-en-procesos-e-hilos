"""Punto de entrada por consola: ejecuta y compara los tres modos.

Uso:
    python main.py                      # compara los 3 modos (línea base)
    python main.py --modo procesos      # ejecuta un solo modo
    python main.py --ciclos 15 --carga 800
    python main.py --gui                # abre la interfaz gráfica

La versión secuencial es la línea base de rendimiento; al final se imprime
el speedup de hilos y procesos respecto a ella.
"""

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


def _imprimir_estadisticas(stats: Estadisticas) -> None:
    print(f"  Mediciones procesadas : {stats.mediciones_procesadas}")
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


def comparar(ciclos: int, carga: int) -> None:
    _imprimir_entorno()
    tiempos: dict[ModoEjecucion, float] = {}
    for modo in ModoEjecucion:
        ctrl = ControladorMonitoreo(ciclos=ciclos, carga_cpu=carga)
        t = perf_counter()
        snap = ctrl.ejecutar(modo)
        dt = perf_counter() - t
        tiempos[modo] = dt
        print(f"\n>>> MODO {modo.value.upper()}  ({dt:.3f} s)")
        _imprimir_estadisticas(snap.estadisticas)

    base = tiempos[ModoEjecucion.SECUENCIAL]
    print("\n" + "=" * 70)
    print("COMPARATIVA DE RENDIMIENTO (línea base: secuencial)")
    print("=" * 70)
    for modo, dt in tiempos.items():
        speedup = base / dt if dt else float("inf")
        print(f"  {modo.value:11} {dt:7.3f} s   speedup x{speedup:.2f}")
    print("=" * 70)


def ejecutar_modo(modo_txt: str, ciclos: int, carga: int) -> None:
    _imprimir_entorno()
    modo = ModoEjecucion[modo_txt.upper()]
    ctrl = ControladorMonitoreo(ciclos=ciclos, carga_cpu=carga)
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
    parser.add_argument("--carga", type=int, default=600, help="Carga de CPU del análisis.")
    parser.add_argument("--gui", action="store_true", help="Abre la interfaz gráfica.")
    args = parser.parse_args()

    if args.gui:
        from UserInterface.app import main as gui_main

        gui_main()
        return

    if args.modo:
        ejecutar_modo(args.modo, args.ciclos, args.carga)
    else:
        comparar(args.ciclos, args.carga)


if __name__ == "__main__":
    main()
