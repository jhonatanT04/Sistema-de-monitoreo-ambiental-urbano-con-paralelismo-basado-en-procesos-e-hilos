"""Modelos de datos que la GUI dibuja.

La interfaz nunca calcula nada: recibe un `SnapshotMonitoreo` (una foto
inmutable del estado del sistema en un instante) y lo pinta. Quien genere
esos snapshots —ejecución secuencial, por hilos o por procesos— es ajeno
a este paquete.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class EstadoEstacion(str, Enum):
    """Estado del ciclo de vida de una estación de monitoreo."""

    ACTIVA = "Activa"
    ESPERANDO = "Esperando"
    PROCESANDO = "Procesando"
    FINALIZADA = "Finalizada"


class ModoEjecucion(str, Enum):
    """Modo con el que el motor de monitoreo procesa las estaciones."""

    SECUENCIAL = "Secuencial"
    HILOS = "Hilos"
    PROCESOS = "Procesos"


@dataclass(frozen=True)
class Medicion:
    """Una medición ambiental tomada por una estación."""

    parametro: str          # p. ej. "PM2.5", "CO2", "Temperatura"
    valor: float
    unidad: str             # p. ej. "µg/m³", "ppm", "°C"
    instante: datetime = field(default_factory=datetime.now)

    def __str__(self) -> str:
        return f"{self.parametro}: {self.valor:g} {self.unidad}"


@dataclass(frozen=True)
class Estacion:
    """Una estación ambiental y su estado actual."""

    id: int
    nombre: str
    estado: EstadoEstacion
    ultima_medicion: Medicion | None = None


@dataclass(frozen=True)
class Alerta:
    """Una alerta activa generada por una medición fuera de umbral."""

    estacion: str
    mensaje: str
    severidad: str = "Media"          # "Baja" | "Media" | "Alta"
    instante: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True)
class Estadisticas:
    """Estadísticas generales agregadas del sistema."""

    estaciones_totales: int = 0
    estaciones_activas: int = 0
    estaciones_finalizadas: int = 0
    mediciones_totales: int = 0
    alertas_totales: int = 0


@dataclass(frozen=True)
class SnapshotMonitoreo:
    """Foto completa del estado del sistema en un instante dado.

    Es la única unidad de información que viaja del motor a la GUI.
    """

    estaciones: list[Estacion] = field(default_factory=list)
    alertas: list[Alerta] = field(default_factory=list)
    estadisticas: Estadisticas = field(default_factory=Estadisticas)
    modo: ModoEjecucion = ModoEjecucion.SECUENCIAL
    tiempo_ejecucion_s: float = 0.0
    en_ejecucion: bool = False
