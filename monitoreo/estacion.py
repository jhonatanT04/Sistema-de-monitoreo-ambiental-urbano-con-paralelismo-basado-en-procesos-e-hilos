"""Estación ambiental: unidad concurrente que genera mediciones."""

from __future__ import annotations

import random

from monitoreo.analizador import AnalizadorDatos
from monitoreo.dominio import EstadoEstacion, Medicion, Variable

# Perfil de simulación por variable: (base, ruido_sigma, prob_pico).
# El "pico" empuja el valor por encima del umbral para generar alertas.
PERFILES: dict[Variable, tuple[float, float, float]] = {
    Variable.TEMPERATURA: (16.0, 4.0, 0.12),
    Variable.HUMEDAD: (68.0, 12.0, 0.10),
    Variable.RUIDO: (55.0, 9.0, 0.15),
    Variable.CO2: (480.0, 130.0, 0.10),
    Variable.PM25: (24.0, 12.0, 0.15),
    Variable.PM10: (45.0, 20.0, 0.15),
}

# Cuántos valores recientes conserva cada estación para el índice ambiental.
VENTANA_HISTORIAL = 60


class EstacionAmbiental:
    """Genera lecturas simuladas para un conjunto de variables ambientales.

    Es picklable: solo guarda tipos simples y un `random.Random`, de modo que
    pueda enviarse a un `multiprocessing.Process`.
    """

    def __init__(
        self,
        id: int,
        nombre: str,
        zona: str,
        variables: list[Variable],
        semilla: int | None = None,
    ) -> None:
        self.id = id
        self.nombre = nombre
        self.zona = zona
        self.variables = list(variables)
        self.estado = EstadoEstacion.ESPERANDO
        self._rng = random.Random(semilla if semilla is not None else id * 7919)
        self._historial: list[float] = []

    # ------------------------------------------------------------------
    def _simular(self, variable: Variable) -> float:
        base, sigma, prob_pico = PERFILES[variable]
        valor = base + self._rng.gauss(0.0, sigma)
        if self._rng.random() < prob_pico:
            # Pico que típicamente supera el umbral.
            valor = max(valor, variable.umbral * self._rng.uniform(1.05, 1.6))
        return round(max(0.0, valor), 1)

    def generar_mediciones(self, ciclo: int) -> list[Medicion]:
        """Genera una medición por cada variable de la estación."""
        mediciones = [
            Medicion(self.nombre, self.zona, var, self._simular(var))
            for var in self.variables
        ]
        self._historial.extend(m.valor for m in mediciones)
        if len(self._historial) > VENTANA_HISTORIAL:
            del self._historial[:-VENTANA_HISTORIAL]
        return mediciones

    def trabajar_ciclo(
        self, ciclo: int, carga_cpu: int
    ) -> tuple[list[Medicion], float]:
        """Ejecuta el trabajo de un ciclo: generar + análisis CPU-bound.

        Devuelve las mediciones y el índice ambiental calculado. El cómputo
        pesado ocurre aquí, dentro de la unidad concurrente.
        """
        self.estado = EstadoEstacion.PROCESANDO
        mediciones = self.generar_mediciones(ciclo)
        indice = AnalizadorDatos.indice_ambiental(self._historial, carga_cpu)
        self.estado = EstadoEstacion.ESPERANDO
        return mediciones, indice

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"EstacionAmbiental(#{self.id} {self.nombre!r}, zona={self.zona!r})"
