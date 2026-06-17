"""Interfaz gráfica (Tkinter) del Sistema de Monitoreo Ambiental Urbano.

La GUI está desacoplada del motor: sólo consume objetos `SnapshotMonitoreo`
(ver `monitoreo.dominio`) producidos por `ControladorMonitoreo`, por lo que
sirve igual para los modos secuencial, por hilos o por procesos.
"""

from UserInterface.models import (
    AlertaAmbiental,
    Estadisticas,
    EstadoEstacion,
    Medicion,
    ModoEjecucion,
    SnapshotMonitoreo,
    Variable,
    VistaEstacion,
)

__all__ = [
    "AlertaAmbiental",
    "Estadisticas",
    "EstadoEstacion",
    "Medicion",
    "ModoEjecucion",
    "SnapshotMonitoreo",
    "Variable",
    "VistaEstacion",
]
