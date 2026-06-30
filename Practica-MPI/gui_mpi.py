from __future__ import annotations

import argparse
import platform

from mpi4py import MPI

from analizador import AnalizadorDatos
from config import crear_estacion

CMD_TERMINAR = "__TERMINAR__"
TAG_ASIGNACION = 11
CARGA = 600

COLOR_SEVERIDAD = {"Alta": "#c0392b", "Media": "#b9770e", "Baja": "#7f8c8d"}
BG_PRINCIPAL = "#E8F2F6"
BG_PANEL = "#FFFFFF"
FG_TEXTO_PRINCIPAL = "#2C3E50"
FG_ACCENTO = "#154360"
BORDER_COLOR = "#D6EAF8"
COLOR_PROCESO = ["#1f5fb0", "#1b7f3b", "#b9770e", "#8e44ad", "#16a085", "#c0392b"]


def repartir(total: int, partes: int) -> list[list[int]]:
    a: list[list[int]] = [[] for _ in range(partes)]
    for i in range(total):
        a[i % partes].append(i)
    return a


def worker_loop(comm, rank: int, size: int) -> None:
    while True:
        cmd = comm.bcast(None, root=0)
        if cmd == CMD_TERMINAR:
            return
        n_est, ciclos, carga = cmd
        indices = comm.recv(source=0, tag=TAG_ASIGNACION)
        estaciones = [crear_estacion(i) for i in indices]
        acc = []
        for ciclo in range(ciclos):
            for est in estaciones:
                acc.extend(est.trabajar_ciclo(ciclo, carga, rank))
            comm.gather(AnalizadorDatos.resumen_local(acc, rank), root=0)


def coordinador_run(comm, size, n_est, ciclos, carga, on_cycle) -> tuple[float, list[int]]:
    comm.bcast((n_est, ciclos, carga), root=0)
    asign = repartir(n_est, size)
    for r in range(1, size):
        comm.send(asign[r], dest=r, tag=TAG_ASIGNACION)
    estaciones = [crear_estacion(i) for i in asign[0]]
    acc = []
    t0 = MPI.Wtime()
    for ciclo in range(ciclos):
        for est in estaciones:
            acc.extend(est.trabajar_ciclo(ciclo, carga, 0))
        resumenes = comm.gather(AnalizadorDatos.resumen_local(acc, 0), root=0)
        stats = AnalizadorDatos.consolidar(resumenes)
        on_cycle(ciclo + 1, ciclos, stats, MPI.Wtime() - t0)
    return MPI.Wtime() - t0, [len(x) for x in asign]


def terminar(comm) -> None:
    comm.bcast(CMD_TERMINAR, root=0)


def lanzar_gui(comm, size: int, estaciones: int, ciclos: int) -> None:
    import tkinter as tk
    from tkinter import ttk

    version_mpi = MPI.Get_library_version().replace("\x00", "").splitlines()[0]

    class GUIMPI(tk.Tk):
        def __init__(self) -> None:
            super().__init__()
            self.title("Sistema de Monitoreo Ambiental Urbano — MPI (Cuenca)")
            self.geometry("1180x720")
            self.minsize(1000, 640)
            self._ejecutando = False
            self._configurar_estilos()
            self._construir_cabecera()
            self._construir_cuerpo()
            self._construir_pie()
            self._pintar_entorno()
            self._pintar_roster(int(self._spin_est.get()))
            self.protocol("WM_DELETE_WINDOW", self._cerrar)

        def _configurar_estilos(self) -> None:
            estilo = ttk.Style(self)
            try:
                estilo.theme_use("clam")
            except tk.TclError:
                pass
            self.configure(bg=BG_PRINCIPAL)
            estilo.configure("TFrame", background=BG_PRINCIPAL)
            estilo.configure("Seccion.TLabelframe", background=BG_PANEL, relief="flat",
                             borderwidth=1, bordercolor=BORDER_COLOR)
            estilo.configure("Seccion.TLabelframe.Label", font=("TkDefaultFont", 12, "bold"),
                             background=BG_PANEL, foreground=FG_ACCENTO)
            estilo.configure("TLabel", background=BG_PRINCIPAL, foreground=FG_TEXTO_PRINCIPAL)
            estilo.configure("Titulo.TLabel", font=("TkDefaultFont", 17, "bold"), foreground=FG_ACCENTO)
            estilo.configure("Stat.TLabel", font=("TkDefaultFont", 9), background=BG_PANEL, foreground="#7F8C8D")
            estilo.configure("StatVal.TLabel", font=("TkDefaultFont", 18, "bold"),
                             background=BG_PANEL, foreground=FG_TEXTO_PRINCIPAL)
            estilo.configure("Treeview", rowheight=28, background=BG_PANEL,
                             fieldbackground=BG_PANEL, borderwidth=0)
            estilo.configure("Treeview.Heading", font=("TkDefaultFont", 10, "bold"),
                             background="#D6EAF8", foreground=FG_TEXTO_PRINCIPAL, relief="flat")
            estilo.map("Treeview.Heading", background=[("active", "#AED6F1")])

        def _construir_cabecera(self) -> None:
            barra = ttk.Frame(self, padding=(12, 10))
            barra.pack(fill="x")
            ttk.Label(barra, text="🌆 Monitoreo Ambiental — MPI", style="Titulo.TLabel").pack(side="left")

            ttk.Label(barra, text="Estaciones:").pack(side="left", padx=(24, 4))
            self._spin_est = ttk.Spinbox(barra, from_=size, to=24, width=4)
            self._spin_est.set(str(max(estaciones, size)))
            self._spin_est.pack(side="left")
            ttk.Label(barra, text="Ciclos:").pack(side="left", padx=(12, 4))
            self._spin_cic = ttk.Spinbox(barra, from_=10, to=40, width=4)
            self._spin_cic.set(str(ciclos))
            self._spin_cic.pack(side="left")

            self._btn = ttk.Button(barra, text="▶ Iniciar", command=self._iniciar)
            self._btn.pack(side="left", padx=(10, 4))
            self._lbl_motor = ttk.Label(barra, text="● Detenido", foreground="#999999")
            self._lbl_motor.pack(side="right")

            ttk.Separator(self, orient="horizontal").pack(fill="x")
            info = ttk.Frame(self, padding=(12, 6))
            info.pack(fill="x")
            self._lbl_modo = ttk.Label(info, text=f"Modo activo: MPI ({size} procesos)")
            self._lbl_modo.pack(side="left")
            self._lbl_ciclo = ttk.Label(info, text="Ciclo: 0 / 0")
            self._lbl_ciclo.pack(side="left", padx=24)
            self._lbl_tiempo = ttk.Label(info, text="Tiempo: 0.000 s")
            self._lbl_tiempo.pack(side="left")
            ttk.Separator(self, orient="horizontal").pack(fill="x")

        def _construir_cuerpo(self) -> None:
            cuerpo = ttk.Frame(self, padding=12)
            cuerpo.pack(fill="both", expand=True)

            izq = ttk.Labelframe(cuerpo, text="Estaciones ambientales (proceso MPI asignado)",
                                 padding=8, style="Seccion.TLabelframe")
            izq.pack(side="left", fill="both", expand=True)
            columnas = ("id", "nombre", "zona", "proc", "medicion", "hora")
            self._tabla = ttk.Treeview(izq, columns=columnas, show="headings", selectmode="browse")
            for col, texto, ancho, anchor in (
                ("id", "ID", 36, "center"),
                ("nombre", "Estación", 150, "w"),
                ("zona", "Zona", 150, "w"),
                ("proc", "Proceso MPI", 95, "center"),
                ("medicion", "Última medición", 180, "w"),
                ("hora", "Hora", 80, "center"),
            ):
                self._tabla.heading(col, text=texto)
                self._tabla.column(col, width=ancho, anchor=anchor)
            for i, color in enumerate(COLOR_PROCESO):
                self._tabla.tag_configure(f"P{i}", foreground=color)
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

        def _construir_estadisticas(self, padre) -> None:
            caja = ttk.Labelframe(padre, text="Estadísticas globales", padding=8, style="Seccion.TLabelframe")
            caja.pack(fill="x")
            self._stats: dict[str, tk.StringVar] = {}
            items = [("Estaciones", "estaciones"), ("Procesos MPI", "procesos"),
                     ("Mediciones", "med"), ("Alertas", "ale"),
                     ("Aceleramiento", "speedup"), ("Tiempo (s)", "tiempo")]
            grid = ttk.Frame(caja)
            grid.pack(fill="x", expand=True, pady=5)
            for col in range(3):
                grid.columnconfigure(col, weight=1)
            for i, (titulo, clave) in enumerate(items):
                var = tk.StringVar(value="—")
                self._stats[clave] = var
                celda = ttk.Frame(grid, padding=5)
                celda.grid(row=i // 3, column=i % 3, sticky="nsew", padx=5, pady=5)
                ttk.Label(celda, textvariable=var, style="StatVal.TLabel", anchor="center").pack(fill="x")
                ttk.Label(celda, text=titulo, style="Stat.TLabel", anchor="center").pack(fill="x")
            fila = ttk.Frame(caja)
            fila.pack(fill="x", pady=(10, 0))
            ttk.Label(fila, text="Zona de mayor riesgo:").pack(side="left")
            self._lbl_zona = ttk.Label(fila, text="—", font=("TkDefaultFont", 10, "bold"), foreground="#c0392b")
            self._lbl_zona.pack(side="left", padx=6)

        def _construir_por_variable(self, padre) -> None:
            caja = ttk.Labelframe(padre, text="Por variable (prom / mín / máx)", padding=8,
                                  style="Seccion.TLabelframe")
            caja.pack(fill="x", pady=(10, 0))
            cols = ("variable", "prom", "min", "max")
            self._tabla_var = ttk.Treeview(caja, columns=cols, show="headings", height=6)
            for col, texto, ancho in (("variable", "Variable", 110), ("prom", "Prom.", 70),
                                      ("min", "Mín.", 60), ("max", "Máx.", 60)):
                self._tabla_var.heading(col, text=texto)
                self._tabla_var.column(col, width=ancho, anchor="center")
            self._tabla_var.pack(fill="x")

        def _construir_alertas(self, padre) -> None:
            caja = ttk.Labelframe(padre, text="Alertas activas", padding=8, style="Seccion.TLabelframe")
            caja.pack(fill="both", expand=True, pady=(10, 0))
            self._texto_alertas = tk.Text(caja, height=6, wrap="word", highlightthickness=0,
                                          borderwidth=0, font=("TkDefaultFont", 9),
                                          background=BG_PANEL, foreground=FG_TEXTO_PRINCIPAL, state="disabled")
            scroll = ttk.Scrollbar(caja, orient="vertical", command=self._texto_alertas.yview)
            self._texto_alertas.configure(yscrollcommand=scroll.set)
            self._texto_alertas.pack(side="left", fill="both", expand=True)
            scroll.pack(side="right", fill="y")
            for sev, color in COLOR_SEVERIDAD.items():
                self._texto_alertas.tag_config(sev, foreground=color)
            self._texto_alertas.tag_config("SinAlertas", foreground="#BDC3C7")

        def _construir_entorno(self, padre) -> None:
            self._entorno = ttk.Labelframe(padre, text="Entorno de ejecución", padding=8,
                                           style="Seccion.TLabelframe")
            self._entorno.pack(fill="x", pady=(10, 0))

        def _construir_pie(self) -> None:
            ttk.Separator(self, orient="horizontal").pack(fill="x")
            pie = ttk.Frame(self, padding=(12, 6))
            pie.pack(fill="x")
            self._lbl_pie = ttk.Label(pie, text="Listo. Pulsa Iniciar para lanzar la simulación distribuida.",
                                      foreground="#777777")
            self._lbl_pie.pack(side="left")

        def _pintar_entorno(self) -> None:
            datos = {
                "Versión de Python": platform.python_version(),
                "Sistema operativo": f"{platform.system()} {platform.release()}",
                "Procesos MPI (size)": str(size),
                "Librería MPI": version_mpi[:34],
            }
            for clave, valor in datos.items():
                fila = ttk.Frame(self._entorno)
                fila.pack(fill="x", pady=1)
                ttk.Label(fila, text=f"{clave}:").pack(side="left")
                ttk.Label(fila, text=valor, font=("TkDefaultFont", 9, "bold")).pack(side="right")

        def _pintar_roster(self, n_est: int) -> None:
            self._tabla.delete(*self._tabla.get_children())
            for i in range(n_est):
                e = crear_estacion(i)
                p = i % size
                self._tabla.insert("", "end", iid=e.nombre,
                                   values=(e.id, e.nombre, e.zona, f"P{p}", "—", "—"),
                                   tags=(f"P{p % len(COLOR_PROCESO)}",))
            self._stats["estaciones"].set(str(n_est))
            self._stats["procesos"].set(str(size))

        def _iniciar(self) -> None:
            if self._ejecutando:
                return
            self._ejecutando = True
            self._btn.config(state="disabled")
            self._spin_est.config(state="disabled")
            self._spin_cic.config(state="disabled")
            self._lbl_motor.config(text="● En ejecución", foreground="#1b7f3b")
            n_est = max(size, int(self._spin_est.get()))
            ciclos = max(10, int(self._spin_cic.get()))
            self._pintar_roster(n_est)
            self._lbl_pie.config(text="Ejecutando simulación distribuida con MPI…")
            tiempo, reparto = coordinador_run(comm, size, n_est, ciclos, CARGA, self._on_cycle)
            self._lbl_motor.config(text="● Detenido", foreground="#999999")
            self._lbl_pie.config(text=f"Completado en {tiempo:.3f} s · reparto de estaciones por proceso: {reparto}")
            self._btn.config(state="normal")
            self._spin_est.config(state="normal")
            self._spin_cic.config(state="normal")
            self._ejecutando = False

        def _on_cycle(self, ciclo: int, total: int, stats: dict, t: float) -> None:
            self._lbl_ciclo.config(text=f"Ciclo: {ciclo} / {total}")
            self._lbl_tiempo.config(text=f"Tiempo: {t:.3f} s")
            self._stats["med"].set(str(stats["mediciones_procesadas"]))
            self._stats["ale"].set(str(stats["alertas_generadas"]))
            self._stats["tiempo"].set(f"{t:.2f}")
            self._stats["speedup"].set(f"{len(stats['procesos'])} proc")
            self._lbl_zona.config(text=stats["zona_mayor_riesgo"])

            for nombre, u in stats.get("ultimas", {}).items():
                if self._tabla.exists(nombre):
                    vals = list(self._tabla.item(nombre, "values"))
                    vals[4] = u["texto"]
                    vals[5] = u.get("hora", "—")
                    self._tabla.item(nombre, values=vals)

            self._tabla_var.delete(*self._tabla_var.get_children())
            for var, d in stats.get("por_variable", {}).items():
                self._tabla_var.insert("", "end", values=(
                    var, f"{d['promedio']:.1f}", f"{d['min']:.1f}", f"{d['max']:.1f}"))

            self._texto_alertas.config(state="normal")
            self._texto_alertas.delete(1.0, "end")
            alertas = stats.get("alertas", [])
            if not alertas:
                self._texto_alertas.insert("end", "Sin alertas activas.\n", "SinAlertas")
            else:
                for a in reversed(alertas):
                    msg = f"[P{a['proceso']}] {a['zona']} — {a['variable']} {a['valor']:.1f} ({a['severidad']})\n"
                    self._texto_alertas.insert("end", msg, a["severidad"])
            self._texto_alertas.config(state="disabled")
            self.update()

        def _cerrar(self) -> None:
            terminar(comm)
            self.destroy()

    GUIMPI().mainloop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitoreo ambiental — GUI + MPI")
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--estaciones", type=int, default=8)
    parser.add_argument("--ciclos", type=int, default=20)
    args = parser.parse_args()

    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()

    if args.selftest:
        if rank == 0:
            def on_cycle(c, total, stats, t):
                if c == 1 or c == total:
                    print(f"[rank0] ciclo {c}/{total}  med={stats['mediciones_procesadas']}  "
                          f"alertas={stats['alertas_generadas']}  procesos={stats['procesos']}  t={t:.3f}s")
            coordinador_run(comm, size, args.estaciones, args.ciclos, CARGA, on_cycle)
            terminar(comm)
        else:
            worker_loop(comm, rank, size)
        return

    if rank == 0:
        lanzar_gui(comm, size, args.estaciones, args.ciclos)
    else:
        worker_loop(comm, rank, size)


if __name__ == "__main__":
    main()
