"""Configuración de la simulación: estaciones de Cuenca y parámetros."""

from __future__ import annotations

from monitoreo.estacion import EstacionAmbiental
from monitoreo.dominio import Variable

# Ciclos de simulación por defecto (requisito: mínimo 10).
CICLOS_DEFECTO = 12

# Número de estaciones por defecto (requisito: mínimo 4).
ESTACIONES_DEFECTO = 6

# Todas las variables ambientales disponibles, en orden de preferencia.
_TODAS_VARIABLES: list[Variable] = [
    Variable.TEMPERATURA,
    Variable.HUMEDAD,
    Variable.RUIDO,
    Variable.CO2,
    Variable.PM25,
    Variable.PM10,
]

# Definición de estaciones reales de Cuenca: (nombre, zona, variables).
# Cada una mide >= 3 variables (requisito).
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
    (
        "Estación Baños",
        "Baños",
        [Variable.TEMPERATURA, Variable.HUMEDAD, Variable.RUIDO, Variable.PM25],
    ),
    (
        "Estación Ricaurte",
        "Ricaurte",
        [Variable.TEMPERATURA, Variable.HUMEDAD, Variable.CO2, Variable.PM10],
    ),
    (
        "Estación Sayausí",
        "Sayausí",
        [Variable.TEMPERATURA, Variable.HUMEDAD, Variable.RUIDO, Variable.PM25],
    ),
    (
        "Estación El Batán",
        "El Batán",
        [Variable.TEMPERATURA, Variable.RUIDO, Variable.CO2, Variable.PM25, Variable.PM10],
    ),
    (
        "Estación Tarqui",
        "Tarqui",
        [Variable.TEMPERATURA, Variable.HUMEDAD, Variable.RUIDO, Variable.CO2],
    ),
    (
        "Estación El Valle",
        "El Valle",
        [Variable.TEMPERATURA, Variable.HUMEDAD, Variable.CO2, Variable.PM25, Variable.PM10],
    ),
]


def _definicion_sintetica(indice: int) -> tuple[str, str, list[Variable]]:
    """Genera la definición de una estación adicional (para tamaños grandes).

    Permite escalar el número de estaciones más allá de las predefinidas, de
    modo que se puedan probar los tamaños 4×10, 8×20 y 12×30 que pide la
    práctica. Cada estación sintética mide 4 variables rotadas.
    """
    inicio = indice % len(_TODAS_VARIABLES)
    variables = [_TODAS_VARIABLES[(inicio + k) % len(_TODAS_VARIABLES)] for k in range(4)]
    return (f"Estación Zona {indice + 1}", f"Zona {indice + 1}", variables)


def crear_estaciones(n: int = ESTACIONES_DEFECTO) -> list[EstacionAmbiental]:
    """Construye la lista de `n` estaciones ambientales de la simulación.

    Reutiliza las estaciones reales de Cuenca y, si se piden más de las
    definidas, genera estaciones sintéticas para alcanzar el total `n`.
    """
    n = max(1, n)
    definiciones: list[tuple[str, str, list[Variable]]] = []
    for i in range(n):
        if i < len(DEFINICION_ESTACIONES):
            definiciones.append(DEFINICION_ESTACIONES[i])
        else:
            definiciones.append(_definicion_sintetica(i))

    return [
        EstacionAmbiental(id=i + 1, nombre=nombre, zona=zona, variables=variables, semilla=100 + i)
        for i, (nombre, zona, variables) in enumerate(definiciones)
    ]
