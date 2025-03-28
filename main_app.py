# main_app.py
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from tkcalendar import Calendar # Ya no necesitamos DateEntry aquí
import database as db # Importamos nuestro módulo de base de datos
import datetime
import threading
import time
import webbrowser # Para abrir links
import re # Para expresiones regulares (parseo de hora)

class AudienciaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Gestor de Audiencias")
        # self.root.geometry("850x650") # Puedes ajustar el tamaño inicial si lo deseas

        # --- Inicializar DB ---
        db.inicializar_db()

        # --- Variables ---
        self.fecha_seleccionada = datetime.date.today().strftime("%Y-%m-%d")
        self.evento_seleccionado_id = None
        self.recordatorios_mostrados_hoy = set() # Para no repetir alertas el mismo día

        # --- Crear Widgets ---
        self.crear_widgets()
        self.cargar_eventos_fecha_actual()
        self.marcar_dias_calendario() # Marcar días con eventos al inicio

        # --- Iniciar Hilo de Recordatorios ---
        self.stop_event = threading.Event()
        self.hilo_recordatorios = threading.Thread(target=self.verificar_recordatorios_periodicamente, daemon=True)
        self.hilo_recordatorios.start()

        # --- Manejar cierre de ventana ---
        self.root.protocol("WM_DELETE_WINDOW", self.cerrar_aplicacion)

    def crear_widgets(self):
        # --- Frame Principal ---
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Frame Izquierdo (Calendario y Botones) ---
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        # Calendario
        self.cal = Calendar(left_frame, selectmode='day',
                            year=datetime.date.today().year,
                            month=datetime.date.today().month,
                            day=datetime.date.today().day,
                            date_pattern='y-mm-dd', # Coincide con formato DB
                            tooltipforeground='black', # Color del tooltip
                            tooltipbackground='#FFFFE0') # Fondo del tooltip (amarillo claro)
        self.cal.pack(pady=10)
        self.cal.bind("<<CalendarSelected>>", self.actualizar_lista_eventos)
        # Configurar tag para eventos en calendario (para las marcas)
        self.cal.tag_config('evento', background='lightblue', foreground='black')

        # Botones bajo el calendario
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X)

        add_btn = ttk.Button(btn_frame, text="Agregar Audiencia", command=self.abrir_dialogo_evento)
        add_btn.pack(fill=tk.X, pady=5)

        # --- Frame Derecho (Lista de Eventos y Detalles) ---
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Etiqueta Fecha Seleccionada
        self.lbl_fecha = ttk.Label(right_frame, text=f"Audiencias para: {self.fecha_seleccionada}", font=("Arial", 12, "bold"))
        self.lbl_fecha.pack(pady=(0, 5), anchor=tk.W)

        # Frame para Treeview con Scrollbar (ocupa la parte superior)
        tree_frame = ttk.Frame(right_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5)) # Se expande verticalmente

        cols = ("ID", "Hora", "Descripción Corta", "Link Corto")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show='headings', selectmode="browse")
        self.tree.heading("ID", text="ID")
        self.tree.heading("Hora", text="Hora")
        self.tree.heading("Descripción Corta", text="Descripción") # Título columna
        self.tree.heading("Link Corto", text="Link") # Título columna

        # Ajustar anchos de columna (ajusta según necesidad)
        self.tree.column("ID", width=40, stretch=tk.NO, anchor=tk.CENTER)
        self.tree.column("Hora", width=60, stretch=tk.NO, anchor=tk.CENTER)
        self.tree.column("Descripción Corta", width=300) # Puede ser más ancha ahora
        self.tree.column("Link Corto", width=150)

        # Añadir Scrollbar Vertical al Treeview
        scrollbar_y = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar_y.set)

        # Empaquetar Treeview y Scrollbar
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.tree.bind('<<TreeviewSelect>>', self.on_tree_select)
        self.tree.bind("<Double-1>", self.abrir_link_seleccionado) # Doble clic en Treeview abre link

        # --- Área de Texto para Detalles Completos (debajo del Treeview) ---
        details_frame = ttk.LabelFrame(right_frame, text="Detalles Completos", padding="5")
        details_frame.pack(fill=tk.X, pady=(5, 5), side=tk.BOTTOM) # Empaquetar abajo

        # Widget Text con Scrollbar
        details_text_frame = ttk.Frame(details_frame) # Frame interno para Text y Scrollbar
        details_text_frame.pack(fill=tk.X, expand=True)

        self.details_text = tk.Text(details_text_frame, height=6, wrap=tk.WORD, state=tk.DISABLED,
                                    borderwidth=0, relief="flat", # Sin borde visible
                                    background=self.root.cget('bg')) # Fondo igual a la ventana
        details_scrollbar = ttk.Scrollbar(details_text_frame, orient=tk.VERTICAL, command=self.details_text.yview)
        self.details_text.configure(yscrollcommand=details_scrollbar.set)

        details_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.details_text.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # --- Frame Botones Edición/Eliminación (debajo del área de detalles) ---
        edit_delete_frame = ttk.Frame(right_frame)
        edit_delete_frame.pack(fill=tk.X, pady=(5, 0), side=tk.BOTTOM) # Empaquetar justo encima de los detalles

        self.edit_btn = ttk.Button(edit_delete_frame, text="Editar", command=self.editar_evento_seleccionado, state=tk.DISABLED)
        self.edit_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.delete_btn = ttk.Button(edit_delete_frame, text="Eliminar", command=self.eliminar_evento_seleccionado, state=tk.DISABLED)
        self.delete_btn.pack(side=tk.LEFT)

        self.open_link_btn = ttk.Button(edit_delete_frame, text="Abrir Link", command=self.abrir_link_seleccionado, state=tk.DISABLED)
        self.open_link_btn.pack(side=tk.RIGHT)


    def marcar_dias_calendario(self):
        """Obtiene fechas con eventos y las marca en el widget Calendar."""
        # Limpiar marcas anteriores para evitar duplicados o marcas incorrectas
        self.cal.calevent_remove(tag='evento')

        fechas_eventos = db.obtener_fechas_con_eventos()
        for fecha_str in fechas_eventos:
            try:
                fecha_obj = datetime.datetime.strptime(fecha_str, "%Y-%m-%d").date()
                # Crear el evento visual con el tag 'evento'
                self.cal.calevent_create(fecha_obj, 'Audiencia', tags='evento')
                # Añadir un tooltip básico (opcional)
                # count = len(db.obtener_eventos_por_fecha(fecha_str)) # Podría ser ineficiente si hay muchas fechas
                # self.cal.calevent_create(fecha_obj, f'{count} evento(s)', tags='evento')
            except ValueError:
                print(f"Error al parsear fecha '{fecha_str}' para marcar calendario.")
            except Exception as e:
                 print(f"Error al crear evento de calendario para {fecha_str}: {e}")


    def actualizar_lista_eventos(self, event=None):
        """Obtiene eventos de la DB para la fecha seleccionada y actualiza el Treeview."""
        self.fecha_seleccionada = self.cal.get_date()
        self.lbl_fecha.config(text=f"Audiencias para: {self.fecha_seleccionada}")

        # Limpiar Treeview
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Cargar nuevos eventos
        eventos = db.obtener_eventos_por_fecha(self.fecha_seleccionada)
        for evento in eventos:
            hora = evento['hora'] if evento['hora'] else "--:--"
            # Mostrar solo la primera línea o los primeros N caracteres en el Treeview
            desc_completa = evento['descripcion'] if evento['descripcion'] else ""
            desc_corta = desc_completa.split('\n')[0] # Toma solo la primera línea
            if len(desc_corta) > 60: desc_corta = desc_corta[:57] + '...' # Acorta si es muy larga

            link_completo = evento['link'] if evento['link'] else ""
            link_corto = link_completo[:40] + '...' if len(link_completo) > 40 else link_completo

            self.tree.insert("", tk.END, values=(evento['id'], hora, desc_corta, link_corto), iid=str(evento['id'])) # Usar ID como iid

        # Deshabilitar botones y limpiar detalles al cambiar de fecha
        self.deshabilitar_botones_edicion()
        self.limpiar_detalles()

    def cargar_eventos_fecha_actual(self):
        """Llama a actualizar_lista_eventos para la fecha de hoy al iniciar."""
        self.actualizar_lista_eventos()

    def on_tree_select(self, event=None):
        """Maneja la selección de un item en el Treeview."""
        selected_items = self.tree.selection()
        if selected_items:
            # Asegurarse de que el ID es un entero
            try:
                self.evento_seleccionado_id = int(selected_items[0]) # Obtener el iid que es el ID del evento
                self.habilitar_botones_edicion()
                self.mostrar_detalles_evento(self.evento_seleccionado_id) # MOSTRAR DETALLES COMPLETOS
            except ValueError:
                print(f"Error: ID de evento no válido '{selected_items[0]}'")
                self.evento_seleccionado_id = None
                self.deshabilitar_botones_edicion()
                self.limpiar_detalles()
        else:
            self.evento_seleccionado_id = None
            self.deshabilitar_botones_edicion()
            self.limpiar_detalles() # LIMPIAR DETALLES si no hay selección

    def mostrar_detalles_evento(self, evento_id):
        """Obtiene los detalles completos de un evento y los muestra en el Text widget."""
        # Usa la función que añadimos a database.py
        evento = db.obtener_evento_por_id(evento_id)

        self.details_text.config(state=tk.NORMAL) # Habilitar para escribir/borrar
        self.details_text.delete('1.0', tk.END) # Limpiar contenido anterior

        if evento:
            hora_display = evento['hora'] if evento['hora'] else "No especificada"
            link_display = evento['link'] if evento['link'] else "No especificado"
            recordatorio_display = "Sí" if evento['recordatorio_activo'] else "No"
            minutos_display = f" ({evento['recordatorio_minutos']} min antes)" if evento['recordatorio_activo'] else ""

            # Construir el texto de detalles
            detalle_texto = f"Fecha: {evento['fecha']}\n"
            detalle_texto += f"Hora: {hora_display}\n\n"
            detalle_texto += f"Descripción:\n{evento['descripcion']}\n\n" # Descripción completa
            detalle_texto += f"Link:\n{link_display}\n\n"
            detalle_texto += f"Recordatorio: {recordatorio_display}{minutos_display}"

            self.details_text.insert('1.0', detalle_texto)
        else:
            self.details_text.insert('1.0', "No se pudieron cargar los detalles del evento.")

        self.details_text.config(state=tk.DISABLED) # Deshabilitar para hacerlo solo lectura

    def limpiar_detalles(self):
        """Limpia el widget de texto de detalles."""
        self.details_text.config(state=tk.NORMAL)
        self.details_text.delete('1.0', tk.END)
        self.details_text.config(state=tk.DISABLED)

    def habilitar_botones_edicion(self):
        self.edit_btn.config(state=tk.NORMAL)
        self.delete_btn.config(state=tk.NORMAL)
        # Habilitar abrir link solo si hay un link válido en la DB para este ID
        if self.evento_seleccionado_id:
             # Consultar DB para el link real, no depender de la vista truncada
             evento = db.obtener_evento_por_id(self.evento_seleccionado_id)
             if evento and evento['link']:
                 self.open_link_btn.config(state=tk.NORMAL)
             else:
                 self.open_link_btn.config(state=tk.DISABLED)
        else:
             self.open_link_btn.config(state=tk.DISABLED)


    def deshabilitar_botones_edicion(self):
        self.edit_btn.config(state=tk.DISABLED)
        self.delete_btn.config(state=tk.DISABLED)
        self.open_link_btn.config(state=tk.DISABLED)

    def abrir_link_seleccionado(self, event=None):
        if not self.evento_seleccionado_id:
            return

        # Obtener el link completo de la base de datos
        evento = db.obtener_evento_por_id(self.evento_seleccionado_id)
        link_completo = evento['link'] if evento else None

        if link_completo:
            try:
                print(f"Abriendo link: {link_completo}")
                webbrowser.open_new_tab(link_completo)
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo abrir el link:\n{e}")
        else:
             messagebox.showinfo("Información", "Este evento no tiene un link asociado o no se pudo encontrar.")


    def abrir_dialogo_evento(self, evento_id=None):
        """Abre una ventana Toplevel para agregar o editar un evento."""
        dialog = tk.Toplevel(self.root)
        if evento_id:
            dialog.title("Editar Audiencia")
            datos_evento = db.obtener_evento_por_id(evento_id) # Usar la función existente
            if not datos_evento:
                messagebox.showerror("Error", "No se pudo cargar la información del evento.", parent=dialog)
                dialog.destroy()
                return
        else:
            dialog.title("Agregar Audiencia")
            datos_evento = None # Para un nuevo evento

        dialog.geometry("450x380") # Aumentar un poco la altura para el Text
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding="15")
        frame.pack(expand=True, fill=tk.BOTH)

        # --- Campos del Formulario ---
        ttk.Label(frame, text="Fecha:").grid(row=0, column=0, sticky=tk.W, pady=2)
        fecha_val = datos_evento['fecha'] if evento_id else self.fecha_seleccionada
        # Mostrar la fecha (no editable directamente aquí, se toma del calendario ppal)
        ttk.Label(frame, text=fecha_val).grid(row=0, column=1, sticky=tk.W, pady=2)
        # Guardamos la fecha internamente para pasarla a guardar_evento
        fecha_a_guardar = fecha_val

        ttk.Label(frame, text="Hora:").grid(row=1, column=0, sticky=tk.W, pady=2)
        hora_var = tk.StringVar(value=datos_evento['hora'] if evento_id and datos_evento['hora'] else "")
        entry_hora = ttk.Entry(frame, textvariable=hora_var, width=40)
        entry_hora.grid(row=1, column=1, sticky=tk.EW, pady=2)

        ttk.Label(frame, text="Link:").grid(row=2, column=0, sticky=tk.W, pady=2)
        link_var = tk.StringVar(value=datos_evento['link'] if evento_id else "")
        ttk.Entry(frame, textvariable=link_var, width=40).grid(row=2, column=1, sticky=tk.EW, pady=2)

        ttk.Label(frame, text="Descripción:").grid(row=3, column=0, sticky=tk.NW, pady=2)
        # Usar tk.Text para descripción multilínea
        desc_text = tk.Text(frame, height=5, width=30, wrap=tk.WORD) # Aumentar altura
        desc_text.grid(row=3, column=1, sticky=tk.EW, pady=2)
        # Scrollbar para el Text de descripción
        desc_scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=desc_text.yview)
        desc_scroll.grid(row=3, column=2, sticky=tk.NS)
        desc_text['yscrollcommand'] = desc_scroll.set
        if evento_id:
             desc_text.insert(tk.END, datos_evento['descripcion'])

        # --- Opciones de Recordatorio ---
        recordatorio_frame = ttk.LabelFrame(frame, text="Recordatorio", padding="5")
        recordatorio_frame.grid(row=4, column=0, columnspan=2, sticky=tk.EW, pady=10) # Span 2 columnas

        recordatorio_activo_var = tk.IntVar(value=datos_evento['recordatorio_activo'] if evento_id else 0)
        chk_recordatorio = ttk.Checkbutton(recordatorio_frame, text="Activar", variable=recordatorio_activo_var)
        chk_recordatorio.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(recordatorio_frame, text="Minutos antes:").pack(side=tk.LEFT)
        minutos_val = datos_evento['recordatorio_minutos'] if evento_id else 15
        minutos_var = tk.IntVar(value=minutos_val)
        # Validación simple para que solo acepte números
        vcmd = (frame.register(self.validate_int), '%P')
        spin_minutos = tk.Spinbox(recordatorio_frame, from_=1, to=1440, width=5, textvariable=minutos_var, validate='key', validatecommand=vcmd)
        spin_minutos.pack(side=tk.LEFT, padx=5)

        # --- Botones Guardar/Cancelar ---
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=5, column=0, columnspan=3, pady=15) # Span 3 por el scrollbar

        btn_guardar = ttk.Button(button_frame, text="Guardar",
                                 command=lambda: self.guardar_evento(
                                     evento_id, fecha_a_guardar, hora_var.get(), link_var.get(),
                                     desc_text.get("1.0", tk.END).strip(), # Obtener texto del widget Text
                                     recordatorio_activo_var.get(), minutos_var.get(), dialog)
                                 )
        btn_guardar.pack(side=tk.LEFT, padx=5)

        btn_cancelar = ttk.Button(button_frame, text="Cancelar", command=dialog.destroy)
        btn_cancelar.pack(side=tk.LEFT, padx=5)

        # Ajustar tamaño de columna principal
        frame.columnconfigure(1, weight=1)

        # Enfocar el campo de hora al abrir
        entry_hora.focus_set()

        # Esperar hasta que el diálogo se cierre
        self.root.wait_window(dialog)

    def validate_int(self, P):
        """ Función de validación para Spinbox: permite solo dígitos o vacío """
        if P == "" or P.isdigit():
            return True
        else:
            return False

    def parsear_hora(self, hora_str):
        """Intenta parsear la hora desde varios formatos a HH:MM. Devuelve HH:MM, "" o None."""
        if not hora_str or hora_str.isspace():
            return "" # Hora vacía es válida (sin hora específica)

        hora_str = hora_str.strip().replace('.', ':') # Limpiar y normalizar separador

        # Formato HH:MM o H:MM
        match = re.fullmatch(r"(\d{1,2}):(\d{1,2})", hora_str)
        if match:
            h, m = int(match.group(1)), int(match.group(2))
            if 0 <= h <= 23 and 0 <= m <= 59:
                return f"{h:02d}:{m:02d}" # Correcto, formatear a HH:MM

        # Formato H o HH (asume :00)
        match = re.fullmatch(r"(\d{1,2})", hora_str)
        if match:
            h = int(match.group(1))
            if 0 <= h <= 23:
                return f"{h:02d}:00" # Correcto, formatear a HH:00

        return None # Ningún formato válido reconocido

    def guardar_evento(self, evento_id, fecha, hora_str, link, descripcion, recordatorio_activo, recordatorio_minutos, dialog):
        """Guarda un evento nuevo o actualiza uno existente en la DB."""
        # Parsear y validar la hora
        hora_formateada = self.parsear_hora(hora_str)
        if hora_str and hora_formateada is None: # Si se ingresó algo pero no es válido
            messagebox.showerror("Error de Validación",
                                 "Formato de hora inválido.\nIntente HH:MM, H:MM, HH.MM, H.MM o solo la hora (ej: 9, 14).",
                                 parent=dialog)
            return # No continuar

        # Validar descripción no vacía
        if not descripcion:
            messagebox.showerror("Error de Validación", "La descripción no puede estar vacía.", parent=dialog)
            return # No continuar

        success = False
        if evento_id: # Actualizar
            success = db.actualizar_evento(evento_id, fecha, hora_formateada, link, descripcion, recordatorio_activo, recordatorio_minutos)
            if success:
                 messagebox.showinfo("Éxito", "Audiencia actualizada correctamente.", parent=dialog)
            else:
                 messagebox.showerror("Error", "No se pudo actualizar la audiencia.", parent=dialog)
        else: # Agregar
            new_id = db.agregar_evento(fecha, hora_formateada, link, descripcion, recordatorio_activo, recordatorio_minutos)
            if new_id:
                 success = True
                 messagebox.showinfo("Éxito", "Audiencia agregada correctamente.", parent=dialog)
            else:
                 messagebox.showerror("Error", "No se pudo agregar la audiencia.", parent=dialog)

        # Si la operación fue exitosa, cerrar diálogo y refrescar UI
        if success:
            dialog.destroy() # Cerrar diálogo
            self.actualizar_lista_eventos() # Refrescar lista en la ventana principal
            self.marcar_dias_calendario() # Refrescar marcas del calendario


    def editar_evento_seleccionado(self):
        """Abre el diálogo para editar el evento seleccionado en el Treeview."""
        if self.evento_seleccionado_id:
            self.abrir_dialogo_evento(self.evento_seleccionado_id)
        else:
             messagebox.showwarning("Advertencia", "Selecciona una audiencia de la lista para editar.")

    def eliminar_evento_seleccionado(self):
        """Elimina el evento seleccionado tras confirmación."""
        if not self.evento_seleccionado_id:
             messagebox.showwarning("Advertencia", "Selecciona una audiencia de la lista para eliminar.")
             return

        # Obtener descripción CORTA para el mensaje de confirmación desde el Treeview
        try:
            item = self.tree.item(str(self.evento_seleccionado_id))
            desc_corta = item['values'][2] if item and len(item['values']) > 2 else "seleccionada"
        except tk.TclError: # Puede pasar si el item ya no existe por alguna razón
             desc_corta = "seleccionada"


        if messagebox.askyesno("Confirmar Eliminación", f"¿Estás seguro de que quieres eliminar la audiencia '{desc_corta}'?", parent=self.root):
            success = db.eliminar_evento(self.evento_seleccionado_id)
            if success:
                self.actualizar_lista_eventos() # Refrescar lista
                self.marcar_dias_calendario()   # Refrescar marcas del calendario
                self.limpiar_detalles()         # Limpiar vista de detalles
            else:
                messagebox.showerror("Error", "No se pudo eliminar la audiencia.")

    # --- Lógica de Recordatorios (sin cambios respecto a la versión anterior) ---
    def verificar_recordatorios_periodicamente(self):
        """Hilo que revisa periódicamente si hay recordatorios pendientes."""
        print("Hilo de recordatorios iniciado.")
        while not self.stop_event.is_set():
            try:
                ahora = datetime.datetime.now()
                hoy_str = ahora.strftime("%Y-%m-%d")

                # Reiniciar set de recordatorios mostrados si es un nuevo día
                if not hasattr(self, 'ultimo_chequeo_dia') or self.ultimo_chequeo_dia != hoy_str:
                     self.recordatorios_mostrados_hoy = set()
                     self.ultimo_chequeo_dia = hoy_str

                eventos_con_recordatorio = db.obtener_todos_eventos_con_recordatorio()

                for evento in eventos_con_recordatorio:
                    evento_id = evento['id']
                    if not evento['hora']: # Ignorar si no tiene hora
                        continue

                    try:
                        fecha_hora_evento_str = f"{evento['fecha']} {evento['hora']}"
                        fecha_hora_evento = datetime.datetime.strptime(fecha_hora_evento_str, "%Y-%m-%d %H:%M")
                        minutos_antes = evento['recordatorio_minutos']
                        hora_recordatorio = fecha_hora_evento - datetime.timedelta(minutes=minutos_antes)

                        if hora_recordatorio <= ahora < fecha_hora_evento and evento_id not in self.recordatorios_mostrados_hoy:
                             print(f"¡Mostrando recordatorio para evento ID: {evento_id}!")
                             self.root.after(0, self.mostrar_recordatorio, evento) # Ejecutar en hilo principal
                             self.recordatorios_mostrados_hoy.add(evento_id)

                    except ValueError as e:
                         print(f"Error procesando fecha/hora para recordatorio evento ID {evento_id}: {e}")
                    except Exception as e:
                         print(f"Error inesperado procesando recordatorio para evento ID {evento_id}: {e}")

            except Exception as e:
                print(f"Error en el bucle de recordatorios: {e}")

            # Esperar 60 segundos antes de la próxima verificación
            self.stop_event.wait(60)

        print("Hilo de recordatorios detenido.")

    def mostrar_recordatorio(self, evento):
        """Muestra un messagebox como recordatorio."""
        hora_evento = evento['hora']
        descripcion = evento['descripcion']
        link = evento['link']
        # Tomar solo la primera línea de la descripción para la alerta
        desc_alerta = descripcion.split('\n')[0]
        if len(desc_alerta) > 100: desc_alerta = desc_alerta[:97] + '...'

        mensaje = f"RECORDATORIO DE AUDIENCIA\n\nHora: {hora_evento}\n{desc_alerta}"
        # Mostrar link en la alerta solo si existe
        if link:
            link_corto_alerta = link[:60] + '...' if len(link) > 60 else link
            mensaje += f"\n\nLink: {link_corto_alerta}"

        # Usar showwarning para que sea más llamativo.
        messagebox.showwarning("Recordatorio de Audiencia", mensaje, parent=self.root)

    def cerrar_aplicacion(self):
        """Detiene el hilo de recordatorios y cierra la aplicación."""
        print("Cerrando aplicación...")
        self.stop_event.set() # Señal para detener el hilo
        # self.hilo_recordatorios.join(timeout=1.0) # Espera opcional
        self.root.destroy()

# --- Punto de Entrada Principal ---
if __name__ == "__main__":
    root = tk.Tk()
    # Aplicar un tema ttk para un look más moderno (opcional)
    style = ttk.Style(root)
    try:
        # Intentar usar un tema más moderno si está disponible (ej. 'clam', 'alt', 'default')
        # En Windows, 'vista' suele estar disponible y se ve mejor que 'classic'
        if 'vista' in style.theme_names():
             style.theme_use('vista')
        elif 'clam' in style.theme_names():
             style.theme_use('clam')
    except Exception as e:
        print(f"No se pudo aplicar el tema ttk: {e}")

    app = AudienciaApp(root)
    root.mainloop()