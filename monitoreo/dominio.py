"""Modelos de dominio del sistema de monitoreo ambiental.

Todas las estructuras de datos son inmutables (`frozen=True`) y picklables,
de modo que las `Medicion` puedan viajar por una `multiprocessing.Queue`
desde los procesos de las estaciones hacia el controlador.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Variable(Enum):
    """Variable ambiental medida por una estación.

    Cada miembro lleva su etiqueta legible, su unidad y el umbral por encima
    del cual se genera una alerta.
    """

    TEMPERATURA = ("Temperatura", "°C", 26.0)
    HUMEDAD = ("Humedad", "%", 90.0)
    RUIDO = ("Ruido", "dB", 75.0)
    CO2 = ("CO₂", "ppm", 1000.0)
    PM25 = ("PM2.5", "µg/m³", 50.0)
    PM10 = ("PM10", "µg/m³", 100.0)

    def __init__(self, etiqueta: str, unidad: str, umbral: float) -> None:
        self.etiqueta = etiqueta
        self.unidad = unidad
        self.umbral = umbral

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.etiqueta


class EstadoEstacion(str, Enum):
    """Estado del ciclo de vida de una estación."""

    ACTIVA = "Activa"
    ESPERANDO = "Esperando"
    PROCESANDO = "Procesando"
    FINALIZADA = "Finalizada"


class ModoEjecucion(str, Enum):
    """Modo con el que el controlador procesa las estaciones."""

    SECUENCIAL = "Secuencial"
    HILOS = "Hilos"
    PROCESOS = "Procesos"


@dataclass(frozen=True)
class Medicion:
    """Lectura generada por una estación en un instante dado."""

    estacion: str
    zona: str
    variable: Variable
    valor: float
    instante: datetime = field(default_factory=datetime.now)

    @property
    def unidad(self) -> str:
        return self.variable.unidad

    @property
    def en_alerta(self) -> bool:
        """True si la lectura supera el umbral de su variable."""
        return self.valor > self.variable.umbral

    def __str__(self) -> str:
        return f"{self.variable.etiqueta}: {self.valor:.1f} {self.variable.unidad}"


@dataclass(frozen=True)
class AlertaAmbiental:
    """Alerta emitida cuando una variable supera su umbral."""

    estacion: str
    zona: str
    variable: Variable
    valor: float
    umbral: float
    instante: datetime = field(default_factory=datetime.now)

    @property
    def severidad(self) -> str:
        razon = self.valor / self.umbral if self.umbral else 0.0
        if razon >= 1.5:
            return "Alta"
        if razon >= 1.2:
            return "Media"
        return "Baja"

    @property
    def mensaje(self) -> str:
        return (
            f"{self.variable.etiqueta} = {self.valor:.1f} {self.variable.unidad} "
            f"(umbral {self.umbral:.0f})"
        )

    @classmethod
    def desde_medicion(cls, m: Medicion) -> "AlertaAmbiental":
        return cls(
            estacion=m.estacion,
            zona=m.zona,
            variable=m.variable,
            valor=m.valor,
            umbral=m.variable.umbral,
            instante=m.instante,
        )


@dataclass(frozen=True)
class EstadisticaVariable:
    """Resumen estadístico de una variable sobre las mediciones recibidas."""

    variable: Variable
    n: int
    promedio: float
    minimo: float
    maximo: float


@dataclass(frozen=True)
class Estadisticas:
    """Estadísticas generales calculadas por `AnalizadorDatos`."""

    por_variable: dict[Variable, EstadisticaVariable] = field(default_factory=dict)
    mediciones_procesadas: int = 0
    alertas_generadas: int = 0
    zona_mayor_riesgo: str = "—"
    tiempo_total_s: float = 0.0
    tiempo_promedio_ciclo_s: float = 0.0
    # Conteos rápidos de estado para la cabecera de la GUI.
    estaciones_totales: int = 0
    estaciones_activas: int = 0
    estaciones_finalizadas: int = 0


@dataclass(frozen=True)
class VistaEstacion:
    """Foto del estado de una estación para la GUI (no es la estación viva)."""

    id: int
    nombre: str
    zona: str
    estado: EstadoEstacion
    ultima_medicion: Medicion | None = None


@dataclass(frozen=True)
class SnapshotMonitoreo:
    """Foto completa del sistema en un instante. Única unidad que ve la GUI."""

    estaciones: list[VistaEstacion] = field(default_factory=list)
    alertas: list[AlertaAmbiental] = field(default_factory=list)
    estadisticas: Estadisticas = field(default_factory=Estadisticas)
    modo: ModoEjecucion = ModoEjecucion.SECUENCIAL
    ciclo_actual: int = 0
    ciclos_totales: int = 0
    tiempo_ejecucion_s: float = 0.0
    en_ejecucion: bool = False
