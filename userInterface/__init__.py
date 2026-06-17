"""Interfaz gráfica del Sistema de Monitoreo Ambiental Urbano.

Este paquete contiene la capa de presentación (Tkinter). Está desacoplada
del motor de monitoreo: la GUI sólo consume objetos `SnapshotMonitoreo`
(ver `models.py`), por lo que puede alimentarse desde la ejecución
secuencial, por hilos o por procesos sin cambios en la interfaz.
"""

from userInterface.models import (
    Alerta,
    Estacion,
    Estadisticas,
    EstadoEstacion,
    Medicion,
    ModoEjecucion,
    SnapshotMonitoreo,
)

__all__ = [
    "Alerta",
    "Estacion",
    "Estadisticas",
    "EstadoEstacion",
    "Medicion",
    "ModoEjecucion",
    "SnapshotMonitoreo",
]
