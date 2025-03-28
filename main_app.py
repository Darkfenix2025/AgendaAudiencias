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
from PIL import Image, ImageTk # Para imagen del logo

# --- Helper para Rutas Relativas (PyInstaller) ---
def resource_path(relative_path):
    """ Obtiene la ruta absoluta al recurso, funciona para desarrollo y para PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)
# --- Fin Helper ---


class AudienciaApp:
    def __init__(self, root):
        self.root = root
        # --- Título de la Ventana Actualizado ---
        self.root.title("Gestor de Audiencias        Powered by Legal-IT-Ø")
        # self.root.geometry("850x650") # Ajusta tamaño inicial si es necesario

        # --- Inicializar DB ---
        db.inicializar_db()

        # --- Variables ---
        self.fecha_seleccionada = datetime.date.today().strftime("%Y-%m-%d")
        self.evento_seleccionado_id = None
        self.recordatorios_mostrados_hoy = set()
        self.logo_image_tk = None # Para mantener referencia a la imagen del logo

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
        # --- Frame Principal ---
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Frame Izquierdo (Calendario, Botones y Logo) ---
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10), anchor=tk.NW)

        # Calendario
        self.cal = Calendar(left_frame, selectmode='day',
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
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X)
        add_btn = ttk.Button(btn_frame, text="Agregar Audiencia", command=self.abrir_dialogo_evento)
        add_btn.pack(fill=tk.X, pady=5)

        # --- Logo Debajo del Botón ---
        try:
            logo_frame = ttk.LabelFrame(left_frame) #, text="Logo")
            logo_frame.pack(pady=(15, 5), padx=5, fill=tk.X)

            logo_path = resource_path("assets/logoLegalito01.png") # Nombre de tu archivo PNG
            #print(f"DEBUG: Intentando cargar logo desde: {logo_path}") # Debug
            logo_image_pil = Image.open(logo_path)

            # Redimensionar (ajusta max_width según necesites)
            max_width = 200
            ratio = min(max_width / logo_image_pil.width, 1)
            new_width = int(logo_image_pil.width * ratio)
            new_height = int(logo_image_pil.height * ratio)
            logo_image_pil = logo_image_pil.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Convertir y guardar referencia
            self.logo_image_tk = ImageTk.PhotoImage(logo_image_pil)

            logo_label = ttk.Label(logo_frame, image=self.logo_image_tk)
            logo_label.pack(pady=5, padx=5)

        except FileNotFoundError:
            print(f"Advertencia: No se encontró el logo en '{logo_path}'.")
            error_label = ttk.Label(left_frame, text="Logo no encontrado")
            error_label.pack(pady=(15, 5), padx=5)
        except Exception as e:
            print(f"Error al cargar el logo: {e}")
            error_label = ttk.Label(left_frame, text="Error al cargar logo")
            error_label.pack(pady=(15, 5), padx=5)
        # --- Fin Logo ---

        # --- Frame Derecho (Lista de Eventos y Detalles) ---
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Etiqueta Fecha Seleccionada
        self.lbl_fecha = ttk.Label(right_frame, text=f"Audiencias para: {self.fecha_seleccionada}", font=("Arial", 12, "bold"))
        self.lbl_fecha.pack(pady=(0, 5), anchor=tk.W)

        # Frame para Treeview con Scrollbar
        tree_frame = ttk.Frame(right_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        cols = ("ID", "Hora", "Descripción Corta", "Link Corto")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show='headings', selectmode="browse")
        # ... (configuración encabezados y columnas) ...
        self.tree.heading("ID", text="ID")
        self.tree.heading("Hora", text="Hora")
        self.tree.heading("Descripción Corta", text="Descripción")
        self.tree.heading("Link Corto", text="Link")
        self.tree.column("ID", width=40, stretch=tk.NO, anchor=tk.CENTER)
        self.tree.column("Hora", width=60, stretch=tk.NO, anchor=tk.CENTER)
        self.tree.column("Descripción Corta", width=300, stretch=True)
        self.tree.column("Link Corto", width=150, stretch=True)

        scrollbar_y = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar_y.set)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.tree.bind('<<TreeviewSelect>>', self.on_tree_select)
        self.tree.bind("<Double-1>", self.abrir_link_seleccionado)

        # Frame para Botones Edición/Eliminación/Compartir
        edit_actions_frame = ttk.Frame(right_frame)
        edit_actions_frame.pack(fill=tk.X, pady=(5, 5))

        self.edit_btn = ttk.Button(edit_actions_frame, text="Editar", command=self.editar_evento_seleccionado, state=tk.DISABLED)
        self.edit_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.delete_btn = ttk.Button(edit_actions_frame, text="Eliminar", command=self.eliminar_evento_seleccionado, state=tk.DISABLED)
        self.delete_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.share_btn = ttk.Button(edit_actions_frame, text="Compartir", command=self.mostrar_menu_compartir, state=tk.DISABLED)
        self.share_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.open_link_btn = ttk.Button(edit_actions_frame, text="Abrir Link", command=self.abrir_link_seleccionado, state=tk.DISABLED)
        self.open_link_btn.pack(side=tk.RIGHT)

        # Área de Texto para Detalles Completos
        details_frame = ttk.LabelFrame(right_frame, text="Detalles Completos", padding="5")
        details_frame.pack(fill=tk.X, pady=(0, 5), side=tk.BOTTOM)

        details_text_frame = ttk.Frame(details_frame)
        details_text_frame.pack(fill=tk.X, expand=True)
        self.details_text = tk.Text(details_text_frame, height=6, wrap=tk.WORD, state=tk.DISABLED, borderwidth=0, relief="flat", background=self.root.cget('bg'))
        details_scrollbar = ttk.Scrollbar(details_text_frame, orient=tk.VERTICAL, command=self.details_text.yview)
        self.details_text.configure(yscrollcommand=details_scrollbar.set)
        details_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.details_text.pack(side=tk.LEFT, fill=tk.X, expand=True)


    # --- RESTO DE MÉTODOS DE LA CLASE (sin cambios respecto a la versión completa anterior) ---

    def marcar_dias_calendario(self):
        self.cal.calevent_remove(tag='evento')
        fechas_eventos = db.obtener_fechas_con_eventos()
        for fecha_str in fechas_eventos:
            try:
                fecha_obj = datetime.datetime.strptime(fecha_str, "%Y-%m-%d").date()
                self.cal.calevent_create(fecha_obj, 'Audiencia', tags='evento')
            except ValueError: print(f"Error parsear fecha '{fecha_str}' calendario.")
            except Exception as e: print(f"Error crear evento calendario {fecha_str}: {e}")

    def actualizar_lista_eventos(self, event=None):
        self.fecha_seleccionada = self.cal.get_date()
        self.lbl_fecha.config(text=f"Audiencias para: {self.fecha_seleccionada}")
        for item in self.tree.get_children(): self.tree.delete(item)
        eventos = db.obtener_eventos_por_fecha(self.fecha_seleccionada)
        for evento in eventos:
            hora = evento.get('hora', '--:--') if evento.get('hora') else "--:--"
            desc_completa = evento.get('descripcion', "")
            desc_corta = desc_completa.split('\n')[0];
            if len(desc_corta) > 60: desc_corta = desc_corta[:57] + '...'
            link_completo = evento.get('link', "")
            link_corto = link_completo[:40] + '...' if len(link_completo) > 40 else link_completo
            self.tree.insert("", tk.END, values=(evento['id'], hora, desc_corta, link_corto), iid=str(evento['id']))
        self.deshabilitar_botones_edicion()
        self.limpiar_detalles()

    def cargar_eventos_fecha_actual(self):
        self.actualizar_lista_eventos()

    def on_tree_select(self, event=None):
        selected_items = self.tree.selection()
        if selected_items:
            try:
                self.evento_seleccionado_id = int(selected_items[0])
                self.habilitar_botones_edicion()
                self.mostrar_detalles_evento(self.evento_seleccionado_id)
            except (ValueError, tk.TclError) as e:
                print(f"Error seleccionar evento: {e}")
                self.evento_seleccionado_id = None; self.deshabilitar_botones_edicion(); self.limpiar_detalles()
        else:
            self.evento_seleccionado_id = None; self.deshabilitar_botones_edicion(); self.limpiar_detalles()

    def mostrar_detalles_evento(self, evento_id):
        evento = db.obtener_evento_por_id(evento_id)
        self.details_text.config(state=tk.NORMAL); self.details_text.delete('1.0', tk.END)
        if evento:
            hora = evento.get('hora') if evento.get('hora') else "No especificada"
            link = evento.get('link') if evento.get('link') else "No especificado"
            rec_act = "Sí" if evento.get('recordatorio_activo') else "No"
            rec_min = f" ({evento.get('recordatorio_minutos', 15)} min antes)" if evento.get('recordatorio_activo') else ""
            texto = f"Fecha: {evento.get('fecha', 'N/A')}\nHora: {hora}\n\n"
            texto += f"Descripción:\n{evento.get('descripcion', 'N/A')}\n\n"
            texto += f"Link:\n{link}\n\n"
            texto += f"Recordatorio: {rec_act}{rec_min}"
            self.details_text.insert('1.0', texto)
        else: self.details_text.insert('1.0', "No se pudieron cargar los detalles.")
        self.details_text.config(state=tk.DISABLED)

    def limpiar_detalles(self):
        self.details_text.config(state=tk.NORMAL); self.details_text.delete('1.0', tk.END); self.details_text.config(state=tk.DISABLED)

    def habilitar_botones_edicion(self):
        self.edit_btn.config(state=tk.NORMAL); self.delete_btn.config(state=tk.NORMAL); self.share_btn.config(state=tk.NORMAL)
        if self.evento_seleccionado_id:
             evento = db.obtener_evento_por_id(self.evento_seleccionado_id)
             self.open_link_btn.config(state=tk.NORMAL if evento and evento.get('link') else tk.DISABLED)
        else: self.open_link_btn.config(state=tk.DISABLED)

    def deshabilitar_botones_edicion(self):
        self.edit_btn.config(state=tk.DISABLED); self.delete_btn.config(state=tk.DISABLED)
        self.share_btn.config(state=tk.DISABLED); self.open_link_btn.config(state=tk.DISABLED)

    def abrir_link_seleccionado(self, event=None):
        if not self.evento_seleccionado_id: return
        evento = db.obtener_evento_por_id(self.evento_seleccionado_id)
        link = evento.get('link') if evento else None
        if link:
            try: print(f"Abriendo link: {link}"); webbrowser.open_new_tab(link)
            except Exception as e: messagebox.showerror("Error", f"No se pudo abrir el link:\n{e}")
        else: messagebox.showinfo("Información", "Este evento no tiene un link asociado.")

    def _formatear_texto_para_compartir(self, evento):
        if not evento: return "Error: Evento no encontrado."
        texto = f"Detalles Audiencia:\n-------------------------\n"
        texto += f"Fecha: {evento.get('fecha', 'N/A')}\n"
        if evento.get('hora'): texto += f"Hora: {evento['hora']}\n"
        texto += f"Descripción: {evento.get('descripcion', 'N/A')}\n"
        if evento.get('link'): texto += f"Link: {evento['link']}\n"
        texto += f"-------------------------"
        return texto

    def _compartir_por_email(self):
        if not self.evento_seleccionado_id: return
        evento = db.obtener_evento_por_id(self.evento_seleccionado_id)
        if not evento: messagebox.showerror("Error", "No se pudo obtener info del evento."); return
        desc_corta = evento.get('descripcion', 'Evento').split('\n')[0][:30]
        asunto = urllib.parse.quote(f"Detalles Audiencia: {evento.get('fecha', '')} - {desc_corta}")
        cuerpo = urllib.parse.quote(self._formatear_texto_para_compartir(evento))
        try: print(f"Abriendo Mail"); webbrowser.open(f"mailto:?subject={asunto}&body={cuerpo}")
        except Exception as e: messagebox.showerror("Error", f"No se pudo abrir cliente de correo:\n{e}", parent=self.root)

    def _compartir_por_whatsapp(self):
        if not self.evento_seleccionado_id: return
        evento = db.obtener_evento_por_id(self.evento_seleccionado_id)
        if not evento: messagebox.showerror("Error", "No se pudo obtener info del evento."); return
        texto = urllib.parse.quote(self._formatear_texto_para_compartir(evento))
        try: print(f"Abriendo WhatsApp"); webbrowser.open(f"https://wa.me/?text={texto}")
        except Exception as e: messagebox.showerror("Error", f"No se pudo abrir WhatsApp:\n{e}", parent=self.root)

    def mostrar_menu_compartir(self):
        if not self.evento_seleccionado_id: messagebox.showwarning("Advertencia", "Selecciona una audiencia.", parent=self.root); return
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Compartir por Email", command=self._compartir_por_email)
        menu.add_command(label="Compartir por WhatsApp", command=self._compartir_por_whatsapp)
        try:
            widget = self.share_btn; x = widget.winfo_rootx(); y = widget.winfo_rooty() + widget.winfo_height()
            menu.tk_popup(x, y)
        except Exception as e: print(f"Error mostrar menú: {e}"); menu.tk_popup(self.root.winfo_pointerx(), self.root.winfo_pointery())
        finally: menu.grab_release()

    def abrir_dialogo_evento(self, evento_id=None):
        dialog = tk.Toplevel(self.root)
        datos_evento = db.obtener_evento_por_id(evento_id) if evento_id else {}
        if evento_id and not datos_evento: messagebox.showerror("Error", "No se pudo cargar info.", parent=dialog); dialog.destroy(); return
        dialog.title("Editar Audiencia" if evento_id else "Agregar Audiencia")
        dialog.geometry("450x380"); dialog.resizable(False, False); dialog.transient(self.root); dialog.grab_set()
        frame = ttk.Frame(dialog, padding="15"); frame.pack(expand=True, fill=tk.BOTH)
        # --- Campos ---
        fecha_val = datos_evento.get('fecha') if evento_id else self.fecha_seleccionada
        ttk.Label(frame, text="Fecha:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Label(frame, text=fecha_val).grid(row=0, column=1, sticky=tk.W, pady=2)
        ttk.Label(frame, text="Hora:").grid(row=1, column=0, sticky=tk.W, pady=2)
        hora_var = tk.StringVar(value=datos_evento.get('hora', '')); entry_hora = ttk.Entry(frame, textvariable=hora_var, width=40); entry_hora.grid(row=1, column=1, sticky=tk.EW, pady=2)
        ttk.Label(frame, text="Link:").grid(row=2, column=0, sticky=tk.W, pady=2)
        link_var = tk.StringVar(value=datos_evento.get('link', '')); ttk.Entry(frame, textvariable=link_var, width=40).grid(row=2, column=1, sticky=tk.EW, pady=2)
        ttk.Label(frame, text="Descripción:").grid(row=3, column=0, sticky=tk.NW, pady=2)
        desc_text = tk.Text(frame, height=5, width=30, wrap=tk.WORD); desc_text.grid(row=3, column=1, sticky=tk.NSEW, pady=2)
        desc_scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=desc_text.yview); desc_scroll.grid(row=3, column=2, sticky=tk.NS); desc_text['yscrollcommand'] = desc_scroll.set
        if evento_id: desc_text.insert(tk.END, datos_evento.get('descripcion', ''))
        # --- Recordatorio ---
        rec_frame = ttk.LabelFrame(frame, text="Recordatorio", padding="5"); rec_frame.grid(row=4, column=0, columnspan=3, sticky=tk.EW, pady=10)
        rec_act_var = tk.IntVar(value=datos_evento.get('recordatorio_activo', 0)); ttk.Checkbutton(rec_frame, text="Activar", variable=rec_act_var).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(rec_frame, text="Minutos antes:").pack(side=tk.LEFT)
        rec_min_var = tk.IntVar(value=datos_evento.get('recordatorio_minutos', 15)); vcmd = (frame.register(self.validate_int), '%P'); ttk.Spinbox(rec_frame, from_=1, to=1440, width=5, textvariable=rec_min_var, validate='key', validatecommand=vcmd).pack(side=tk.LEFT, padx=5)
        # --- Botones ---
        btn_frame = ttk.Frame(frame); btn_frame.grid(row=5, column=0, columnspan=3, pady=15)
        ttk.Button(btn_frame, text="Guardar", command=lambda: self.guardar_evento(evento_id, fecha_val, hora_var.get(), link_var.get(), desc_text.get("1.0", tk.END).strip(), rec_act_var.get(), rec_min_var.get(), dialog)).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancelar", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        # --- Configuración Grid y Focus ---
        frame.columnconfigure(1, weight=1); frame.rowconfigure(3, weight=1); entry_hora.focus_set()
        self.root.wait_window(dialog)

    def validate_int(self, P): return P == "" or P.isdigit()

    def parsear_hora(self, hora_str):
        if not hora_str or hora_str.isspace(): return ""
        hora_str = hora_str.strip().replace('.', ':')
        m_hm = re.fullmatch(r"(\d{1,2}):(\d{1,2})", hora_str)
        if m_hm: h, m = int(m_hm.group(1)), int(m_hm.group(2)); return f"{h:02d}:{m:02d}" if 0<=h<=23 and 0<=m<=59 else None
        m_h = re.fullmatch(r"(\d{1,2})", hora_str)
        if m_h: h = int(m_h.group(1)); return f"{h:02d}:00" if 0<=h<=23 else None
        return None

    def guardar_evento(self, evento_id, fecha, hora_str, link, descripcion, rec_act, rec_min, dialog):
        hora_fmt = self.parsear_hora(hora_str)
        if hora_str and hora_fmt is None: messagebox.showerror("Error Validación", "Hora inválida.", parent=dialog); return
        if not descripcion: messagebox.showerror("Error Validación", "Descripción vacía.", parent=dialog); return
        success = False
        if evento_id: success = db.actualizar_evento(evento_id, fecha, hora_fmt, link, descripcion, rec_act, rec_min)
        else: new_id = db.agregar_evento(fecha, hora_fmt, link, descripcion, rec_act, rec_min); success = bool(new_id)
        if success:
            msg = "Actualizada" if evento_id else "Agregada"; messagebox.showinfo("Éxito", f"Audiencia {msg}.", parent=dialog)
            dialog.destroy(); self.actualizar_lista_eventos(); self.marcar_dias_calendario()
        else: msg = "actualizar" if evento_id else "agregar"; messagebox.showerror("Error", f"No se pudo {msg}.", parent=dialog)

    def editar_evento_seleccionado(self):
        if self.evento_seleccionado_id: self.abrir_dialogo_evento(self.evento_seleccionado_id)
        else: messagebox.showwarning("Advertencia", "Selecciona audiencia a editar.")

    def eliminar_evento_seleccionado(self):
        if not self.evento_seleccionado_id: messagebox.showwarning("Advertencia", "Selecciona audiencia a eliminar."); return
        try: desc_corta = self.tree.item(str(self.evento_seleccionado_id))['values'][2]
        except: desc_corta = "seleccionada"
        if messagebox.askyesno("Confirmar", f"Eliminar '{desc_corta}'?", parent=self.root):
            if db.eliminar_evento(self.evento_seleccionado_id): self.actualizar_lista_eventos(); self.marcar_dias_calendario(); self.limpiar_detalles()
            else: messagebox.showerror("Error", "No se pudo eliminar.")

    def verificar_recordatorios_periodicamente(self):
        print("Hilo recordatorios iniciado.")
        while not self.stop_event.is_set():
            try:
                ahora = datetime.datetime.now(); hoy = ahora.strftime("%Y-%m-%d")
                if not hasattr(self, 'dia_chk') or self.dia_chk != hoy: self.rec_mostrados = set(); self.dia_chk = hoy
                eventos = db.obtener_todos_eventos_con_recordatorio()
                for ev in eventos:
                    if not ev.get('hora'): continue
                    ev_id = ev['id']
                    try:
                        t_ev = datetime.datetime.strptime(f"{ev['fecha']} {ev['hora']}", "%Y-%m-%d %H:%M")
                        t_rec = t_ev - datetime.timedelta(minutes=ev.get('recordatorio_minutos', 15))
                        if t_rec <= ahora < t_ev and ev_id not in self.rec_mostrados:
                            print(f"Mostrar recordatorio ID: {ev_id}")
                            self.root.after(0, self.mostrar_recordatorio, ev); self.rec_mostrados.add(ev_id)
                    except Exception as e: print(f"Error proc. recordatorio {ev_id}: {e}")
            except Exception as e: print(f"Error bucle recordatorios: {e}")
            self.stop_event.wait(60)
        print("Hilo recordatorios detenido.")

    def mostrar_recordatorio(self, evento):
        desc = evento.get('descripcion', '').split('\n')[0]; desc = desc[:97] + '...' if len(desc) > 100 else desc
        link = evento.get('link', ''); link = link[:60] + '...' if len(link) > 60 else link
        msg = f"RECORDATORIO AUDIENCIA\n\nHora: {evento.get('hora', '')}\n{desc}"
        if link: msg += f"\n\nLink: {link}"
        messagebox.showwarning("Recordatorio de Audiencia", msg, parent=self.root)

    def cerrar_aplicacion(self):
        print("Cerrando aplicación..."); self.stop_event.set(); self.root.destroy()

# --- Punto de Entrada Principal ---
if __name__ == "__main__":
    root = tk.Tk()
    style = ttk.Style(root)
    themes = style.theme_names()
    if 'vista' in themes: style.theme_use('vista')
    elif 'clam' in themes: style.theme_use('clam')
    elif 'alt' in themes: style.theme_use('alt')
    app = AudienciaApp(root)
    root.mainloop()