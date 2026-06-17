"""Re-exporta los modelos de dominio para la GUI.

La fuente de verdad de estos modelos es `monitoreo.dominio`; este módulo
existe sólo para que la capa de presentación los importe desde el paquete
`UserInterface`.
"""

from monitoreo.dominio import (
    AlertaAmbiental,
    EstadisticaVariable,
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
    "EstadisticaVariable",
    "Estadisticas",
    "EstadoEstacion",
    "Medicion",
    "ModoEjecucion",
    "SnapshotMonitoreo",
    "Variable",
    "VistaEstacion",
]
