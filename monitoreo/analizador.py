"""Análisis de datos del sistema de monitoreo.

`AnalizadorDatos` cumple dos roles:

1.  `estadisticas(...)`: agrega las mediciones recibidas (promedio, mínimo,
    máximo por variable, conteos, zona de mayor riesgo, métricas de tiempo).
    Es liviano.

2.  `indice_ambiental(...)`: cálculo **intensivo en CPU** (media móvil
    ponderada + funciones trigonométricas, repetido muchas veces). Cada
    estación lo ejecuta en cada ciclo, de modo que la carga de cómputo recae
    sobre la unidad concurrente. Esto es lo que hace comparable hilos vs.
    procesos: al ser CPU-bound y Python puro, mantiene tomado el GIL —los
    hilos se serializan, los procesos sí escalan en varios núcleos.
"""

from __future__ import annotations

import math
from collections import Counter

from monitoreo.dominio import (
    AlertaAmbiental,
    EstadisticaVariable,
    Estadisticas,
    Medicion,
    Variable,
)

# Repeticiones por defecto del núcleo de cómputo. Más alto => más carga de CPU.
CARGA_CPU_DEFECTO = 600


class AnalizadorDatos:
    """Procesa mediciones y ofrece el cálculo CPU-bound de carga."""

    def __init__(self, carga_cpu: int = CARGA_CPU_DEFECTO) -> None:
        self.carga = carga_cpu

    # ------------------------------------------------------------------
    # Núcleo intensivo en CPU (Python puro, mantiene el GIL).
    # ------------------------------------------------------------------
    @staticmethod
    def indice_ambiental(valores: list[float], repeticiones: int) -> float:
        """Índice ambiental compuesto. Trabajo deliberadamente CPU-bound.

        Aplica una media móvil ponderada con un kernel trigonométrico y repite
        el barrido `repeticiones` veces para simular una carga real de análisis.
        """
        if not valores:
            return 0.0
        n = len(valores)
        acumulado = 0.0
        for _ in range(repeticiones):
            parcial = 0.0
            for i in range(n):
                inicio = i - 5 if i >= 5 else 0
                ventana = valores[inicio : i + 1]
                media_movil = sum(ventana) / len(ventana)
                v = valores[i]
                parcial += math.sqrt(abs(media_movil) + 1.0) * math.sin(v) \
                    + math.log1p(abs(v))
            acumulado += parcial
        return acumulado / repeticiones

    # ------------------------------------------------------------------
    # Agregación estadística (liviana).
    # ------------------------------------------------------------------
    def estadisticas(
        self,
        mediciones: list[Medicion],
        alertas: list[AlertaAmbiental],
        tiempos_ciclo: list[float],
        tiempo_total: float,
    ) -> Estadisticas:
        """Calcula las estadísticas generales sobre las mediciones acumuladas."""
        por_variable: dict[Variable, EstadisticaVariable] = {}
        valores_por_var: dict[Variable, list[float]] = {}
        for m in mediciones:
            valores_por_var.setdefault(m.variable, []).append(m.valor)

        for var, valores in valores_por_var.items():
            por_variable[var] = EstadisticaVariable(
                variable=var,
                n=len(valores),
                promedio=sum(valores) / len(valores),
                minimo=min(valores),
                maximo=max(valores),
            )

        zona_riesgo = "—"
        if alertas:
            conteo = Counter(a.zona for a in alertas)
            zona_riesgo = conteo.most_common(1)[0][0]

        promedio_ciclo = (
            sum(tiempos_ciclo) / len(tiempos_ciclo) if tiempos_ciclo else 0.0
        )

        return Estadisticas(
            por_variable=por_variable,
            mediciones_procesadas=len(mediciones),
            alertas_generadas=len(alertas),
            zona_mayor_riesgo=zona_riesgo,
            tiempo_total_s=tiempo_total,
            tiempo_promedio_ciclo_s=promedio_ciclo,
        )
