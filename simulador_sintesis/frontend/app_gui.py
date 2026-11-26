import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
import customtkinter as ctk

from backend.services.compiler_service import CompilerSynthesisService


class SynthesisSimulatorApp(ctk.CTk):
    def __init__(self, initial_file: Path | None = None):
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Simulador Etapa de Síntesis - Lenguajes y Autómatas II (Versión 1)")
        self.geometry("1420x830")
        self.minsize(1160, 700)

        self.service = CompilerSynthesisService()
        self.selected_mode = tk.StringVar(value=CompilerSynthesisService.MODE_CUADRUPLOS)
        self._debounce_job = None

        self._configure_treeview_style()
        self._build_ui()

        if initial_file and initial_file.exists():
            content = initial_file.read_text(encoding="utf-8")
            self.code_editor.insert("1.0", content)

        self._update_line_numbers()
        self._run_synthesis()

    def _configure_treeview_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Custom.Treeview",
            background="#1e222a",
            foreground="#e6edf3",
            fieldbackground="#1e222a",
            rowheight=28,
            font=("Consolas", 11),
            borderwidth=0,
        )
        style.configure(
            "Custom.Treeview.Heading",
            background="#2b313c",
            foreground="#ffffff",
            font=("Segoe UI", 11, "bold"),
            relief="flat",
        )
        style.map("Custom.Treeview", background=[("selected", "#1f6feb")])

    def _build_ui(self):
        # --- BARRA SUPERIOR ---
        top_bar = ctk.CTkFrame(self, corner_radius=8)
        top_bar.pack(fill="x", padx=12, pady=(12, 6))

        btn_load = ctk.CTkButton(
            top_bar,
            text="Cargar archivo (.java / .txt)",
            command=self._load_file,
            width=210,
            font=("Segoe UI", 12, "bold"),
        )
        btn_load.pack(side="left", padx=10, pady=10)

        mode_label = ctk.CTkLabel(top_bar, text="Código Intermedio:", font=("Segoe UI", 12, "bold"))
        mode_label.pack(side="left", padx=(14, 6))

        modes = [
            ("Cuádruplos", CompilerSynthesisService.MODE_CUADRUPLOS),
            ("Triplos", CompilerSynthesisService.MODE_TRIPLOS),
            ("Tres Direcciones (1 ≤ n ≤ 3)", CompilerSynthesisService.MODE_TRES_DIRECCIONES),
        ]
        for label_text, mode_val in modes:
            rb = ctk.CTkRadioButton(
                top_bar,
                text=label_text,
                variable=self.selected_mode,
                value=mode_val,
                command=self._on_mode_changed,
                font=("Segoe UI", 12),
            )
            rb.pack(side="left", padx=10)

        # Banner de validación
        self.status_label = ctk.CTkLabel(
            self,
            text="Validando código...",
            anchor="w",
            corner_radius=6,
            height=34,
            padx=12,
            font=("Segoe UI", 12, "bold"),
        )
        self.status_label.pack(fill="x", padx=12, pady=(0, 8))

        # --- CONTENEDOR PRINCIPAL ---
        main_pane = ctk.CTkFrame(self, fg_color="transparent")
        main_pane.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        main_pane.grid_columnconfigure(0, weight=4)
        main_pane.grid_columnconfigure(1, weight=6)
        main_pane.grid_rowconfigure(0, weight=1)

        # PANEL IZQUIERDO: Editor con números de línea + Tabla de Símbolos (IDs)
        left_frame = ctk.CTkFrame(main_pane, corner_radius=8)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        left_frame.grid_rowconfigure(1, weight=3)
        left_frame.grid_rowconfigure(3, weight=2)
        left_frame.grid_columnconfigure(0, weight=1)

        editor_header = ctk.CTkLabel(
            left_frame,
            text="1. Código Fuente Java Depurado (Líneas y Edición en Vivo)",
            font=("Segoe UI", 13, "bold"),
            anchor="w",
        )
        editor_header.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 6))

        # Contenedor Editor + Gutter de números de línea
        editor_container = tk.Frame(left_frame, bg="#181b20", bd=0)
        editor_container.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))

        self.line_numbers = tk.Text(
            editor_container,
            width=4,
            padx=6,
            pady=8,
            takefocus=0,
            border=0,
            background="#161920",
            foreground="#6e7681",
            font=("Consolas", 13),
            state="disabled",
            wrap="none",
        )
        self.line_numbers.pack(side="left", fill="y")

        self.code_editor = ctk.CTkTextbox(
            editor_container,
            font=("Consolas", 13),
            wrap="none",
            undo=True,
            corner_radius=0,
        )
        self.code_editor.pack(side="left", fill="both", expand=True)

        # Sincronizar scroll y eventos del editor con los números de línea
        self._raw_text: tk.Text = self.code_editor._textbox
        self._raw_text.configure(pady=8, yscrollcommand=self._on_text_scroll)
        self._raw_text.tag_configure("error_line", background="#491d21")
        self.line_numbers.tag_configure("error_num", background="#491d21", foreground="#ff7b72")

        self._raw_text.bind("<KeyRelease>", self._on_code_edited)
        self._raw_text.bind("<ButtonRelease-1>", lambda _e: self._update_line_numbers())
        self._raw_text.bind("<MouseWheel>", lambda _e: self.after(5, self._update_line_numbers))
        self._raw_text.bind("<Configure>", lambda _e: self._update_line_numbers())

        # Tabla de Símbolos (ID1, ID2...) con Ámbito Global vs Local
        sym_header = ctk.CTkLabel(
            left_frame,
            text="Tabla de Símbolos (IDs y Ámbito Global / Local)",
            font=("Segoe UI", 12, "bold"),
            anchor="w",
        )
        sym_header.grid(row=2, column=0, sticky="ew", padx=12, pady=(2, 4))

        sym_wrap = tk.Frame(left_frame, bg="#1e222a")
        sym_wrap.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))

        self.sym_tree = ttk.Treeview(
            sym_wrap,
            columns=("id", "lexema", "tipo", "ambito"),
            show="headings",
            style="Custom.Treeview",
        )
        self.sym_tree.heading("id", text="ID")
        self.sym_tree.heading("lexema", text="Lexema")
        self.sym_tree.heading("tipo", text="Tipo")
        self.sym_tree.heading("ambito", text="Ámbito")

        self.sym_tree.column("id", width=65, anchor="center", stretch=False)
        self.sym_tree.column("lexema", width=130, anchor="w")
        self.sym_tree.column("tipo", width=85, anchor="center", stretch=False)
        self.sym_tree.column("ambito", width=140, anchor="w")

        sym_scroll = ttk.Scrollbar(sym_wrap, orient="vertical", command=self.sym_tree.yview)
        self.sym_tree.configure(yscrollcommand=sym_scroll.set)
        self.sym_tree.pack(side="left", fill="both", expand=True)
        sym_scroll.pack(side="right", fill="y")

        # PANEL DERECHO: Código Intermedio + Tabla de Optimización
        right_frame = ctk.CTkFrame(main_pane, fg_color="transparent")
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        right_frame.grid_rowconfigure(0, weight=2)
        right_frame.grid_rowconfigure(1, weight=3)
        right_frame.grid_columnconfigure(0, weight=1)

        # Subpanel Superior: Código Intermedio Generado
        inter_frame = ctk.CTkFrame(right_frame, corner_radius=8)
        inter_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 6))

        self.inter_title = ctk.CTkLabel(
            inter_frame,
            text="2. Código Intermedio Generado",
            font=("Segoe UI", 13, "bold"),
            anchor="w",
        )
        self.inter_title.pack(fill="x", padx=12, pady=(8, 4))

        inter_tree_wrap = tk.Frame(inter_frame, bg="#1e222a")
        inter_tree_wrap.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.inter_tree = ttk.Treeview(
            inter_tree_wrap,
            columns=("num", "instruccion"),
            show="headings",
            style="Custom.Treeview",
        )
        self.inter_tree.heading("num", text="#")
        self.inter_tree.heading("instruccion", text="Instrucción Intermedia Generada")
        self.inter_tree.column("num", width=55, anchor="center", stretch=False)
        self.inter_tree.column("instruccion", width=540, anchor="w")

        inter_scroll = ttk.Scrollbar(inter_tree_wrap, orient="vertical", command=self.inter_tree.yview)
        self.inter_tree.configure(yscrollcommand=inter_scroll.set)
        self.inter_tree.pack(side="left", fill="both", expand=True)
        inter_scroll.pack(side="right", fill="y")

        # Subpanel Inferior: Tabla de Optimización (4 columnas exactas Inciso 4)
        opt_frame = ctk.CTkFrame(right_frame, corner_radius=8)
        opt_frame.grid(row=1, column=0, sticky="nsew", pady=(6, 0))

        opt_header_row = ctk.CTkFrame(opt_frame, fg_color="transparent")
        opt_header_row.pack(fill="x", padx=12, pady=(8, 4))

        ctk.CTkLabel(
            opt_header_row,
            text="3. Proceso de Optimización (Local / Derivada)",
            font=("Segoe UI", 13, "bold"),
            anchor="w",
        ).pack(side="left")

        self.opt_lock_badge = ctk.CTkLabel(
            opt_header_row,
            text="HABILITADA",
            text_color="#3fb950",
            font=("Segoe UI", 11, "bold"),
        )
        self.opt_lock_badge.pack(side="right")

        opt_tree_wrap = tk.Frame(opt_frame, bg="#1e222a")
        opt_tree_wrap.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        cols = ("original", "optimizacion", "afectado", "modificado")
        self.opt_tree = ttk.Treeview(
            opt_tree_wrap,
            columns=cols,
            show="headings",
            style="Custom.Treeview",
        )
        self.opt_tree.heading("original", text="Cuádruplo original")
        self.opt_tree.heading("optimizacion", text="Optimización")
        self.opt_tree.heading("afectado", text="Cuádruplo afectado")
        self.opt_tree.heading("modificado", text="Cuádruplo modificado")

        self.opt_tree.column("original", width=235, anchor="w")
        self.opt_tree.column("optimizacion", width=110, anchor="center", stretch=False)
        self.opt_tree.column("afectado", width=135, anchor="center", stretch=False)
        self.opt_tree.column("modificado", width=250, anchor="w")

        opt_scroll = ttk.Scrollbar(opt_tree_wrap, orient="vertical", command=self.opt_tree.yview)
        self.opt_tree.configure(yscrollcommand=opt_scroll.set)
        self.opt_tree.pack(side="left", fill="both", expand=True)
        opt_scroll.pack(side="right", fill="y")

        self.lock_overlay = ctk.CTkLabel(
            opt_tree_wrap,
            text="OPTIMIZACIÓN BLOQUEADA POR DEFECTO\n(No disponible para Código de Tres Direcciones)",
            fg_color="#161920",
            text_color="#f85149",
            font=("Segoe UI", 14, "bold"),
        )

    def _on_text_scroll(self, first, last):
        self.line_numbers.yview_moveto(first)

    def _update_line_numbers(self, error_line: int | None = None):
        total_lines = int(self._raw_text.index("end-1c").split(".")[0])
        numbers_text = "\n".join(str(i) for i in range(1, total_lines + 1))

        self.line_numbers.configure(state="normal")
        self.line_numbers.delete("1.0", "end")
        self.line_numbers.insert("1.0", numbers_text)

        self._raw_text.tag_remove("error_line", "1.0", "end")
        self.line_numbers.tag_remove("error_num", "1.0", "end")

        if error_line is not None and 1 <= error_line <= total_lines:
            self._raw_text.tag_add("error_line", f"{error_line}.0", f"{error_line}.end+1c")
            self.line_numbers.tag_add("error_num", f"{error_line}.0", f"{error_line}.end+1c")

        self.line_numbers.yview_moveto(self._raw_text.yview()[0])
        self.line_numbers.configure(state="disabled")

    def _load_file(self):
        file_path = filedialog.askopenfilename(
            title="Seleccionar archivo con código Java depurado",
            filetypes=[("Archivos Java / Texto", "*.java *.txt"), ("Todos los archivos", "*.*")],
        )
        if not file_path:
            return
        content = Path(file_path).read_text(encoding="utf-8")
        self.code_editor.delete("1.0", "end")
        self.code_editor.insert("1.0", content)
        self._update_line_numbers()
        self._run_synthesis()

    def _on_mode_changed(self):
        self._run_synthesis()

    def _on_code_edited(self, _event=None):
        self._update_line_numbers()
        if self._debounce_job is not None:
            self.after_cancel(self._debounce_job)
        self._debounce_job = self.after(180, self._run_synthesis)

    def _clear_all_tables(self):
        """Limpia por completo las tablas cuando existe un error en el código Java."""
        for tree in (self.inter_tree, self.opt_tree, self.sym_tree):
            for item_id in tree.get_children():
                tree.delete(item_id)

    def _sync_treeview_inplace(self, tree: ttk.Treeview, new_rows: list[tuple]):
        """Actualiza filas existentes sin reiniciar la tabla (Inciso 6)."""
        existing_ids = tree.get_children()
        min_len = min(len(existing_ids), len(new_rows))

        for i in range(min_len):
            tree.item(existing_ids[i], values=new_rows[i])

        if len(new_rows) > len(existing_ids):
            for i in range(len(existing_ids), len(new_rows)):
                tree.insert("", "end", values=new_rows[i])
        elif len(existing_ids) > len(new_rows):
            for i in range(len(new_rows), len(existing_ids)):
                tree.delete(existing_ids[i])

    def _run_synthesis(self):
        source_code = self.code_editor.get("1.0", "end-1c")
        mode = self.selected_mode.get()

        titles = {
            CompilerSynthesisService.MODE_CUADRUPLOS: "2. Código Intermedio Generado (Cuádruplos: n. (val1, ope, val2, res))",
            CompilerSynthesisService.MODE_TRIPLOS: "2. Código Intermedio Generado (Triplos: n. (val1, ope, val2))",
            CompilerSynthesisService.MODE_TRES_DIRECCIONES: "2. Código Intermedio Generado (Tres Direcciones: Tn. (val1, ope, val2) | 1 ≤ n ≤ 3)",
        }
        self.inter_title.configure(text=titles.get(mode, "2. Código Intermedio Generado"))

        result = self.service.process(source_code, mode)

        # Bloqueo por defecto en Tres Direcciones (Inciso 3)
        if result.optimization_locked:
            self.opt_lock_badge.configure(text="BLOQUEADA (TRES DIRECCIONES)", text_color="#f85149")
            self.lock_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        else:
            self.opt_lock_badge.configure(text="HABILITADA", text_color="#3fb950")
            self.lock_overlay.place_forget()

        # Si hay cualquier error de validación, limpiar tablas y marcar línea (Inciso 1)
        if not result.validation.is_valid:
            first_error = result.validation.errors[0] if result.validation.errors else "Código no válido."
            self._update_line_numbers(error_line=result.validation.error_line)
            self._clear_all_tables()
            self.status_label.configure(
                text=f"✖ VALIDACIÓN FALLIDA (No se genera CI): {first_error}",
                fg_color="#3d1c1e",
                text_color="#ff7b72",
            )
            return

        if result.runtime_error:
            self._update_line_numbers(error_line=None)
            self._clear_all_tables()
            self.status_label.configure(
                text=f"⚠ RESTRICCIÓN DE SÍNTESIS: {result.runtime_error}",
                fg_color="#3d2e14",
                text_color="#ffa657",
            )
            return

        self._update_line_numbers(error_line=None)
        self.status_label.configure(
            text=f"✔ CLASE PRINCIPAL VÁLIDA: '{result.validation.class_name}' ({result.validation.main_class_id}) — Actualización continua activa",
            fg_color="#163322",
            text_color="#56d364",
        )

        # Actualizar Tabla de Símbolos (IDs Global vs Local)
        sym_values = [
            (s.id_code, s.lexeme, s.data_type, s.scope)
            for s in result.symbols
        ]
        self._sync_treeview_inplace(self.sym_tree, sym_values)

        # Actualizar Código Intermedio in-place
        inter_values = [(i, line) for i, line in enumerate(result.intermediate_lines, start=1)]
        self._sync_treeview_inplace(self.inter_tree, inter_values)

        # Actualizar Tabla de Optimización in-place
        if not result.optimization_locked:
            opt_values = [
                (
                    row.cuadruplo_original,
                    row.acronimo_optimizacion,
                    row.cuadruplo_afectado,
                    row.cuadruplo_modificado,
                )
                for row in result.optimization_rows
            ]
            self._sync_treeview_inplace(self.opt_tree, opt_values)
            # Actualizar encabezados de la tabla de optimización según el modo activo
        if mode == "TRIPLOS":
            self.opt_tree.heading("#1", text="Triplo original")
            self.opt_tree.heading("#3", text="Triplo afectado")
            self.opt_tree.heading("#4", text="Triplo modificado")
        else:
            self.opt_tree.heading("#1", text="Cuádruplo original")
            self.opt_tree.heading("#3", text="Cuádruplo afectado")
            self.opt_tree.heading("#4", text="Cuádruplo modificado")

        # Evitar que se recorte el texto "Cuádruplo afectado" en la 3ra columna
        self.opt_tree.column("#3", width=155)