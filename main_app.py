# main_app.py
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from tkcalendar import Calendar
import database as db
import datetime
import threading
import time
import webbrowser
import re
import urllib.parse # Para codificar URLs (Compartir)
import sys # Para resource_path (PyInstaller)
import os  # Para resource_path (PyInstaller)
from PIL import Image, ImageTk # Para imagen de fondo

# --- Helper para Rutas Relativas (PyInstaller) ---
def resource_path(relative_path):
    """ Obtiene la ruta absoluta al recurso, funciona para desarrollo y para PyInstaller """
    try:
        # PyInstaller crea una carpeta temporal y almacena la ruta en _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Si no se está ejecutando desde PyInstaller, __file__ apunta al script actual
        base_path = os.path.abspath(os.path.dirname(__file__))

    return os.path.join(base_path, relative_path)
# --- Fin Helper ---


class AudienciaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Gestor de Audiencias")
        # self.root.geometry("850x650") # Ajusta tamaño inicial si es necesario

        # --- Inicializar DB ---
        db.inicializar_db()

        # --- Variables ---
        self.fecha_seleccionada = datetime.date.today().strftime("%Y-%m-%d")
        self.evento_seleccionado_id = None
        self.recordatorios_mostrados_hoy = set()
        self.bg_image = None # Para mantener referencia a la imagen de fondo

        # --- Crear Widgets ---
        self.crear_widgets()
        self.cargar_eventos_fecha_actual()
        self.marcar_dias_calendario()

        # --- Iniciar Hilo de Recordatorios ---
        self.stop_event = threading.Event()
        self.hilo_recordatorios = threading.Thread(target=self.verificar_recordatorios_periodicamente, daemon=True)
        self.hilo_recordatorios.start()

        # --- Manejar cierre de ventana ---
        self.root.protocol("WM_DELETE_WINDOW", self.cerrar_aplicacion)

    def crear_widgets(self):
        # --- Configurar Imagen de Fondo ---
        try:
            image_path = resource_path("assets/logoLegalito01.png") # Ajusta si tu imagen tiene otro nombre/extensión
            bg_image_pil = Image.open(image_path)
            # Opcional: Redimensionar si es necesario para ajustarse mejor
            # desired_width = 850
            # desired_height = 650
            # bg_image_pil = bg_image_pil.resize((desired_width, desired_height), Image.Resampling.LANCZOS)
            self.bg_image = ImageTk.PhotoImage(bg_image_pil) # Guardar referencia

            bg_label = tk.Label(self.root, image=self.bg_image)
            bg_label.place(x=0, y=0, relwidth=1, relheight=1)
            bg_label.lower() # Poner detrás de otros widgets
        except FileNotFoundError:
            print("Advertencia: No se encontró la imagen de fondo en 'assets/background.png'.")
        except Exception as e:
            print(f"Error al cargar la imagen de fondo: {e}")
        # --- Fin Configurar Imagen de Fondo ---


        # --- Frame Principal (Ahora encima del fondo) ---
        # Este frame contendrá todo lo demás
        main_frame = ttk.Frame(self.root, padding="10")
        # Para que se vea la imagen de fondo a través de los huecos, el frame no debe tener fondo propio.
        # Esto se puede hacer con estilos, pero es más complejo. Por ahora, los widgets internos lo taparán.
        main_frame.pack(fill=tk.BOTH, expand=True)


        # --- Frame Izquierdo (Calendario y Botones) ---
        left_frame = ttk.Frame(main_frame) # PADRE: main_frame
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10), anchor=tk.NW) # Anclar Noroeste

        # Calendario
        self.cal = Calendar(left_frame, selectmode='day', # PADRE: left_frame
                            year=datetime.date.today().year,
                            month=datetime.date.today().month,
                            day=datetime.date.today().day,
                            date_pattern='y-mm-dd',
                            tooltipforeground='black',
                            tooltipbackground='#FFFFE0')
        self.cal.pack(pady=10)
        self.cal.bind("<<CalendarSelected>>", self.actualizar_lista_eventos)
        self.cal.tag_config('evento', background='lightblue', foreground='black')

        # Botones bajo el calendario
        btn_frame = ttk.Frame(left_frame) # PADRE: left_frame
        btn_frame.pack(fill=tk.X)

        add_btn = ttk.Button(btn_frame, text="Agregar Audiencia", command=self.abrir_dialogo_evento) # PADRE: btn_frame
        add_btn.pack(fill=tk.X, pady=5)

        # --- Frame Derecho (Lista de Eventos y Detalles) ---
        right_frame = ttk.Frame(main_frame) # PADRE: main_frame
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True) # Usar LEFT aquí también para que estén uno al lado del otro

        # Etiqueta Fecha Seleccionada
        self.lbl_fecha = ttk.Label(right_frame, text=f"Audiencias para: {self.fecha_seleccionada}", font=("Arial", 12, "bold")) # PADRE: right_frame
        self.lbl_fecha.pack(pady=(0, 5), anchor=tk.W)

        # Frame para Treeview con Scrollbar (ocupa la parte superior)
        tree_frame = ttk.Frame(right_frame) # PADRE: right_frame
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5)) # Se expande verticalmente

        cols = ("ID", "Hora", "Descripción Corta", "Link Corto")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show='headings', selectmode="browse") # PADRE: tree_frame
        # ... (configuración encabezados y columnas como antes) ...
        self.tree.heading("ID", text="ID")
        self.tree.heading("Hora", text="Hora")
        self.tree.heading("Descripción Corta", text="Descripción")
        self.tree.heading("Link Corto", text="Link")
        self.tree.column("ID", width=40, stretch=tk.NO, anchor=tk.CENTER)
        self.tree.column("Hora", width=60, stretch=tk.NO, anchor=tk.CENTER)
        self.tree.column("Descripción Corta", width=300, stretch=True) # Permitir expansión
        self.tree.column("Link Corto", width=150, stretch=True) # Permitir expansión

        scrollbar_y = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview) # PADRE: tree_frame
        self.tree.configure(yscrollcommand=scrollbar_y.set)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.tree.bind('<<TreeviewSelect>>', self.on_tree_select)
        self.tree.bind("<Double-1>", self.abrir_link_seleccionado)

        # --- Frame para Botones Edición/Eliminación/Compartir (justo debajo del Treeview) ---
        # Lo ponemos aquí para que el área de detalles quede al final
        edit_actions_frame = ttk.Frame(right_frame) # PADRE: right_frame
        edit_actions_frame.pack(fill=tk.X, pady=(5, 5)) # Rellena horizontalmente

        self.edit_btn = ttk.Button(edit_actions_frame, text="Editar", command=self.editar_evento_seleccionado, state=tk.DISABLED) # PADRE: edit_actions_frame
        self.edit_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.delete_btn = ttk.Button(edit_actions_frame, text="Eliminar", command=self.eliminar_evento_seleccionado, state=tk.DISABLED) # PADRE: edit_actions_frame
        self.delete_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.share_btn = ttk.Button(edit_actions_frame, text="Compartir", command=self.mostrar_menu_compartir, state=tk.DISABLED) # PADRE: edit_actions_frame
        self.share_btn.pack(side=tk.LEFT, padx=(0, 5)) # Añadido Botón Compartir

        self.open_link_btn = ttk.Button(edit_actions_frame, text="Abrir Link", command=self.abrir_link_seleccionado, state=tk.DISABLED) # PADRE: edit_actions_frame
        self.open_link_btn.pack(side=tk.RIGHT) # Botón Abrir Link a la derecha

        # --- Área de Texto para Detalles Completos (debajo de los botones de acción) ---
        details_frame = ttk.LabelFrame(right_frame, text="Detalles Completos", padding="5") # PADRE: right_frame
        details_frame.pack(fill=tk.X, pady=(0, 5), side=tk.BOTTOM) # Empaquetar abajo, relleno horizontal

        # Widget Text con Scrollbar
        details_text_frame = ttk.Frame(details_frame) # Frame interno
        details_text_frame.pack(fill=tk.X, expand=True)

        self.details_text = tk.Text(details_text_frame, height=6, wrap=tk.WORD, state=tk.DISABLED,
                                    borderwidth=0, relief="flat",
                                    background=self.root.cget('bg')) # Fondo igual a la ventana
        details_scrollbar = ttk.Scrollbar(details_text_frame, orient=tk.VERTICAL, command=self.details_text.yview)
        self.details_text.configure(yscrollcommand=details_scrollbar.set)

        details_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.details_text.pack(side=tk.LEFT, fill=tk.X, expand=True)

    # --- Métodos de la Clase ---

    def marcar_dias_calendario(self):
        """Obtiene fechas con eventos y las marca en el widget Calendar."""
        self.cal.calevent_remove(tag='evento') # Limpiar marcas anteriores
        fechas_eventos = db.obtener_fechas_con_eventos()
        for fecha_str in fechas_eventos:
            try:
                fecha_obj = datetime.datetime.strptime(fecha_str, "%Y-%m-%d").date()
                self.cal.calevent_create(fecha_obj, 'Audiencia', tags='evento')
            except ValueError:
                print(f"Error al parsear fecha '{fecha_str}' para marcar calendario.")
            except Exception as e:
                 print(f"Error al crear evento de calendario para {fecha_str}: {e}")

    def actualizar_lista_eventos(self, event=None):
        """Obtiene eventos de la DB para la fecha seleccionada y actualiza el Treeview."""
        self.fecha_seleccionada = self.cal.get_date()
        self.lbl_fecha.config(text=f"Audiencias para: {self.fecha_seleccionada}")

        for item in self.tree.get_children(): self.tree.delete(item) # Limpiar Treeview

        eventos = db.obtener_eventos_por_fecha(self.fecha_seleccionada)
        for evento in eventos:
            hora = evento.get('hora', '--:--') if evento.get('hora') else "--:--" # Más seguro con .get
            desc_completa = evento.get('descripcion', "")
            desc_corta = desc_completa.split('\n')[0]
            if len(desc_corta) > 60: desc_corta = desc_corta[:57] + '...'

            link_completo = evento.get('link', "")
            link_corto = link_completo[:40] + '...' if len(link_completo) > 40 else link_completo

            self.tree.insert("", tk.END, values=(evento['id'], hora, desc_corta, link_corto), iid=str(evento['id']))

        self.deshabilitar_botones_edicion()
        self.limpiar_detalles()

    def cargar_eventos_fecha_actual(self):
        """Llama a actualizar_lista_eventos para la fecha de hoy al iniciar."""
        self.actualizar_lista_eventos()

    def on_tree_select(self, event=None):
        """Maneja la selección de un item en el Treeview."""
        selected_items = self.tree.selection()
        if selected_items:
            try:
                self.evento_seleccionado_id = int(selected_items[0])
                self.habilitar_botones_edicion()
                self.mostrar_detalles_evento(self.evento_seleccionado_id)
            except (ValueError, tk.TclError) as e: # Capturar TclError también por si el item desaparece
                print(f"Error al seleccionar evento: {e}")
                self.evento_seleccionado_id = None
                self.deshabilitar_botones_edicion()
                self.limpiar_detalles()
        else:
            self.evento_seleccionado_id = None
            self.deshabilitar_botones_edicion()
            self.limpiar_detalles()

    def mostrar_detalles_evento(self, evento_id):
        """Obtiene los detalles completos de un evento y los muestra en el Text widget."""
        evento = db.obtener_evento_por_id(evento_id)
        self.details_text.config(state=tk.NORMAL)
        self.details_text.delete('1.0', tk.END)

        if evento:
            hora_display = evento.get('hora') if evento.get('hora') else "No especificada"
            link_display = evento.get('link') if evento.get('link') else "No especificado"
            recordatorio_display = "Sí" if evento.get('recordatorio_activo') else "No"
            minutos_display = f" ({evento.get('recordatorio_minutos', 15)} min antes)" if evento.get('recordatorio_activo') else ""

            detalle_texto = f"Fecha: {evento.get('fecha', 'N/A')}\n"
            detalle_texto += f"Hora: {hora_display}\n\n"
            detalle_texto += f"Descripción:\n{evento.get('descripcion', 'N/A')}\n\n"
            detalle_texto += f"Link:\n{link_display}\n\n"
            detalle_texto += f"Recordatorio: {recordatorio_display}{minutos_display}"

            self.details_text.insert('1.0', detalle_texto)
        else:
            self.details_text.insert('1.0', "No se pudieron cargar los detalles del evento.")

        self.details_text.config(state=tk.DISABLED)

    def limpiar_detalles(self):
        """Limpia el widget de texto de detalles."""
        self.details_text.config(state=tk.NORMAL)
        self.details_text.delete('1.0', tk.END)
        self.details_text.config(state=tk.DISABLED)

    def habilitar_botones_edicion(self):
        self.edit_btn.config(state=tk.NORMAL)
        self.delete_btn.config(state=tk.NORMAL)
        self.share_btn.config(state=tk.NORMAL) # Habilitar Compartir
        if self.evento_seleccionado_id:
             evento = db.obtener_evento_por_id(self.evento_seleccionado_id)
             if evento and evento.get('link'):
                 self.open_link_btn.config(state=tk.NORMAL)
             else:
                 self.open_link_btn.config(state=tk.DISABLED)
        else:
             self.open_link_btn.config(state=tk.DISABLED)

    def deshabilitar_botones_edicion(self):
        self.edit_btn.config(state=tk.DISABLED)
        self.delete_btn.config(state=tk.DISABLED)
        self.share_btn.config(state=tk.DISABLED) # Deshabilitar Compartir
        self.open_link_btn.config(state=tk.DISABLED)

    def abrir_link_seleccionado(self, event=None):
        if not self.evento_seleccionado_id: return
        evento = db.obtener_evento_por_id(self.evento_seleccionado_id)
        link_completo = evento.get('link') if evento else None

        if link_completo:
            try:
                print(f"Abriendo link: {link_completo}")
                webbrowser.open_new_tab(link_completo)
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo abrir el link:\n{e}")
        else:
             messagebox.showinfo("Información", "Este evento no tiene un link asociado.")

    def _formatear_texto_para_compartir(self, evento):
        """Formatea los detalles del evento en un texto legible para compartir."""
        if not evento: return "Error: No se encontró el evento."
        texto = f"Detalles de la Audiencia:\n"
        texto += f"-------------------------\n"
        texto += f"Fecha: {evento.get('fecha', 'N/A')}\n"
        if evento.get('hora'): texto += f"Hora: {evento['hora']}\n"
        texto += f"Descripción: {evento.get('descripcion', 'N/A')}\n"
        if evento.get('link'): texto += f"Link: {evento['link']}\n"
        texto += f"-------------------------"
        return texto

    def _compartir_por_email(self):
        """Prepara y abre el cliente de email con los detalles del evento."""
        if not self.evento_seleccionado_id: return
        evento = db.obtener_evento_por_id(self.evento_seleccionado_id)
        if not evento:
            messagebox.showerror("Error", "No se pudo obtener la información del evento para compartir.")
            return

        desc_corta = evento.get('descripcion', 'Evento').split('\n')[0][:30]
        asunto = f"Detalles Audiencia: {evento.get('fecha', '')} - {desc_corta}"
        cuerpo = self._formatear_texto_para_compartir(evento)
        asunto_codificado = urllib.parse.quote(asunto)
        cuerpo_codificado = urllib.parse.quote(cuerpo)
        mailto_url = f"mailto:?subject={asunto_codificado}&body={cuerpo_codificado}"

        try:
            print(f"Abriendo URL de email: {mailto_url}")
            webbrowser.open(mailto_url)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el cliente de correo:\n{e}", parent=self.root)

    def _compartir_por_whatsapp(self):
        """Prepara y abre WhatsApp Web/Desktop con los detalles del evento."""
        if not self.evento_seleccionado_id: return
        evento = db.obtener_evento_por_id(self.evento_seleccionado_id)
        if not evento:
            messagebox.showerror("Error", "No se pudo obtener la información del evento para compartir.")
            return

        texto = self._formatear_texto_para_compartir(evento)
        texto_codificado = urllib.parse.quote(texto)
        whatsapp_url = f"https://wa.me/?text={texto_codificado}"

        try:
            print(f"Abriendo URL de WhatsApp: {whatsapp_url}")
            webbrowser.open(whatsapp_url)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir WhatsApp:\n{e}", parent=self.root)

    def mostrar_menu_compartir(self):
        """Muestra un menú emergente con opciones para compartir."""
        if not self.evento_seleccionado_id:
            messagebox.showwarning("Advertencia", "Selecciona una audiencia para compartir.", parent=self.root)
            return

        # Crear el menú emergente
        menu_compartir = tk.Menu(self.root, tearoff=0)
        menu_compartir.add_command(label="Compartir por Email", command=self._compartir_por_email)
        menu_compartir.add_command(label="Compartir por WhatsApp", command=self._compartir_por_whatsapp)

        # Calcular coordenadas para mostrar el menú cerca del botón "Compartir"
        try:
            share_button_widget = self.share_btn
            x = share_button_widget.winfo_rootx()
            y = share_button_widget.winfo_rooty() + share_button_widget.winfo_height()
            menu_compartir.tk_popup(x, y)
        except Exception as e:
             print(f"Error al mostrar menú compartir: {e}")
             # Fallback: mostrar en la posición del cursor
             menu_compartir.tk_popup(self.root.winfo_pointerx(), self.root.winfo_pointery())
        finally:
            # Asegurarse de que el menú se maneje correctamente
            menu_compartir.grab_release()


    def abrir_dialogo_evento(self, evento_id=None):
        """Abre una ventana Toplevel para agregar o editar un evento."""
        dialog = tk.Toplevel(self.root)
        if evento_id:
            dialog.title("Editar Audiencia")
            datos_evento = db.obtener_evento_por_id(evento_id)
            if not datos_evento:
                messagebox.showerror("Error", "No se pudo cargar la información del evento.", parent=dialog)
                dialog.destroy(); return
        else:
            dialog.title("Agregar Audiencia")
            datos_evento = {} # Diccionario vacío para evitar errores de clave

        dialog.geometry("450x380")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding="15")
        frame.pack(expand=True, fill=tk.BOTH)

        # Campos del Formulario...
        ttk.Label(frame, text="Fecha:").grid(row=0, column=0, sticky=tk.W, pady=2)
        fecha_val = datos_evento.get('fecha') if evento_id else self.fecha_seleccionada
        ttk.Label(frame, text=fecha_val).grid(row=0, column=1, sticky=tk.W, pady=2)
        fecha_a_guardar = fecha_val

        ttk.Label(frame, text="Hora:").grid(row=1, column=0, sticky=tk.W, pady=2)
        hora_var = tk.StringVar(value=datos_evento.get('hora', ''))
        entry_hora = ttk.Entry(frame, textvariable=hora_var, width=40)
        entry_hora.grid(row=1, column=1, sticky=tk.EW, pady=2)

        ttk.Label(frame, text="Link:").grid(row=2, column=0, sticky=tk.W, pady=2)
        link_var = tk.StringVar(value=datos_evento.get('link', ''))
        ttk.Entry(frame, textvariable=link_var, width=40).grid(row=2, column=1, sticky=tk.EW, pady=2)

        ttk.Label(frame, text="Descripción:").grid(row=3, column=0, sticky=tk.NW, pady=2)
        desc_text = tk.Text(frame, height=5, width=30, wrap=tk.WORD)
        desc_text.grid(row=3, column=1, sticky=tk.NSEW, pady=2) # NSEW para que expanda
        desc_scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=desc_text.yview)
        desc_scroll.grid(row=3, column=2, sticky=tk.NS)
        desc_text['yscrollcommand'] = desc_scroll.set
        if evento_id: desc_text.insert(tk.END, datos_evento.get('descripcion', ''))

        # Opciones de Recordatorio...
        recordatorio_frame = ttk.LabelFrame(frame, text="Recordatorio", padding="5")
        recordatorio_frame.grid(row=4, column=0, columnspan=3, sticky=tk.EW, pady=10) # Span 3

        recordatorio_activo_var = tk.IntVar(value=datos_evento.get('recordatorio_activo', 0))
        chk_recordatorio = ttk.Checkbutton(recordatorio_frame, text="Activar", variable=recordatorio_activo_var)
        chk_recordatorio.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(recordatorio_frame, text="Minutos antes:").pack(side=tk.LEFT)
        minutos_val = datos_evento.get('recordatorio_minutos', 15)
        minutos_var = tk.IntVar(value=minutos_val)
        vcmd = (frame.register(self.validate_int), '%P')
        spin_minutos = tk.Spinbox(recordatorio_frame, from_=1, to=1440, width=5, textvariable=minutos_var, validate='key', validatecommand=vcmd)
        spin_minutos.pack(side=tk.LEFT, padx=5)

        # Botones Guardar/Cancelar...
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=5, column=0, columnspan=3, pady=15)

        btn_guardar = ttk.Button(button_frame, text="Guardar",
                                 command=lambda: self.guardar_evento(
                                     evento_id, fecha_a_guardar, hora_var.get(), link_var.get(),
                                     desc_text.get("1.0", tk.END).strip(),
                                     recordatorio_activo_var.get(), minutos_var.get(), dialog))
        btn_guardar.pack(side=tk.LEFT, padx=5)
        btn_cancelar = ttk.Button(button_frame, text="Cancelar", command=dialog.destroy)
        btn_cancelar.pack(side=tk.LEFT, padx=5)

        frame.columnconfigure(1, weight=1) # Columna de campos expandible
        frame.rowconfigure(3, weight=1) # Fila de descripción expandible

        entry_hora.focus_set()
        self.root.wait_window(dialog)

    def validate_int(self, P):
        """ Función de validación para Spinbox: permite solo dígitos o vacío """
        return P == "" or P.isdigit()

    def parsear_hora(self, hora_str):
        """Intenta parsear la hora desde varios formatos a HH:MM. Devuelve HH:MM, "" o None."""
        if not hora_str or hora_str.isspace(): return ""
        hora_str = hora_str.strip().replace('.', ':')
        match_hm = re.fullmatch(r"(\d{1,2}):(\d{1,2})", hora_str)
        if match_hm:
            h, m = int(match_hm.group(1)), int(match_hm.group(2))
            if 0 <= h <= 23 and 0 <= m <= 59: return f"{h:02d}:{m:02d}"
        match_h = re.fullmatch(r"(\d{1,2})", hora_str)
        if match_h:
            h = int(match_h.group(1))
            if 0 <= h <= 23: return f"{h:02d}:00"
        return None

    def guardar_evento(self, evento_id, fecha, hora_str, link, descripcion, recordatorio_activo, recordatorio_minutos, dialog):
        """Guarda un evento nuevo o actualiza uno existente en la DB."""
        hora_formateada = self.parsear_hora(hora_str)
        if hora_str and hora_formateada is None:
            messagebox.showerror("Error de Validación", "Formato de hora inválido.\nIntente HH:MM, H:MM, o solo la hora (ej: 9, 14).", parent=dialog)
            return
        if not descripcion:
            messagebox.showerror("Error de Validación", "La descripción no puede estar vacía.", parent=dialog)
            return

        success = False
        action_msg = ""
        error_msg = ""

        if evento_id: # Actualizar
            success = db.actualizar_evento(evento_id, fecha, hora_formateada, link, descripcion, recordatorio_activo, recordatorio_minutos)
            action_msg = "Audiencia actualizada correctamente."
            error_msg = "No se pudo actualizar la audiencia."
        else: # Agregar
            new_id = db.agregar_evento(fecha, hora_formateada, link, descripcion, recordatorio_activo, recordatorio_minutos)
            if new_id: success = True
            action_msg = "Audiencia agregada correctamente."
            error_msg = "No se pudo agregar la audiencia."

        if success:
            messagebox.showinfo("Éxito", action_msg, parent=dialog)
            dialog.destroy()
            self.actualizar_lista_eventos()
            self.marcar_dias_calendario()
        else:
            messagebox.showerror("Error", error_msg, parent=dialog)


    def editar_evento_seleccionado(self):
        if self.evento_seleccionado_id: self.abrir_dialogo_evento(self.evento_seleccionado_id)
        else: messagebox.showwarning("Advertencia", "Selecciona una audiencia de la lista para editar.")

    def eliminar_evento_seleccionado(self):
        if not self.evento_seleccionado_id:
             messagebox.showwarning("Advertencia", "Selecciona una audiencia de la lista para eliminar.")
             return
        try:
            item = self.tree.item(str(self.evento_seleccionado_id))
            desc_corta = item['values'][2] if item and len(item['values']) > 2 else "seleccionada"
        except tk.TclError: desc_corta = "seleccionada"

        if messagebox.askyesno("Confirmar Eliminación", f"¿Estás seguro de que quieres eliminar la audiencia '{desc_corta}'?", parent=self.root):
            success = db.eliminar_evento(self.evento_seleccionado_id)
            if success:
                self.actualizar_lista_eventos()
                self.marcar_dias_calendario()
                self.limpiar_detalles()
            else: messagebox.showerror("Error", "No se pudo eliminar la audiencia.")

    # --- Lógica de Recordatorios (sin cambios funcionales mayores) ---
    def verificar_recordatorios_periodicamente(self):
        print("Hilo de recordatorios iniciado.")
        while not self.stop_event.is_set():
            try:
                ahora = datetime.datetime.now()
                hoy_str = ahora.strftime("%Y-%m-%d")
                if not hasattr(self, 'ultimo_chequeo_dia') or self.ultimo_chequeo_dia != hoy_str:
                     self.recordatorios_mostrados_hoy = set()
                     self.ultimo_chequeo_dia = hoy_str

                eventos = db.obtener_todos_eventos_con_recordatorio()
                for evento in eventos:
                    if not evento.get('hora'): continue
                    evento_id = evento['id']
                    try:
                        fecha_hora_evento = datetime.datetime.strptime(f"{evento['fecha']} {evento['hora']}", "%Y-%m-%d %H:%M")
                        minutos_antes = evento.get('recordatorio_minutos', 15)
                        hora_recordatorio = fecha_hora_evento - datetime.timedelta(minutes=minutos_antes)

                        if hora_recordatorio <= ahora < fecha_hora_evento and evento_id not in self.recordatorios_mostrados_hoy:
                             print(f"Mostrando recordatorio para evento ID: {evento_id}")
                             self.root.after(0, self.mostrar_recordatorio, evento) # Ejecutar en hilo principal
                             self.recordatorios_mostrados_hoy.add(evento_id)
                    except ValueError as e: print(f"Error fecha/hora recordatorio ID {evento_id}: {e}")
                    except Exception as e: print(f"Error inesperado recordatorio ID {evento_id}: {e}")
            except Exception as e: print(f"Error bucle recordatorios: {e}")
            self.stop_event.wait(60) # Verificar cada minuto
        print("Hilo de recordatorios detenido.")

    def mostrar_recordatorio(self, evento):
        hora_evento = evento.get('hora', '')
        descripcion = evento.get('descripcion', '')
        link = evento.get('link', '')
        desc_alerta = descripcion.split('\n')[0]
        if len(desc_alerta) > 100: desc_alerta = desc_alerta[:97] + '...'

        mensaje = f"RECORDATORIO DE AUDIENCIA\n\nHora: {hora_evento}\n{desc_alerta}"
        if link:
            link_corto_alerta = link[:60] + '...' if len(link) > 60 else link
            mensaje += f"\n\nLink: {link_corto_alerta}"
        messagebox.showwarning("Recordatorio de Audiencia", mensaje, parent=self.root)

    def cerrar_aplicacion(self):
        print("Cerrando aplicación...")
        self.stop_event.set()
        # self.hilo_recordatorios.join(timeout=1.0) # Espera opcional
        self.root.destroy()

# --- Punto de Entrada Principal ---
if __name__ == "__main__":
    root = tk.Tk()
    style = ttk.Style(root)
    # Intentar usar temas más modernos
    themes = style.theme_names()
    if 'vista' in themes: style.theme_use('vista')
    elif 'clam' in themes: style.theme_use('clam')
    elif 'alt' in themes: style.theme_use('alt')
    # print(f"Temas disponibles: {themes}") # Para depuración
    # print(f"Tema usado: {style.theme_use()}")

    app = AudienciaApp(root)
    root.mainloop()