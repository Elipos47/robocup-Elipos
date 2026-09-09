# ===========================================================================
# gui_main.py – Interfaccia grafica CustomTkinter per RoboCup Line
# ===========================================================================
# Risoluzione: 800x480 (Raspberry Pi touchscreen)
# Mostra: entrambi i frame video (CSI + USB), telemetria completa
# Calibrazione colori integrata nella GUI
# ===========================================================================

import tkinter as tk
import customtkinter as ctk
import cv2
import numpy as np
from PIL import Image, ImageTk
import threading
import queue
from typing import Optional, Callable

# Configurazione CustomTkinter
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class RoboCupGUI:
    """Interfaccia grafica principale per il robot RoboCup."""
    
    def __init__(self, width=800, height=480):
        """Inizializza la GUI.
        
        Parameters
        ----------
        width : int
            Larghezza finestra
        height : int
            Altezza finestra
        """
        self.width = width
        self.height = height
        
        # Coda per aggiornamenti thread-safe
        self.update_queue = queue.Queue()
        
        # Callback per invio comandi
        self.command_callback: Optional[Callable] = None
        self.calibration_callback: Optional[Callable] = None
        
        # Stato calibrazione
        self.calibration_mode = False
        
        # Inizializza finestra
        self.root = ctk.CTk()
        self.root.title("RoboCup Line - Controllo Robot (FASE 5)")
        self.root.geometry(f"{width}x{height}")
        self.root.resizable(False, False)
        #self.root.attributes('-topmost', True)  # Rimosso - causa problemi di focus
        
        # Frame buffer
        self.csi_frame = None
        self.usb_frame = None
        
        # Flag per shutdown pulito
        self._closed = False
        self._update_after_id = None
        
        # Crea layout
        self._create_layout()
        
        # Avvia loop aggiornamento
        self._schedule_update()
    
    def _create_layout(self):
        """Crea il layout della GUI."""
        # Frame principale diviso in due colonne
        self.main_frame = ctk.CTkFrame(self.root)
        self.main_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Colonna sinistra: Video (60%)
        self.video_frame = ctk.CTkFrame(self.main_frame)
        self.video_frame.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        
        # Frame CSI (telecamera principale)
        self.csi_label = ctk.CTkLabel(self.video_frame, text="CSI Camera")
        self.csi_label.pack(pady=2)
        
        self.csi_canvas = ctk.CTkCanvas(self.video_frame, width=420, height=236, bg="black")
        self.csi_canvas.pack(pady=2)
        
        # Frame USB (telecamera ostacoli)
        self.usb_label = ctk.CTkLabel(self.video_frame, text="USB Camera (Ostacoli)")
        self.usb_label.pack(pady=2)
        
        self.usb_canvas = ctk.CTkCanvas(self.video_frame, width=420, height=140, bg="black")
        self.usb_canvas.pack(pady=2)
        
        # Colonna destra: Telemetria e controlli (40%)
        # Usa un frame scrollabile perché tutto non entra nello schermo
        right_container = ctk.CTkFrame(self.main_frame, width=340)
        right_container.pack(side="right", fill="both", expand=False, padx=2, pady=2)
        right_container.pack_propagate(False)
        
        # Canvas per scrolling
        import tkinter as tk
        canvas = tk.Canvas(right_container, highlightthickness=0, bg="#2B2B2B")
        scrollbar = ctk.CTkScrollbar(right_container, command=canvas.yview)
        
        self.control_frame = ctk.CTkFrame(canvas)
        
        canvas.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.create_window((0, 0), window=self.control_frame, anchor="nw", width=320)
        
        # Aggiorna scrollregion
        def on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        self.control_frame.bind("<Configure>", on_frame_configure)
        
        # Aggiungi scroll con mousewheel
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        # CONTROLLI PRIMA - sempre visibili in alto
        self._create_control_panel()
        
        # Stato principale
        self._create_state_panel()
        
        # Telemetria linea (compatta)
        self._create_line_telemetry()
        
        # Stato colori (compatta)
        self._create_color_panel()
        
        # Stato hardware (compatta)
        self._create_hardware_panel()

        # Pannello Giroscopio (FASE 5)
        self._create_gyro_panel()

        # Stato Smart Recovery
        self._create_recovery_panel()

        # Pannello calibrazione (inizialmente nascosto)
        self._create_calibration_panel()
    
    def _create_state_panel(self):
        """Crea pannello stato principale."""
        self.state_frame = ctk.CTkFrame(self.control_frame)
        self.state_frame.pack(fill="x", padx=5, pady=2)
        
        ctk.CTkLabel(self.state_frame, text="STATO ROBOT", 
                    font=("Arial", 12, "bold")).pack()
        
        self.state_label = ctk.CTkLabel(self.state_frame, text="LINE_DETECTED",
                                       font=("Arial", 14, "bold"),
                                       text_color="green")
        self.state_label.pack(pady=2)
        
        self.command_label = ctk.CTkLabel(self.state_frame, text="CMD: A",
                                         font=("Arial", 16, "bold"))
        self.command_label.pack(pady=2)
    
    def _create_line_telemetry(self):
        """Crea pannello telemetria linea."""
        self.line_frame = ctk.CTkFrame(self.control_frame)
        self.line_frame.pack(fill="x", padx=5, pady=2)
        
        ctk.CTkLabel(self.line_frame, text="TELEMETRIA LINEA", 
                    font=("Arial", 10, "bold")).pack()
        
        # Angolo con gauge
        angle_frame = ctk.CTkFrame(self.line_frame)
        angle_frame.pack(fill="x", padx=5, pady=2)
        
        ctk.CTkLabel(angle_frame, text="Angolo:").pack(side="left", padx=5)
        self.angle_value = ctk.CTkLabel(angle_frame, text="0°", 
                                         font=("Arial", 12, "bold"))
        self.angle_value.pack(side="left", padx=5)
        
        # Barra angolo
        self.angle_bar = ctk.CTkProgressBar(angle_frame, width=100)
        self.angle_bar.pack(side="left", padx=5)
        self.angle_bar.set(0.5)  # Centro
        
        # Gap
        self.gap_frame = ctk.CTkFrame(self.line_frame)
        self.gap_frame.pack(fill="x", padx=5, pady=2)
        
        self.gap_label = ctk.CTkLabel(self.gap_frame, text="GAP: --",
                                      text_color="gray")
        self.gap_label.pack(side="left", padx=5)
        
        # Centroidi
        centroid_frame = ctk.CTkFrame(self.line_frame)
        centroid_frame.pack(fill="x", padx=5, pady=2)
        
        self.centroid_left = ctk.CTkLabel(centroid_frame, text="L: --", 
                                          text_color="gray")
        self.centroid_left.pack(side="left", expand=True)
        
        self.centroid_center = ctk.CTkLabel(centroid_frame, text="C: --",
                                            text_color="gray")
        self.centroid_center.pack(side="left", expand=True)
        
        self.centroid_right = ctk.CTkLabel(centroid_frame, text="R: --",
                                           text_color="gray")
        self.centroid_right.pack(side="left", expand=True)
    
    def _create_color_panel(self):
        """Crea pannello stato colori."""
        self.color_frame = ctk.CTkFrame(self.control_frame)
        self.color_frame.pack(fill="x", padx=5, pady=2)
        
        ctk.CTkLabel(self.color_frame, text="COLORI", 
                    font=("Arial", 10, "bold")).pack()
        
        colors_row = ctk.CTkFrame(self.color_frame)
        colors_row.pack(fill="x", padx=5, pady=2)
        
        self.green_left_indicator = ctk.CTkLabel(colors_row, text="◄ V",
                                                  text_color="gray",
                                                  font=("Arial", 14, "bold"))
        self.green_left_indicator.pack(side="left", expand=True)
        
        self.red_indicator = ctk.CTkLabel(colors_row, text="ROSSO",
                                           text_color="gray",
                                           font=("Arial", 12, "bold"))
        self.red_indicator.pack(side="left", expand=True)
        
        self.green_right_indicator = ctk.CTkLabel(colors_row, text="V ►",
                                                   text_color="gray",
                                                   font=("Arial", 14, "bold"))
        self.green_right_indicator.pack(side="left", expand=True)
    
    def _create_hardware_panel(self):
        """Crea pannello stato hardware (compatto)."""
        self.hardware_frame = ctk.CTkFrame(self.control_frame)
        self.hardware_frame.pack(fill="x", padx=5, pady=1)

        ctk.CTkLabel(self.hardware_frame, text="HARDWARE",
                    font=("Arial", 9, "bold")).pack()

        # Timer generale
        timer_frame = ctk.CTkFrame(self.hardware_frame)
        timer_frame.pack(fill="x", padx=2, pady=1)

        ctk.CTkLabel(timer_frame, text="Timer:", font=("Arial", 9)).pack(side="left", padx=2)
        self.timer_label = ctk.CTkLabel(timer_frame, text="00:00:00",
                                        font=("Arial", 11, "bold"),
                                        text_color="cyan")
        self.timer_label.pack(side="left", padx=2)

        # Distanza e ostacolo sulla stessa riga
        dist_frame = ctk.CTkFrame(self.hardware_frame)
        dist_frame.pack(fill="x", padx=2, pady=1)

        ctk.CTkLabel(dist_frame, text="Dist:", font=("Arial", 9)).pack(side="left", padx=2)
        self.distance_label = ctk.CTkLabel(dist_frame, text="-- cm", font=("Arial", 9))
        self.distance_label.pack(side="left", padx=2)

        self.obstacle_label = ctk.CTkLabel(dist_frame, text="| Ost: NO",
                                           text_color="green", font=("Arial", 9))
        self.obstacle_label.pack(side="left", padx=5)

        # Seriale
        self.serial_label = ctk.CTkLabel(self.hardware_frame, text="Seriale: Disconnesso",
                                         text_color="red", font=("Arial", 9))
        self.serial_label.pack(pady=1)

    def _create_gyro_panel(self):
        """Crea pannello giroscopio BNO085."""
        self.gyro_frame = ctk.CTkFrame(self.control_frame)
        self.gyro_frame.pack(fill="x", padx=5, pady=2)

        ctk.CTkLabel(self.gyro_frame, text="GIROSCOPIO BNO085",
                    font=("Arial", 10, "bold")).pack()

        # Stato connessione
        conn_frame = ctk.CTkFrame(self.gyro_frame)
        conn_frame.pack(fill="x", padx=2, pady=1)
        ctk.CTkLabel(conn_frame, text="Stato:", font=("Arial", 9)).pack(side="left", padx=2)
        self.gyro_conn_label = ctk.CTkLabel(conn_frame, text="Disconnesso",
                                             text_color="red",
                                             font=("Arial", 9, "bold"))
        self.gyro_conn_label.pack(side="left", padx=2)

        # Yaw / Pitch / Roll
        orient_frame = ctk.CTkFrame(self.gyro_frame)
        orient_frame.pack(fill="x", padx=2, pady=1)

        self.gyro_yaw_label = ctk.CTkLabel(orient_frame, text="Y: --",
                                            font=("Arial", 10, "bold"),
                                            text_color="#00BFFF")
        self.gyro_yaw_label.pack(side="left", expand=True)

        self.gyro_pitch_label = ctk.CTkLabel(orient_frame, text="P: --",
                                              font=("Arial", 10),
                                              text_color="#FFD700")
        self.gyro_pitch_label.pack(side="left", expand=True)

        self.gyro_roll_label = ctk.CTkLabel(orient_frame, text="R: --",
                                             font=("Arial", 10),
                                             text_color="#FF69B4")
        self.gyro_roll_label.pack(side="left", expand=True)

        # Calibrazione e livello
        calib_frame = ctk.CTkFrame(self.gyro_frame)
        calib_frame.pack(fill="x", padx=2, pady=1)

        self.gyro_calib_label = ctk.CTkLabel(calib_frame, text="Calib: --",
                                              font=("Arial", 9),
                                              text_color="gray")
        self.gyro_calib_label.pack(side="left", padx=2)

        self.gyro_level_label = ctk.CTkLabel(calib_frame, text="Piano: --",
                                              font=("Arial", 9),
                                              text_color="gray")
        self.gyro_level_label.pack(side="left", padx=10)

        self.gyro_stuck_label = ctk.CTkLabel(calib_frame, text="Gyro Stuck: NO",
                                              font=("Arial", 9),
                                              text_color="green")
        self.gyro_stuck_label.pack(side="left", padx=2)

    def _create_recovery_panel(self):
        """Crea pannello stato recovery."""
        self.recovery_frame = ctk.CTkFrame(self.control_frame)
        self.recovery_frame.pack(fill="x", padx=5, pady=2)

        ctk.CTkLabel(self.recovery_frame, text="SMART RECOVERY",
                    font=("Arial", 10, "bold")).pack()

        # Stato recovery
        self.recovery_state_label = ctk.CTkLabel(self.recovery_frame,
                                                  text="IDLE",
                                                  text_color="gray",
                                                  font=("Arial", 10))
        self.recovery_state_label.pack(pady=1)

        # Tentativo recovery
        self.recovery_attempt_label = ctk.CTkLabel(self.recovery_frame,
                                                    text="Tentativo: --",
                                                    font=("Arial", 9))
        self.recovery_attempt_label.pack(pady=1)

        # Stuck indicator
        self.stuck_label = ctk.CTkLabel(self.recovery_frame,
                                         text="Stuck: NO",
                                         text_color="green",
                                         font=("Arial", 9))
        self.stuck_label.pack(pady=1)
    
    def _create_control_panel(self):
        """Crea pannello controlli con pulsanti."""
        control_frame = ctk.CTkFrame(self.control_frame)
        control_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(control_frame, text="CONTROLLI", 
                    font=("Arial", 10, "bold")).pack()
        
        # Pulsanti
        btn_frame = ctk.CTkFrame(control_frame)
        btn_frame.pack(fill="x", padx=5, pady=5)
        
        self.calib_btn = ctk.CTkButton(btn_frame, text="Calibrazione (C)", 
                                       command=self.show_calibration_window,
                                       fg_color="#2B6CB0")
        self.calib_btn.pack(fill="x", pady=2)
        
        self.exit_btn = ctk.CTkButton(btn_frame, text="Esci (Q)", 
                                      command=self._on_exit,
                                      fg_color="#C53030")
        self.exit_btn.pack(fill="x", pady=2)
        
        # Flag per segnalare uscita
        self.should_exit = False
    
    def _on_exit(self):
        """Gestisce pressione pulsante uscita."""
        self.should_exit = True
    
    def _create_calibration_panel(self):
        """Crea pannello calibrazione (inizialmente nascosto)."""
        self.calibration_window = None
    
    def _create_scrollable_slider_frame(self, parent, params, color_button, color_hover):
        """Crea un frame scrollabile con slider per la calibrazione.
        
        Returns dict {name: (slider, value_label)}
        """
        # Canvas + Scrollbar per permettere lo scroll
        canvas = tk.Canvas(parent, highlightthickness=0, bg="#2B2B2B")
        scrollbar = ctk.CTkScrollbar(parent, command=canvas.yview)
        inner_frame = ctk.CTkFrame(canvas)
        
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas_window = canvas.create_window((0, 0), window=inner_frame, anchor="nw")
        
        def on_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            # Adatta larghezza inner_frame alla larghezza del canvas
            canvas.itemconfig(canvas_window, width=canvas.winfo_width())
        inner_frame.bind("<Configure>", on_configure)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))
        
        # Scroll con mousewheel/touch
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel, add="+")
        
        sliders = {}
        for name, default, min_val, max_val in params:
            row = ctk.CTkFrame(inner_frame)
            row.pack(fill="x", pady=3, padx=5)
            
            label_frame = ctk.CTkFrame(row, fg_color="transparent")
            label_frame.pack(fill="x", pady=(0, 2))
            ctk.CTkLabel(label_frame, text=f"{name}:", font=("Arial", 10)).pack(side="left")
            value_label = ctk.CTkLabel(label_frame, text=str(default), width=40, font=("Arial", 10))
            value_label.pack(side="right")
            
            slider = ctk.CTkSlider(row, from_=min_val, to=max_val,
                                  width=350, height=20,
                                  button_color=color_button,
                                  button_hover_color=color_hover)
            slider.set(default)
            slider.pack(fill="x", padx=5, pady=2)
            
            sliders[name] = (slider, value_label)
            slider.configure(command=lambda v, l=value_label: l.configure(text=str(int(v))))
        
        return sliders

    def show_calibration_window(self):
        """Mostra finestra di calibrazione con scrollbar."""
        try:
            if self.calibration_window is not None and self.calibration_window.winfo_exists():
                self.calibration_window.lift()
                return
            
            self.calibration_window = ctk.CTkToplevel(self.root)
            self.calibration_window.title("Calibrazione Colori")
            self.calibration_window.geometry("600x450")
            self.calibration_window.transient(self.root)
            self.calibration_window.lift()
            self.calibration_window.focus_set()
            
            # Tabview per verde e rosso
            tabview = ctk.CTkTabview(self.calibration_window, height=50)
            tabview.pack(fill="both", expand=True, padx=10, pady=10)
            
            tabview.add("VERDE")
            tabview.add("ROSSO")
            
            # Slider verde con scroll
            green_params = [
                ("H Low", 40, 0, 179),
                ("H High", 80, 0, 179),
                ("S Low", 50, 0, 255),
                ("S High", 255, 0, 255),
                ("V Low", 50, 0, 255),
                ("V High", 255, 0, 255),
            ]
            self.green_sliders = self._create_scrollable_slider_frame(
                tabview.tab("VERDE"), green_params, "#2B6CB0", "#1a4a7a")
            
            # Slider rosso con scroll
            red_params = [
                ("1 H Low", 0, 0, 179),
                ("1 H High", 10, 0, 179),
                ("2 H Low", 170, 0, 179),
                ("2 H High", 180, 0, 179),
                ("S Low", 100, 0, 255),
                ("S High", 255, 0, 255),
            ]
            self.red_sliders = self._create_scrollable_slider_frame(
                tabview.tab("ROSSO"), red_params, "#C53030", "#9a2525")
            
            # Pulsanti
            btn_frame = ctk.CTkFrame(self.calibration_window)
            btn_frame.pack(fill="x", padx=10, pady=5)
            
            ctk.CTkButton(btn_frame, text="Salva", 
                         command=self._save_calibration).pack(side="left", padx=5)
            ctk.CTkButton(btn_frame, text="Carica Default",
                         command=self._load_default_calibration).pack(side="left", padx=5)
            ctk.CTkButton(btn_frame, text="Chiudi",
                         command=self.calibration_window.destroy).pack(side="right", padx=5)
        except Exception as e:
            print(f"Errore calibrazione: {e}")
            import traceback
            traceback.print_exc()
    
    def _save_calibration(self):
        """Salva calibrazione."""
        if self.calibration_callback:
            green_values = {}
            for name, (slider, _) in self.green_sliders.items():
                green_values[name] = int(slider.get())
            
            red_values = {}
            for name, (slider, _) in self.red_sliders.items():
                red_values[name] = int(slider.get())
            
            self.calibration_callback(green_values, red_values)
    
    def _load_default_calibration(self):
        """Carica valori default."""
        # Resetta slider ai valori default
        defaults_green = {"H Low": 40, "H High": 80, "S Low": 50, "S High": 255, "V Low": 50, "V High": 255}
        for name, default_val in defaults_green.items():
            if name in self.green_sliders:
                self.green_sliders[name][0].set(default_val)
                self.green_sliders[name][1].configure(text=str(default_val))
        
        defaults_red = {"1 H Low": 0, "1 H High": 10, "2 H Low": 170, "2 H High": 180, "S Low": 100, "S High": 255}
        for name, default_val in defaults_red.items():
            if name in self.red_sliders:
                self.red_sliders[name][0].set(default_val)
                self.red_sliders[name][1].configure(text=str(default_val))
    
    def _schedule_update(self):
        """Programma il prossimo aggiornamento GUI."""
        if self._closed:
            return
        self._update_after_id = self.root.after(50, self._update_gui)  # 20 FPS
    
    def _update_gui(self):
        """Aggiorna la GUI con i dati dalla coda."""
        if self._closed:
            return
        try:
            # Processa tutti i messaggi nella coda
            while not self.update_queue.empty():
                msg = self.update_queue.get_nowait()
                self._process_update(msg)
        except queue.Empty:
            pass
        
        # Aggiorna frame video
        self._update_video_frames()
        
        # Programma prossimo aggiornamento
        self._schedule_update()
    
    def _process_update(self, msg):
        """Processa un messaggio di aggiornamento."""
        msg_type = msg.get('type')
        
        if msg_type == 'state':
            self._update_state(msg)
        elif msg_type == 'telemetry':
            self._update_telemetry(msg)
        elif msg_type == 'hardware':
            self._update_hardware(msg)
    
    def _update_state(self, msg):
        """Aggiorna stato visualizzato."""
        state = msg.get('state', 'UNKNOWN')
        command = msg.get('command', 'S')
        
        self.state_label.configure(text=state)
        self.command_label.configure(text=f"CMD: {command}")
        
        # Colore in base allo stato
        state_colors = {
            'LINE_DETECTED': 'green',
            'GAP_DETECTED': 'yellow',
            'GAP_AVOID': 'orange',
            'OBSTACLE_DETECTED': 'red',
            'OBSTACLE_AVOID': 'red',
            'STOP': 'red',
        }
        self.state_label.configure(text_color=state_colors.get(state, 'white'))
    
    def _update_telemetry(self, msg):
        """Aggiorna telemetria."""
        # Angolo
        angle = msg.get('angle', 0)
        self.angle_value.configure(text=f"{int(angle)}°")
        # Normalizza per progress bar (0-1, centro=0.5)
        angle_normalized = (angle + 180) / 360
        self.angle_bar.set(max(0, min(1, angle_normalized)))
        
        # Gap
        gap_detected = msg.get('gap_detected', False)
        gap_angle = msg.get('gap_angle', -181)
        if gap_detected:
            self.gap_label.configure(text=f"GAP: {int(gap_angle)}°", 
                                    text_color="yellow")
        else:
            self.gap_label.configure(text="GAP: --", text_color="gray")
        
        # Centroidi
        has_left = msg.get('has_left', False)
        has_center = msg.get('has_center', False)
        has_right = msg.get('has_right', False)
        
        self.centroid_left.configure(text="L: OK" if has_left else "L: --",
                                     text_color="green" if has_left else "gray")
        self.centroid_center.configure(text="C: OK" if has_center else "C: --",
                                       text_color="green" if has_center else "gray")
        self.centroid_right.configure(text="R: OK" if has_right else "R: --",
                                      text_color="green" if has_right else "gray")
        
        # Colori
        green_left = msg.get('green_left', False)
        green_right = msg.get('green_right', False)
        red_detected = msg.get('red_detected', False)
        
        self.green_left_indicator.configure(
            text_color="green" if green_left else "gray")
        self.red_indicator.configure(
            text_color="red" if red_detected else "gray")
        self.green_right_indicator.configure(
            text_color="green" if green_right else "gray")
    
    def _update_hardware(self, msg):
        """Aggiorna stato hardware."""
        # Timer generale
        elapsed = msg.get('elapsed_time', 0)
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        self.timer_label.configure(text=f"{hours:02d}:{minutes:02d}:{seconds:02d}")

        # Distanza
        distance = msg.get('distance', 999)
        if distance != 999:
            self.distance_label.configure(text=f"{int(distance)} cm")
        else:
            self.distance_label.configure(text="-- cm")

        # Ostacolo
        obstacle = msg.get('obstacle', False)
        self.obstacle_label.configure(
            text="Ostacolo: SÌ" if obstacle else "Ostacolo: NO",
            text_color="red" if obstacle else "green")

        # Seriale
        serial_connected = msg.get('serial_connected', False)
        serial_port = msg.get('serial_port', 'N/A')
        self.serial_label.configure(
            text=f"Seriale: {serial_port}" if serial_connected else "Seriale: Disconnesso",
            text_color="green" if serial_connected else "red")

        # ── Giroscopio ──────────────────────────────────────────────
        gyro_connected = msg.get('gyro_connected', False)
        gyro_simulation = msg.get('gyro_simulation', True)
        gyro_yaw = msg.get('gyro_yaw', 0.0)
        gyro_pitch = msg.get('gyro_pitch', 0.0)
        gyro_roll = msg.get('gyro_roll', 0.0)
        gyro_calibrated = msg.get('gyro_calibrated', False)
        gyro_calibration = msg.get('gyro_calibration', (0, 0, 0, 0))
        gyro_stuck = msg.get('gyro_stuck', False)
        gyro_level = msg.get('gyro_level', False)

        # Stato connessione giroscopio
        if gyro_connected and not gyro_simulation:
            self.gyro_conn_label.configure(text="Hardware ✓", text_color="green")
        elif gyro_connected and gyro_simulation:
            self.gyro_conn_label.configure(text="Simulazione", text_color="yellow")
        else:
            self.gyro_conn_label.configure(text="Disconnesso", text_color="red")

        # Orientamento
        self.gyro_yaw_label.configure(text=f"Y: {gyro_yaw:.1f}°")
        self.gyro_pitch_label.configure(text=f"P: {gyro_pitch:.1f}°")
        self.gyro_roll_label.configure(text=f"R: {gyro_roll:.1f}°")

        # Calibrazione (sys, gyro, accel, mag — 3 = calibrato)
        if isinstance(gyro_calibration, (list, tuple)) and len(gyro_calibration) >= 4:
            s, g, a, m = gyro_calibration
            calib_text = f"Calib: S{s} G{g} A{a} M{m}"
        else:
            calib_text = "Calib: --"
        calib_color = "green" if gyro_calibrated else "orange" if gyro_connected else "gray"
        self.gyro_calib_label.configure(text=calib_text, text_color=calib_color)

        # Livello
        self.gyro_level_label.configure(
            text="Piano: SÌ" if gyro_level else "Piano: NO",
            text_color="green" if gyro_level else "orange")

        # Stuck via giroscopio
        self.gyro_stuck_label.configure(
            text="Gyro Stuck: SÌ!" if gyro_stuck else "Gyro Stuck: NO",
            text_color="red" if gyro_stuck else "green")

        # ── Recovery ────────────────────────────────────────────────
        recovery_state = msg.get('recovery_state', 'IDLE')
        recovery_attempt = msg.get('recovery_attempt', 0)
        is_stuck = msg.get('is_stuck', False)

        # Aggiorna recovery state label
        state_colors = {
            'IDLE': 'gray',
            'BACKUP': 'orange',
            'JIGGLE_RIGHT': 'yellow',
            'JIGGLE_LEFT': 'yellow',
            'WIDE_SEARCH': 'yellow',
            'FINAL_BACKUP': 'orange',
            'FAILED': 'red'
        }
        self.recovery_state_label.configure(
            text=recovery_state,
            text_color=state_colors.get(recovery_state, 'white'))

        # Aggiorna tentativo
        if recovery_state != 'IDLE':
            self.recovery_attempt_label.configure(
                text=f"Tentativo: {recovery_attempt}/4")
        else:
            self.recovery_attempt_label.configure(text="Tentativo: --")

        # Aggiorna stuck indicator (image similarity)
        self.stuck_label.configure(
            text="STUCK!" if is_stuck else "Stuck: NO",
            text_color="red" if is_stuck else "green")
    
    def _update_video_frames(self):
        """Aggiorna i frame video."""
        # CSI Frame
        if self.csi_frame is not None:
            self._update_canvas(self.csi_canvas, self.csi_frame, 420, 236)
        
        # USB Frame
        if self.usb_frame is not None:
            self._update_canvas(self.usb_canvas, self.usb_frame, 420, 140)
    
    def _update_canvas(self, canvas, frame, target_width, target_height):
        """Aggiorna canvas con frame ridimensionato."""
        try:
            # Ridimensiona frame
            h, w = frame.shape[:2]
            scale = min(target_width / w, target_height / h)
            new_w, new_h = int(w * scale), int(h * scale)
            
            resized = cv2.resize(frame, (new_w, new_h))
            
            # Converti per Tkinter
            if len(resized.shape) == 2:  # Grayscale
                resized = cv2.cvtColor(resized, cv2.COLOR_GRAY2RGB)
            elif resized.shape[2] == 3:  # BGR
                resized = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            
            img = Image.fromarray(resized)
            imgtk = ImageTk.PhotoImage(image=img)
            
            # Centra nel canvas
            x = (target_width - new_w) // 2
            y = (target_height - new_h) // 2
            
            canvas.delete("all")
            canvas.create_image(x, y, anchor="nw", image=imgtk)
            canvas.image = imgtk  # Keep reference
        except Exception as e:
            pass
    
    def queue_update(self, msg_type: str, **kwargs):
        """Aggiunge un aggiornamento alla coda (thread-safe).
        
        Parameters
        ----------
        msg_type : str
            Tipo di messaggio: 'state', 'telemetry', 'hardware'
        **kwargs
            Dati da aggiornare
        """
        msg = {'type': msg_type, **kwargs}
        self.update_queue.put(msg)
    
    def set_csi_frame(self, frame: np.ndarray):
        """Imposta il frame CSI da visualizzare."""
        self.csi_frame = frame.copy() if frame is not None else None
    
    def set_usb_frame(self, frame: np.ndarray):
        """Imposta il frame USB da visualizzare."""
        self.usb_frame = frame.copy() if frame is not None else None
    
    def run(self):
        """Avvia il loop principale della GUI (bloccante)."""
        self.root.mainloop()
    
    def update(self):
        """Aggiorna la GUI senza bloccare (da chiamare nel loop principale)."""
        if self._closed:
            return
        try:
            self.root.update()
        except tk.TclError:
            # Finestra chiusa
            self._closed = True
    
    def close(self):
        """Chiude la GUI in modo pulito."""
        if self._closed:
            return
        self._closed = True
        
        # Sopprimi TUTTI gli errori da after() pendenti di customtkinter
        # (update, check_dpi_scaling, _click_animation, ecc.)
        # Questi callback interni non possiamo cancellarli singolarmente,
        # quindi sovrascriviamo il gestore errori di Tkinter.
        def _suppress_errors(*args):
            pass  # Ignora tutti gli errori durante la chiusura
        
        try:
            self.root.report_callback_exception = _suppress_errors
        except Exception:
            pass
        
        # Cancella il nostro callback after()
        try:
            if self._update_after_id is not None:
                self.root.after_cancel(self._update_after_id)
                self._update_after_id = None
        except Exception:
            pass
        
        try:
            if self.calibration_window and self.calibration_window.winfo_exists():
                self.calibration_window.destroy()
        except Exception:
            pass
        
        try:
            self.root.quit()
            self.root.update_idletasks()
            self.root.destroy()
        except Exception:
            pass


# Istanza globale
gui = None

def create_gui(width=800, height=480):
    """Crea l'istanza GUI globale."""
    global gui
    gui = RoboCupGUI(width, height)
    return gui
