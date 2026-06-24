from __future__ import annotations

import multiprocessing
import platform
import queue
import sys
import sysconfig
import threading
import tkinter as tk
from tkinter import ttk

from monitoreo.controlador import ControladorMonitoreo
from monitoreo.dominio import (
    EstadoEstacion,
    ModoEjecucion,
    SnapshotMonitoreo,
)

INTERVALO_REFRESCO_MS = 150

COLOR_ESTADO = {
    EstadoEstacion.ACTIVA: "#1b7f3b",
    EstadoEstacion.ESPERANDO: "#8a6d00",
    EstadoEstacion.PROCESANDO: "#1f5fb0",
    EstadoEstacion.FINALIZADA: "#666666",
}
COLOR_SEVERIDAD = {"Alta": "#c0392b", "Media": "#b9770e", "Baja": "#7f8c8d"}

BG_PRINCIPAL = "#E8F2F6"
BG_PANEL = "#FFFFFF"
FG_TEXTO_PRINCIPAL = "#2C3E50"
FG_ACCENTO = "#154360"
FG_ALERTA_TEXTO = "#E74C3C"
BORDER_COLOR = "#D6EAF8"


def _estado_gil() -> str:
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


class MonitoreoGUI(tk.Tk):

    def __init__(self, ciclos: int = 12, carga_cpu: int = 600, estaciones: int = 6) -> None:
        super().__init__()
        self._ciclos = ciclos
        self._carga = carga_cpu
        self._estaciones = estaciones

        self._cola: "queue.Queue[SnapshotMonitoreo]" = queue.Queue()
        self._controlador: ControladorMonitoreo | None = None
        self._hilo: threading.Thread | None = None

        self.title("Sistema de Monitoreo Ambiental Urbano — Cuenca")
        self.geometry("1100x720")
        self.minsize(960, 640)

        self._configurar_estilos()
        self._construir_cabecera()
        self._construir_cuerpo()
        self._construir_pie()
        self._pintar_entorno()

        self.protocol("WM_DELETE_WINDOW", self._al_cerrar)
        self.after(INTERVALO_REFRESCO_MS, self._sondear_cola)

    def _configurar_estilos(self) -> None:
        estilo = ttk.Style(self)
        try:
            estilo.theme_use("clam")
        except tk.TclError:
            pass

        self.configure(bg=BG_PRINCIPAL)

        estilo.configure("TFrame", background=BG_PRINCIPAL)

        estilo.configure("Seccion.TLabelframe", background=BG_PANEL, relief="flat", borderwidth=1, bordercolor=BORDER_COLOR)
        estilo.configure("Seccion.TLabelframe.Label", font=("TkDefaultFont", 12, "bold"), background=BG_PANEL, foreground=FG_ACCENTO)

        estilo.configure("TLabel", background=BG_PRINCIPAL, foreground=FG_TEXTO_PRINCIPAL)
        estilo.configure("Titulo.TLabel", font=("TkDefaultFont", 17, "bold"), foreground=FG_ACCENTO)

        estilo.configure("Stat.TLabel", font=("TkDefaultFont", 9), background=BG_PANEL, foreground="#7F8C8D")
        estilo.configure("StatVal.TLabel", font=("TkDefaultFont", 18, "bold"), background=BG_PANEL, foreground=FG_TEXTO_PRINCIPAL)

        estilo.configure("Treeview", rowheight=28, background=BG_PANEL, fieldbackground=BG_PANEL, borderwidth=0)
        estilo.configure("Treeview.Heading", font=("TkDefaultFont", 10, "bold"), background="#D6EAF8", foreground=FG_TEXTO_PRINCIPAL, relief="flat")
        estilo.map("Treeview.Heading", background=[('active', '#AED6F1')])

    def _construir_cabecera(self) -> None:
        barra = ttk.Frame(self, padding=(12, 10))
        barra.pack(fill="x")

        ttk.Label(barra, text="🌆 Monitoreo Ambiental — Cuenca",
                  style="Titulo.TLabel").pack(side="left")

        ttk.Label(barra, text="Modo:").pack(side="left", padx=(24, 4))
        self._combo_modo = ttk.Combobox(
            barra, state="readonly", width=12,
            values=[m.value for m in ModoEjecucion],
        )
        self._combo_modo.current(0)
        self._combo_modo.pack(side="left")

        ttk.Label(barra, text="Estaciones:").pack(side="left", padx=(12, 4))
        self._spin_estaciones = ttk.Spinbox(barra, from_=4, to=12, width=4)
        self._spin_estaciones.set(str(self._estaciones))
        self._spin_estaciones.pack(side="left")

        ttk.Label(barra, text="Ciclos:").pack(side="left", padx=(12, 4))
        self._spin_ciclos = ttk.Spinbox(barra, from_=10, to=30, width=4)
        self._spin_ciclos.set(str(self._ciclos))
        self._spin_ciclos.pack(side="left")

        self._btn_iniciar = ttk.Button(barra, text="▶ Iniciar", command=self._iniciar)
        self._btn_iniciar.pack(side="left", padx=(10, 4))
        self._btn_detener = ttk.Button(
            barra, text="■ Detener", command=self._detener, state="disabled"
        )
        self._btn_detener.pack(side="left")

        self._lbl_estado_motor = ttk.Label(barra, text="● Detenido", foreground="#999999")
        self._lbl_estado_motor.pack(side="right")

        ttk.Separator(self, orient="horizontal").pack(fill="x")

        info = ttk.Frame(self, padding=(12, 6))
        info.pack(fill="x")
        self._lbl_modo = ttk.Label(info, text="Modo activo: —")
        self._lbl_modo.pack(side="left")
        self._lbl_ciclo = ttk.Label(info, text="Ciclo: 0 / 0")
        self._lbl_ciclo.pack(side="left", padx=24)
        self._lbl_tiempo = ttk.Label(info, text="Tiempo: 0.000 s")
        self._lbl_tiempo.pack(side="left")
        ttk.Separator(self, orient="horizontal").pack(fill="x")

    def _construir_cuerpo(self) -> None:
        cuerpo = ttk.Frame(self, padding=12)
        cuerpo.pack(fill="both", expand=True)

        izq = ttk.Labelframe(cuerpo, text="Estaciones ambientales", padding=8,
                             style="Seccion.TLabelframe")
        izq.pack(side="left", fill="both", expand=True)

        columnas = ("id", "nombre", "zona", "estado", "medicion", "hora")
        self._tabla = ttk.Treeview(izq, columns=columnas, show="headings", selectmode="browse")
        for col, texto, ancho, anchor in (
            ("id", "ID", 36, "center"),
            ("nombre", "Estación", 150, "w"),
            ("zona", "Zona", 150, "w"),
            ("estado", "Estado", 100, "center"),
            ("medicion", "Última medición", 170, "w"),
            ("hora", "Hora", 80, "center"),
        ):
            self._tabla.heading(col, text=texto)
            self._tabla.column(col, width=ancho, anchor=anchor)
        for estado, color in COLOR_ESTADO.items():
            self._tabla.tag_configure(estado.name, foreground=color)
        scroll = ttk.Scrollbar(izq, orient="vertical", command=self._tabla.yview)
        self._tabla.configure(yscrollcommand=scroll.set)
        self._tabla.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        der = ttk.Frame(cuerpo)
        der.pack(side="right", fill="both", padx=(12, 0))

        self._construir_estadisticas(der)
        self._construir_por_variable(der)
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
            ("Mediciones", "mediciones_procesadas"),
            ("Alertas", "alertas_generadas"),
            ("Prom/ciclo (s)", "tiempo_promedio_ciclo_s"),
        ]
        grid = ttk.Frame(caja)
        grid.pack(fill="x", expand=True, pady=(5))

        for col in range(3):
            grid.columnconfigure(col, weight=1)

        for i, (titulo, clave) in enumerate(items):
            var = tk.StringVar(value="0")
            self._stats_vars[clave] = var
            celda = ttk.Frame(grid, padding=5)
            celda.grid(row=i // 3, column=i % 3, sticky="nsew", padx=5, pady=5)

            ttk.Label(celda, textvariable=var, style="StatVal.TLabel", anchor="center").pack(fill="x")
            ttk.Label(celda, text=titulo, style="Stat.TLabel", anchor="center").pack(fill="x")

        fila = ttk.Frame(caja)
        fila.pack(fill="x", pady=(10, 0))
        ttk.Label(fila, text="Zona de mayor riesgo:").pack(side="left")
        self._lbl_zona = ttk.Label(fila, text="—", font=("TkDefaultFont", 10, "bold"),
                                   foreground="#c0392b")
        self._lbl_zona.pack(side="left", padx=6)

    def _construir_por_variable(self, padre: ttk.Frame) -> None:
        caja = ttk.Labelframe(padre, text="Por variable (prom / mín / máx)", padding=8,
                             style="Seccion.TLabelframe")
        caja.pack(fill="x", pady=(10, 0))
        cols = ("variable", "prom", "min", "max")
        self._tabla_var = ttk.Treeview(caja, columns=cols, show="headings", height=6)
        for col, texto, ancho in (
            ("variable", "Variable", 110),
            ("prom", "Prom.", 70),
            ("min", "Mín.", 60),
            ("max", "Máx.", 60),
        ):
            self._tabla_var.heading(col, text=texto)
            self._tabla_var.column(col, width=ancho, anchor="center")
        self._tabla_var.pack(fill="x")

    def _construir_alertas(self, padre: ttk.Frame) -> None:
        caja = ttk.Labelframe(padre, text="Alertas activas", padding=8,
                             style="Seccion.TLabelframe")
        caja.pack(fill="both", expand=True, pady=(10, 0))

        self._texto_alertas = tk.Text(caja, height=6, wrap="word",
                                      highlightthickness=0, borderwidth=0,
                                      font=("TkDefaultFont", 9),
                                      background=BG_PANEL, foreground=FG_TEXTO_PRINCIPAL,
                                      state="disabled")

        scroll = ttk.Scrollbar(caja, orient="vertical", command=self._texto_alertas.yview)
        self._texto_alertas.configure(yscrollcommand=scroll.set)

        self._texto_alertas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self._texto_alertas.tag_config("Alta", foreground=COLOR_SEVERIDAD["Alta"], font=("TkDefaultFont", 9, "bold"))
        self._texto_alertas.tag_config("Media", foreground=COLOR_SEVERIDAD["Media"])
        self._texto_alertas.tag_config("Baja", foreground=COLOR_SEVERIDAD["Baja"])
        self._texto_alertas.tag_config("SinAlertas", foreground="#BDC3C7")

    def _construir_entorno(self, padre: ttk.Frame) -> None:
        self._entorno_caja = ttk.Labelframe(padre, text="Entorno de ejecución", padding=8,
                                            style="Seccion.TLabelframe")
        self._entorno_caja.pack(fill="x", pady=(10, 0))

    def _construir_pie(self) -> None:
        ttk.Separator(self, orient="horizontal").pack(fill="x")
        pie = ttk.Frame(self, padding=(12, 6))
        pie.pack(fill="x")
        self._lbl_pie = ttk.Label(pie, text="Listo. Elige un modo y pulsa Iniciar.",
                                  foreground="#777777")
        self._lbl_pie.pack(side="left")

    def _pintar_entorno(self) -> None:
        for clave, valor in _info_entorno().items():
            fila = ttk.Frame(self._entorno_caja)
            fila.pack(fill="x", pady=1)
            ttk.Label(fila, text=f"{clave}:").pack(side="left")
            ttk.Label(fila, text=valor, font=("TkDefaultFont", 9, "bold")).pack(side="right")

    def _iniciar(self) -> None:
        if self._hilo and self._hilo.is_alive():
            return
        modo = ModoEjecucion(self._combo_modo.get())
        try:
            n_est = max(4, int(self._spin_estaciones.get()))
            n_ciclos = max(10, int(self._spin_ciclos.get()))
        except (TypeError, ValueError):
            n_est, n_ciclos = self._estaciones, self._ciclos
        self._controlador = ControladorMonitoreo(
            ciclos=n_ciclos, carga_cpu=self._carga, n_estaciones=n_est
        )

        def trabajo() -> None:
            self._controlador.ejecutar(modo, publicar=self._cola.put)

        self._hilo = threading.Thread(target=trabajo, name="simulacion", daemon=True)
        self._btn_iniciar.config(state="disabled")
        self._btn_detener.config(state="normal")
        self._combo_modo.config(state="disabled")
        self._spin_estaciones.config(state="disabled")
        self._spin_ciclos.config(state="disabled")
        self._lbl_pie.config(text=f"Ejecutando en modo {modo.value}…")
        self._hilo.start()

    def _detener(self) -> None:
        if self._controlador is not None:
            self._controlador.detener()
            self._lbl_pie.config(text="Deteniendo…")

    def _al_cerrar(self) -> None:
        if self._controlador is not None:
            self._controlador.detener()
        self.destroy()

    def _sondear_cola(self) -> None:
        ultimo: SnapshotMonitoreo | None = None
        try:
            while True:
                ultimo = self._cola.get_nowait()
        except queue.Empty:
            pass
        if ultimo is not None:
            self.aplicar_snapshot(ultimo)
            if not ultimo.en_ejecucion and not (self._hilo and self._hilo.is_alive()):
                self._btn_iniciar.config(state="normal")
                self._btn_detener.config(state="disabled")
                self._combo_modo.config(state="readonly")
                self._spin_estaciones.config(state="normal")
                self._spin_ciclos.config(state="normal")
        self.after(INTERVALO_REFRESCO_MS, self._sondear_cola)

    def aplicar_snapshot(self, snap: SnapshotMonitoreo) -> None:
        self._lbl_modo.config(text=f"Modo activo: {snap.modo.value}")
        self._lbl_ciclo.config(text=f"Ciclo: {snap.ciclo_actual} / {snap.ciclos_totales}")
        self._lbl_tiempo.config(text=f"Tiempo: {snap.tiempo_ejecucion_s:.3f} s")
        if snap.en_ejecucion:
            self._lbl_estado_motor.config(text="● En ejecución", foreground="#1b7f3b")
        else:
            self._lbl_estado_motor.config(text="● Detenido", foreground="#999999")

        self._tabla.delete(*self._tabla.get_children())
        for est in snap.estaciones:
            med = str(est.ultima_medicion) if est.ultima_medicion else "—"
            hora = est.ultima_medicion.instante.strftime("%H:%M:%S") if est.ultima_medicion else "—"
            self._tabla.insert(
                "", "end",
                values=(est.id, est.nombre, est.zona, est.estado.value, med, hora),
                tags=(est.estado.name,),
            )

        e = snap.estadisticas
        self._stats_vars["estaciones_totales"].set(str(e.estaciones_totales))
        self._stats_vars["estaciones_activas"].set(str(e.estaciones_activas))
        self._stats_vars["estaciones_finalizadas"].set(str(e.estaciones_finalizadas))
        self._stats_vars["mediciones_procesadas"].set(str(e.mediciones_procesadas))
        self._stats_vars["alertas_generadas"].set(str(e.alertas_generadas))
        self._stats_vars["tiempo_promedio_ciclo_s"].set(f"{e.tiempo_promedio_ciclo_s:.4f}")
        self._lbl_zona.config(text=e.zona_mayor_riesgo)

        self._tabla_var.delete(*self._tabla_var.get_children())
        for var, ev in e.por_variable.items():
            self._tabla_var.insert(
                "", "end",
                values=(var.etiqueta, f"{ev.promedio:.1f}", f"{ev.minimo:.1f}", f"{ev.maximo:.1f}"),
            )

        self._texto_alertas.config(state="normal")
        self._texto_alertas.delete(1.0, "end")

        if not snap.alertas:
            self._texto_alertas.insert("end", "Sin alertas activas.\n", "SinAlertas")
        else:
            for al in reversed(snap.alertas):
                hora = al.instante.strftime("%H:%M:%S")
                mensaje = f"[{hora}] {al.zona} — {al.mensaje} ({al.severidad})\n"

                self._texto_alertas.insert("end", mensaje, al.severidad)

        self._texto_alertas.config(state="disabled")


def main() -> None:
    app = MonitoreoGUI()
    app.mainloop()

if __name__ == "__main__":
    main()
