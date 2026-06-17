"""Interfaz gráfica (Tkinter) del Sistema de Monitoreo Ambiental Urbano.

DECISIÓN DE HILOS
-----------------
Tkinter NO es thread-safe: todos los widgets deben tocarse desde el mismo
hilo que ejecuta `mainloop()`. Por eso la GUI vive en el HILO PRINCIPAL.

El motor de monitoreo (secuencial, por hilos o por procesos) corre aparte y
publica su estado como `SnapshotMonitoreo` en una `queue.Queue`. La GUI NO
lee de los hilos secundarios directamente: se reprograma a sí misma con
`widget.after(...)` y drena la cola dentro del hilo de la GUI. Así, toda
mutación de widgets ocurre en el hilo principal y se evitan actualizaciones
inseguras desde hilos secundarios.

Ejecución de demostración (sin motor real):
    python -m UserInterface
"""

from __future__ import annotations

import multiprocessing
import platform
import queue
import sys
import sysconfig
import tkinter as tk
from tkinter import ttk

from userInterface.models import (
    Alerta,
    Estacion,
    Estadisticas,
    EstadoEstacion,
    ModoEjecucion,
    SnapshotMonitoreo,
)

# --- Intervalo de refresco de la GUI (ms) -------------------------------------
INTERVALO_REFRESCO_MS = 250

# --- Colores por estado de estación -------------------------------------------
COLOR_ESTADO = {
    EstadoEstacion.ACTIVA: "#1b7f3b",
    EstadoEstacion.ESPERANDO: "#8a6d00",
    EstadoEstacion.PROCESANDO: "#1f5fb0",
    EstadoEstacion.FINALIZADA: "#666666",
}


# ---------------------------------------------------------------------------
# Información del entorno de ejecución
# ---------------------------------------------------------------------------
def _estado_gil() -> str:
    """Describe el estado del GIL cuando el intérprete lo expone."""
    is_gil_enabled = getattr(sys, "_is_gil_enabled", None)
    if callable(is_gil_enabled):
        return "Activo (free-threaded)" if is_gil_enabled() else "Deshabilitado (free-threaded)"
    if sysconfig.get_config_var("Py_GIL_DISABLED"):
        return "Deshabilitable (build sin GIL)"
    return "Activo"


def _info_entorno() -> dict[str, str]:
    return {
        "Versión de Python": platform.python_version(),
        "Sistema operativo": f"{platform.system()} {platform.release()}",
        "Núcleos de CPU": str(multiprocessing.cpu_count()),
        "Estado del GIL": _estado_gil(),
    }


# ---------------------------------------------------------------------------
# Ventana principal
# ---------------------------------------------------------------------------
class MonitoreoGUI(tk.Tk):
    """Ventana principal del sistema de monitoreo.

    Se alimenta de `SnapshotMonitoreo` colocados en `cola`. Si no se pasa una
    cola, la ventana funciona igual pero permanece en estado vacío hasta que
    se llame a `aplicar_snapshot(...)` manualmente.
    """

    def __init__(self, cola: "queue.Queue[SnapshotMonitoreo] | None" = None) -> None:
        super().__init__()
        self._cola = cola

        self.title("Sistema de Monitoreo Ambiental Urbano")
        self.geometry("1040x680")
        self.minsize(900, 600)

        self._configurar_estilos()
        self._construir_cabecera()
        self._construir_cuerpo()
        self._construir_pie()

        # Pintar el entorno una sola vez (no cambia durante la ejecución).
        self._pintar_entorno()

        # Arranca el sondeo de la cola en el hilo de la GUI.
        if self._cola is not None:
            self.after(INTERVALO_REFRESCO_MS, self._sondear_cola)

    # -- Estilos ------------------------------------------------------------
    def _configurar_estilos(self) -> None:
        estilo = ttk.Style(self)
        try:
            estilo.theme_use("clam")
        except tk.TclError:
            pass
        estilo.configure("Titulo.TLabel", font=("TkDefaultFont", 13, "bold"))
        estilo.configure("Seccion.TLabelframe.Label", font=("TkDefaultFont", 10, "bold"))
        estilo.configure("Stat.TLabel", font=("TkDefaultFont", 10))
        estilo.configure("StatVal.TLabel", font=("TkDefaultFont", 14, "bold"))
        estilo.configure("Treeview", rowheight=26)

    # -- Cabecera: título, modo, tiempo de ejecución ------------------------
    def _construir_cabecera(self) -> None:
        barra = ttk.Frame(self, padding=(12, 10))
        barra.pack(fill="x")

        ttk.Label(barra, text="🌆 Monitoreo Ambiental Urbano",
                  style="Titulo.TLabel").pack(side="left")

        self._lbl_estado_motor = ttk.Label(barra, text="● Detenido", foreground="#999999")
        self._lbl_estado_motor.pack(side="right")

        self._lbl_tiempo = ttk.Label(barra, text="Tiempo: 0.0 s")
        self._lbl_tiempo.pack(side="right", padx=(0, 18))

        self._lbl_modo = ttk.Label(barra, text="Modo: —")
        self._lbl_modo.pack(side="right", padx=(0, 18))

        ttk.Separator(self, orient="horizontal").pack(fill="x")

    # -- Cuerpo: estaciones | (alertas + estadísticas + entorno) ------------
    def _construir_cuerpo(self) -> None:
        cuerpo = ttk.Frame(self, padding=12)
        cuerpo.pack(fill="both", expand=True)

        # Columna izquierda: tabla de estaciones.
        izq = ttk.Labelframe(cuerpo, text="Estaciones ambientales", padding=8,
                             style="Seccion.TLabelframe")
        izq.pack(side="left", fill="both", expand=True)

        columnas = ("id", "nombre", "estado", "medicion", "hora")
        self._tabla = ttk.Treeview(izq, columns=columnas, show="headings", selectmode="browse")
        for col, texto, ancho, anchor in (
            ("id", "ID", 50, "center"),
            ("nombre", "Estación", 180, "w"),
            ("estado", "Estado", 110, "center"),
            ("medicion", "Última medición", 200, "w"),
            ("hora", "Hora", 90, "center"),
        ):
            self._tabla.heading(col, text=texto)
            self._tabla.column(col, width=ancho, anchor=anchor)

        for estado, color in COLOR_ESTADO.items():
            self._tabla.tag_configure(estado.name, foreground=color)

        scroll = ttk.Scrollbar(izq, orient="vertical", command=self._tabla.yview)
        self._tabla.configure(yscrollcommand=scroll.set)
        self._tabla.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # Columna derecha: estadísticas, alertas, entorno.
        der = ttk.Frame(cuerpo)
        der.pack(side="right", fill="both", padx=(12, 0))
        der.configure(width=340)

        self._construir_estadisticas(der)
        self._construir_alertas(der)
        self._construir_entorno(der)

    def _construir_estadisticas(self, padre: ttk.Frame) -> None:
        caja = ttk.Labelframe(padre, text="Estadísticas generales", padding=8,
                             style="Seccion.TLabelframe")
        caja.pack(fill="x")

        self._stats_vars: dict[str, tk.StringVar] = {}
        items = [
            ("Estaciones", "estaciones_totales"),
            ("Activas", "estaciones_activas"),
            ("Finalizadas", "estaciones_finalizadas"),
            ("Mediciones", "mediciones_totales"),
            ("Alertas", "alertas_totales"),
        ]
        grid = ttk.Frame(caja)
        grid.pack(fill="x")
        for i, (titulo, clave) in enumerate(items):
            var = tk.StringVar(value="0")
            self._stats_vars[clave] = var
            celda = ttk.Frame(grid, padding=6)
            celda.grid(row=i // 2, column=i % 2, sticky="w", padx=4, pady=2)
            ttk.Label(celda, textvariable=var, style="StatVal.TLabel").pack(anchor="w")
            ttk.Label(celda, text=titulo, style="Stat.TLabel").pack(anchor="w")

    def _construir_alertas(self, padre: ttk.Frame) -> None:
        caja = ttk.Labelframe(padre, text="Alertas activas", padding=8,
                             style="Seccion.TLabelframe")
        caja.pack(fill="both", expand=True, pady=(10, 0))

        self._lista_alertas = tk.Listbox(caja, activestyle="none", height=8,
                                          highlightthickness=0, borderwidth=0)
        scroll = ttk.Scrollbar(caja, orient="vertical", command=self._lista_alertas.yview)
        self._lista_alertas.configure(yscrollcommand=scroll.set)
        self._lista_alertas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def _construir_entorno(self, padre: ttk.Frame) -> None:
        caja = ttk.Labelframe(padre, text="Entorno de ejecución", padding=8,
                             style="Seccion.TLabelframe")
        caja.pack(fill="x", pady=(10, 0))
        self._entorno_caja = caja

    def _construir_pie(self) -> None:
        ttk.Separator(self, orient="horizontal").pack(fill="x")
        pie = ttk.Frame(self, padding=(12, 6))
        pie.pack(fill="x")
        self._lbl_pie = ttk.Label(pie, text="Listo.", foreground="#777777")
        self._lbl_pie.pack(side="left")

    # -- Pintado de datos ---------------------------------------------------
    def _pintar_entorno(self) -> None:
        for clave, valor in _info_entorno().items():
            fila = ttk.Frame(self._entorno_caja)
            fila.pack(fill="x", pady=1)
            ttk.Label(fila, text=f"{clave}:").pack(side="left")
            ttk.Label(fila, text=valor, font=("TkDefaultFont", 9, "bold")).pack(side="right")

    def aplicar_snapshot(self, snap: SnapshotMonitoreo) -> None:
        """Vuelca un snapshot en los widgets. SÓLO se llama en el hilo de la GUI."""
        # Cabecera.
        self._lbl_modo.config(text=f"Modo: {snap.modo.value}")
        self._lbl_tiempo.config(text=f"Tiempo: {snap.tiempo_ejecucion_s:.1f} s")
        if snap.en_ejecucion:
            self._lbl_estado_motor.config(text="● En ejecución", foreground="#1b7f3b")
        else:
            self._lbl_estado_motor.config(text="● Detenido", foreground="#999999")

        # Tabla de estaciones (reconstrucción simple: el volumen es pequeño).
        self._tabla.delete(*self._tabla.get_children())
        for est in snap.estaciones:
            medicion = str(est.ultima_medicion) if est.ultima_medicion else "—"
            hora = est.ultima_medicion.instante.strftime("%H:%M:%S") if est.ultima_medicion else "—"
            self._tabla.insert(
                "", "end",
                values=(est.id, est.nombre, est.estado.value, medicion, hora),
                tags=(est.estado.name,),
            )

        # Estadísticas.
        e: Estadisticas = snap.estadisticas
        self._stats_vars["estaciones_totales"].set(str(e.estaciones_totales))
        self._stats_vars["estaciones_activas"].set(str(e.estaciones_activas))
        self._stats_vars["estaciones_finalizadas"].set(str(e.estaciones_finalizadas))
        self._stats_vars["mediciones_totales"].set(str(e.mediciones_totales))
        self._stats_vars["alertas_totales"].set(str(e.alertas_totales))

        # Alertas.
        self._lista_alertas.delete(0, "end")
        if not snap.alertas:
            self._lista_alertas.insert("end", "Sin alertas activas.")
            self._lista_alertas.itemconfig("end", foreground="#888888")
        else:
            colores = {"Alta": "#c0392b", "Media": "#b9770e", "Baja": "#7f8c8d"}
            for al in snap.alertas:
                hora = al.instante.strftime("%H:%M:%S")
                self._lista_alertas.insert("end", f"[{hora}] {al.estacion} — {al.mensaje}")
                self._lista_alertas.itemconfig("end", foreground=colores.get(al.severidad, "#333333"))

        self._lbl_pie.config(text=f"{len(snap.estaciones)} estaciones · {len(snap.alertas)} alertas activas")

    # -- Sondeo de la cola (hilo principal) ---------------------------------
    def _sondear_cola(self) -> None:
        """Drena la cola y pinta el último snapshot. Corre en el hilo de la GUI."""
        ultimo: SnapshotMonitoreo | None = None
        try:
            while True:
                ultimo = self._cola.get_nowait()  # type: ignore[union-attr]
        except queue.Empty:
            pass

        if ultimo is not None:
            self.aplicar_snapshot(ultimo)

        # Reprogramar el siguiente sondeo en el hilo principal.
        self.after(INTERVALO_REFRESCO_MS, self._sondear_cola)


# ---------------------------------------------------------------------------
# Datos de demostración (para ver la GUI sin un motor real)
# ---------------------------------------------------------------------------
def _snapshot_demo() -> SnapshotMonitoreo:
    """Construye un snapshot estático de ejemplo."""
    from datetime import datetime

    from userInterface.models import Medicion

    ahora = datetime.now()
    estaciones = [
        Estacion(1, "Centro Histórico", EstadoEstacion.PROCESANDO,
                 Medicion("PM2.5", 42.7, "µg/m³", ahora)),
        Estacion(2, "Av. Industrial", EstadoEstacion.ACTIVA,
                 Medicion("CO2", 612, "ppm", ahora)),
        Estacion(3, "Parque Norte", EstadoEstacion.ESPERANDO, None),
        Estacion(4, "Terminal Sur", EstadoEstacion.FINALIZADA,
                 Medicion("Temperatura", 24.3, "°C", ahora)),
        Estacion(5, "Zona Escolar", EstadoEstacion.ACTIVA,
                 Medicion("PM10", 88.1, "µg/m³", ahora)),
    ]
    alertas = [
        Alerta("Av. Industrial", "CO2 por encima del umbral (612 ppm)", "Alta", ahora),
        Alerta("Zona Escolar", "PM10 elevado (88 µg/m³)", "Media", ahora),
    ]
    stats = Estadisticas(
        estaciones_totales=len(estaciones),
        estaciones_activas=sum(e.estado == EstadoEstacion.ACTIVA for e in estaciones),
        estaciones_finalizadas=sum(e.estado == EstadoEstacion.FINALIZADA for e in estaciones),
        mediciones_totales=128,
        alertas_totales=len(alertas),
    )
    return SnapshotMonitoreo(
        estaciones=estaciones,
        alertas=alertas,
        estadisticas=stats,
        modo=ModoEjecucion.SECUENCIAL,
        tiempo_ejecucion_s=12.4,
        en_ejecucion=True,
    )


def main() -> None:
    """Lanza la GUI con un snapshot de demostración."""
    app = MonitoreoGUI()
    app.aplicar_snapshot(_snapshot_demo())
    app.mainloop()


if __name__ == "__main__":
    main()
