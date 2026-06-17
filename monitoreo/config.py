"""Configuración de la simulación: estaciones de Cuenca y parámetros."""

from __future__ import annotations

from monitoreo.estacion import EstacionAmbiental
from monitoreo.dominio import Variable

# Ciclos de simulación por defecto (requisito: mínimo 10).
CICLOS_DEFECTO = 12

# Definición de estaciones: (nombre, zona, variables). Cada una mide >= 3.
DEFINICION_ESTACIONES: list[tuple[str, str, list[Variable]]] = [
    (
        "Estación Centro",
        "El Centro Histórico",
        [Variable.TEMPERATURA, Variable.RUIDO, Variable.CO2, Variable.PM25, Variable.PM10],
    ),
    (
        "Estación Totoracocha",
        "Totoracocha",
        [Variable.TEMPERATURA, Variable.HUMEDAD, Variable.PM25, Variable.PM10],
    ),
    (
        "Estación Yanuncay",
        "Yanuncay",
        [Variable.TEMPERATURA, Variable.HUMEDAD, Variable.RUIDO, Variable.PM25],
    ),
    (
        "Estación El Vecino",
        "El Vecino",
        [Variable.TEMPERATURA, Variable.CO2, Variable.PM25, Variable.PM10],
    ),
    (
        "Estación Monay",
        "Monay",
        [Variable.TEMPERATURA, Variable.HUMEDAD, Variable.RUIDO, Variable.CO2],
    ),
    (
        "Estación Machángara",
        "Machángara (industrial)",
        [Variable.TEMPERATURA, Variable.RUIDO, Variable.CO2, Variable.PM25, Variable.PM10],
    ),
]


def crear_estaciones() -> list[EstacionAmbiental]:
    """Construye la lista de estaciones ambientales de la simulación."""
    return [
        EstacionAmbiental(id=i + 1, nombre=nombre, zona=zona, variables=variables, semilla=100 + i)
        for i, (nombre, zona, variables) in enumerate(DEFINICION_ESTACIONES)
    ]
