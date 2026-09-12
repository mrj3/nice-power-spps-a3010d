#!/usr/bin/env python3
import csv
import os
import queue
import threading
import time
from collections import deque
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import serial
import serial.tools.list_ports

try:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
except ImportError:
    Figure = None

BAUD = 9600
V_MAX = 30.0
I_MAX = 10.0
SAMPLE_PERIOD = 0.5
MAX_POINTS = 3600


class PSU:
    """Dokładny protokół z ostatniej działającej wersji programu."""
    def __init__(self, port):
        self.port = port
        self.ser = None
        self.lock = threading.Lock()

    def connect(self):
        self.ser = serial.Serial(
            self.port, BAUD, bytesize=8, parity="N", stopbits=1,
            timeout=1, xonxoff=False, rtscts=False, dsrdtr=False
        )

    def close(self):
        ser = self.ser
        self.ser = None
        if ser and ser.is_open:
            try:
                ser.close()
            except Exception:
                pass

    def command(self, cmd):
        with self.lock:
            if self.ser is None or not self.ser.is_open:
                raise serial.SerialException("Port szeregowy nie jest otwarty.")
            self.ser.reset_input_buffer()
            self.ser.write(cmd.encode("ascii"))
            self.ser.flush()
            return self.ser.read_until(b">")

    @staticmethod
    def parse_measurement(data):
        if len(data) < 10 or not data.startswith(b"<"):
            raise ValueError(f"Nieprawidłowa odpowiedź: {data!r}")
        raw = data[3:9]
        value = int(raw) / 1000.0
        code = chr(data[2])
        mode = {"1": "CV", "C": "CC / OFF"}.get(code, code)
        return value, mode

    def voltage(self):
        return self.parse_measurement(self.command("<02000000000>"))

    def current(self):
        return self.parse_measurement(self.command("<04000000000>"))

    @staticmethod
    def ok(data):
        return b"OK" in data.upper()

    def remote(self):
        return self.ok(self.command("<09100000000>"))

    def local(self):
        return self.ok(self.command("<09200000000>"))

    def set_voltage(self, v):
        if not 0 <= v <= V_MAX:
            raise ValueError("Napięcie: 0–30 V.")
        digits = f"{v:07.3f}".replace(".", "")
        return self.ok(self.command(f"<01{digits}000>"))

    def set_current(self, a):
        if not 0 <= a <= I_MAX:
            raise ValueError("Prąd: 0–10 A.")
        digits = f"{a:07.3f}".replace(".", "")
        return self.ok(self.command(f"<03{digits}000>"))

    def output_on(self):
        return self.ok(self.command("<07000000000>"))

    def output_off(self):
        return self.ok(self.command("<08000000000>"))


class App(tk.Tk):
    VERSION = "1.0 Stable"
    AUTHOR = "Marian Jędrych"

    def __init__(self):
        super().__init__(className="NICE-POWER")

        # Tk sets the X11 WM_CLASS at window creation time. This is important on
        # Ubuntu/GNOME: the dock then matches this window with our .desktop file
        # instead of treating it as a generic Tk application.
        try:
            icon_path = "/usr/share/icons/hicolor/128x128/apps/nice-power-spps-a3010d.png"
            if os.path.exists(icon_path):
                self._app_icon = tk.PhotoImage(file=icon_path)
                self.iconphoto(True, self._app_icon)
        except tk.TclError:
            pass

        self.title(f"NICE-POWER / KUAIQU SPPS-A3010D — {self.VERSION}")
        self.geometry("1280x900")
        self.minsize(1080, 780)
        self.configure(bg="#0b1118")

        self.psu = None
        self.running = False
        self.connecting = False
        self.t0 = None
        self.ui_queue = queue.Queue()
        self.poll_thread = None

        self.t = deque(maxlen=MAX_POINTS)
        self.vdata = deque(maxlen=MAX_POINTS)
        self.idata = deque(maxlen=MAX_POINTS)
        self.pdata = deque(maxlen=MAX_POINTS)

        self.port = tk.StringVar(value="")
        self.status = tk.StringVar(value="Rozłączony")
        self.mode = tk.StringVar(value="—")
        self.output_var = tk.StringVar(value="OUTPUT —")
        self.v = tk.StringVar(value="---.--- V")
        self.i = tk.StringVar(value="---.--- A")
        self.p = tk.StringVar(value="---.--- W")
        self.vset = tk.StringVar(value="5.000")
        self.iset = tk.StringVar(value="1.000")
        self.info = tk.StringVar(value="Gotowy.")
        self.auto_scale = tk.BooleanVar(value=True)
        self.chart_unit = tk.StringVar(value="V + A + W")
        self.history_choice = tk.StringVar(value="5 min")
        self.sample_rate_choice = tk.StringVar(value="500 ms")
        self.csv_writer = None
        self.csv_handle = None

        self.build()
        self.refresh()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(50, self.process_ui_queue)

    def build(self):
        BG, PANEL, CARD = "#0b1118", "#111b26", "#101923"
        BORDER, TEXT, MUTED = "#294158", "#e8eef5", "#9fb3c8"
        GREEN, BLUE, ORANGE, RED = "#39ff6a", "#20b8ff", "#ff9f1c", "#ff4d57"
        self._colors = (BG, PANEL, CARD, BORDER, TEXT, MUTED, GREEN, BLUE, ORANGE, RED)

        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("TButton", background="#243447", foreground=TEXT, padding=(12, 7), borderwidth=0, font=("DejaVu Sans", 10, "bold"))
        style.map("TButton", background=[("active", "#34506b"), ("pressed", "#1b2b3b")])
        style.configure("Green.TButton", background="#168a3a", foreground="white")
        style.map("Green.TButton", background=[("active", "#20a94b")])
        style.configure("Red.TButton", background="#c92f3a", foreground="white")
        style.map("Red.TButton", background=[("active", "#ed3d48")])
        style.configure("Info.TButton", background="#1769aa", foreground="white")
        style.map("Info.TButton", background=[("active", "#2387d1")])
        style.configure("TEntry", fieldbackground="#14202c", foreground="white", insertcolor="white", bordercolor=BORDER)
        style.configure("TCombobox", fieldbackground="#14202c", foreground=TEXT, background="#243447", arrowcolor=TEXT)
        style.map("TCombobox", fieldbackground=[("readonly", "#14202c")], foreground=[("readonly", TEXT)])
        style.configure("TCheckbutton", background=BG, foreground=TEXT)
        style.map("TCheckbutton", background=[("active", BG)])
        style.configure("Card.TLabelframe", background=PANEL, bordercolor=BORDER, relief="solid")
        style.configure("Card.TLabelframe.Label", background=PANEL, foreground="#7dd3fc", font=("DejaVu Sans", 10, "bold"))
        # Popdown list is a Tk listbox, not a ttk widget: explicitly set it after opening.
        self.option_add("*TCombobox*Listbox.background", "#14202c")
        self.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.option_add("*TCombobox*Listbox.selectBackground", "#1769aa")
        self.option_add("*TCombobox*Listbox.selectForeground", "white")
        self.option_add("*TCombobox*Listbox.font", ("DejaVu Sans", 10))

        outer = tk.Frame(self, bg=BG, padx=14, pady=10)
        outer.pack(fill="both", expand=True)

        top = tk.Frame(outer, bg=BG); top.pack(fill="x", pady=(0, 8))
        tk.Label(top, text="USB", bg="#17314a", fg="#7dd3fc", font=("DejaVu Sans", 11, "bold"), width=5, pady=6).pack(side="left", padx=(0,8))
        tk.Label(top, text="Port USB:", bg=BG, fg=TEXT, font=("DejaVu Sans", 11, "bold")).pack(side="left")
        self.combo = ttk.Combobox(top, textvariable=self.port, width=20)
        self.combo.pack(side="left", padx=7)
        ttk.Button(top, text="⟳  Odśwież", command=self.refresh).pack(side="left")
        self.connect_btn = ttk.Button(top, text="Połącz", style="Green.TButton", command=self.toggle)
        self.connect_btn.pack(side="right")
        self.header_status = tk.Label(top, textvariable=self.status, bg=BG, fg=GREEN, font=("DejaVu Sans", 11, "bold"))
        self.header_status.pack(side="right", padx=18)

        titlebar = tk.Frame(outer, bg=BG); titlebar.pack(fill="x", pady=(0,10))
        tk.Label(titlebar, text=f"NICE-POWER / KUAIQU SPPS-A3010D — {self.VERSION}", bg=BG, fg=TEXT, font=("DejaVu Sans",18,"bold")).pack(side="left")
        ttk.Button(titlebar, text="ⓘ  Info", style="Info.TButton", command=self.show_info).pack(side="right")

        meas = tk.Frame(outer, bg=BG); meas.pack(fill="x", pady=(0,10))
        for idx,(name,var,color,mode_text) in enumerate([("Napięcie (V)",self.v,GREEN,"Tryb: CV"),("Prąd (A)",self.i,BLUE,"Tryb: CV"),("Moc (W)",self.p,ORANGE,"")]):
            card=tk.Frame(meas,bg=CARD,highlightbackground=color,highlightcolor=color,highlightthickness=1,bd=0)
            card.grid(row=0,column=idx,sticky="nsew",padx=(0 if idx==0 else 5,5 if idx<2 else 0)); meas.columnconfigure(idx,weight=1)
            tk.Label(card,text=name,bg=CARD,fg=color,font=("DejaVu Sans",11,"bold"),anchor="w").pack(fill="x",padx=14,pady=(10,0))
            tk.Label(card,textvariable=var,bg=CARD,fg=color,font=("DejaVu Sans",27,"bold")).pack(pady=(3,0))
            tk.Label(card,text=mode_text,bg=CARD,fg=color,font=("DejaVu Sans",10,"bold")).pack(pady=(0,10))

        status_card=tk.Frame(meas,bg=CARD,highlightbackground=BORDER,highlightcolor=BORDER,highlightthickness=1); status_card.grid(row=0,column=3,sticky="nsew",padx=(5,0)); meas.columnconfigure(3,weight=1)
        tk.Label(status_card,text="Status",bg=CARD,fg=TEXT,font=("DejaVu Sans",11,"bold"),anchor="w").pack(fill="x",padx=14,pady=(10,4))
        sr=tk.Frame(status_card,bg=CARD); sr.pack(fill="x",padx=14)
        for r,(lab,var,col) in enumerate([("Połączenie:",self.status,GREEN),("Wyjście:",self.output_var,GREEN),("Tryb:",self.mode,BLUE)]):
            tk.Label(sr,text=lab,bg=CARD,fg=MUTED).grid(row=r,column=0,sticky="w",pady=(0,5) if r<2 else 0)
            tk.Label(sr,textvariable=var,bg=CARD,fg=col,font=("DejaVu Sans",10,"bold")).grid(row=r,column=1,sticky="e",padx=8,pady=(0,5) if r<2 else 0)
        sr.columnconfigure(1,weight=1)

        controls=tk.Frame(outer,bg=BG); controls.pack(fill="x",pady=(0,10))
        settings=ttk.LabelFrame(controls,text="Nastawy",style="Card.TLabelframe",padding=9); settings.pack(side="left",fill="both",expand=True,padx=(0,5))
        tk.Label(settings,text="Napięcie (V):",bg=PANEL,fg=TEXT).grid(row=0,column=0,sticky="w")
        ttk.Entry(settings,textvariable=self.vset,width=10).grid(row=1,column=0,padx=(0,5),pady=(5,0)); ttk.Button(settings,text="Ustaw V",command=self.set_v).grid(row=1,column=1,pady=(5,0))
        tk.Label(settings,text="Prąd (A):",bg=PANEL,fg=TEXT).grid(row=0,column=2,sticky="w",padx=(15,0))
        ttk.Entry(settings,textvariable=self.iset,width=10).grid(row=1,column=2,padx=(15,5),pady=(5,0)); ttk.Button(settings,text="Ustaw I",command=self.set_i).grid(row=1,column=3,pady=(5,0))

        out=ttk.LabelFrame(controls,text="Wyjście",style="Card.TLabelframe",padding=9); out.pack(side="left",padx=5)
        ttk.Button(out,text="⏻  OUTPUT ON",style="Green.TButton",command=self.output_on).pack(side="left",padx=2,pady=4); ttk.Button(out,text="⏻  OUTPUT OFF",style="Red.TButton",command=self.output_off).pack(side="left",padx=2,pady=4)
        mode=ttk.LabelFrame(controls,text="Sterowanie",style="Card.TLabelframe",padding=9); mode.pack(side="left",padx=5)
        ttk.Button(mode,text="▣  REMOTE / PC",command=self.remote).pack(side="left",padx=2,pady=4); ttk.Button(mode,text="⌂  LOCAL / PANEL",command=self.local).pack(side="left",padx=2,pady=4)
        tools=ttk.LabelFrame(controls,text="Zapis danych (CSV)",style="Card.TLabelframe",padding=9); tools.pack(side="left",fill="both",padx=(5,0))
        self.rec_btn=ttk.Button(tools,text="●  Nagrywaj CSV",command=self.toggle_recording); self.rec_btn.pack(side="left",padx=2,pady=4); ttk.Button(tools,text="▤  Eksport CSV",command=self.export_csv).pack(side="left",padx=2,pady=4)

        chart_tools=tk.Frame(outer,bg=BG); chart_tools.pack(fill="x",pady=(0,6))
        tk.Label(chart_tools,text="Historia:",bg=BG,fg=TEXT,font=("DejaVu Sans",10,"bold")).pack(side="left")
        self.make_dark_dropdown(chart_tools,self.history_choice,("1 min","5 min","15 min","30 min","60 min"),"5 min",9,self.draw_chart)
        ttk.Checkbutton(chart_tools,text="Auto skala",variable=self.auto_scale,command=self.draw_chart).pack(side="left",padx=8)
        tk.Label(chart_tools,text="Wykres:",bg=BG,fg=TEXT,font=("DejaVu Sans",10,"bold")).pack(side="left",padx=(5,0))
        self.make_dark_dropdown(chart_tools,self.chart_unit,("V + A + W","V + A","V","A","W"),"V + A + W",11,self.draw_chart)
        tk.Label(chart_tools,text="Odczyt:",bg=BG,fg=TEXT,font=("DejaVu Sans",10,"bold")).pack(side="left",padx=(10,0))
        self.make_dark_dropdown(chart_tools,self.sample_rate_choice,("100 ms","250 ms","500 ms","1 s","2 s"),"500 ms",8,self.on_sample_rate_change)
        ttk.Button(chart_tools,text="🗑  Wyczyść wykres",command=self.clear_chart).pack(side="right",padx=3)

        if Figure:
            frame=ttk.LabelFrame(outer,text="Pomiary na żywo",style="Card.TLabelframe",padding=3); frame.pack(fill="both",expand=True)
            self.fig=Figure(figsize=(10,4.4),dpi=90,facecolor="#05080c"); self.ax=self.fig.add_subplot(111); self.ax2=None; self.ax3=None
            self.canvas=FigureCanvasTkAgg(self.fig,master=frame); self.canvas.get_tk_widget().pack(fill="both",expand=True); self.canvas.get_tk_widget().configure(bg="#05080c",highlightthickness=0)
        else: ttk.Label(outer,text="Brak matplotlib. Zainstaluj python3-matplotlib.").pack()

        bottom=tk.Frame(outer,bg=BG); bottom.pack(fill="x",pady=(8,0)); log=ttk.LabelFrame(bottom,text="Dziennik zdarzeń",style="Card.TLabelframe",padding=7); log.pack(fill="x"); ttk.Label(log,textvariable=self.info,foreground=MUTED).pack(fill="x")
        ttk.Label(outer,text=f"Autor: {self.AUTHOR}   •   NICE-POWER / KUAIQU SPPS-A3010D   •   {self.VERSION}",foreground=MUTED,background=BG).pack(anchor="e",pady=(5,0))

    def make_dark_dropdown(self, parent, variable, values, default, width, command):
        # Tk/GTK can ignore ttk Combobox readonly colors on some Ubuntu themes.
        # A native Tk Menu keeps both the field and popup high-contrast.
        variable.set(default)
        btn=tk.Menubutton(parent,textvariable=variable,indicatoron=True,direction="below",width=width,anchor="w",
                          bg="#14202c",fg="#e8eef5",activebackground="#1769aa",activeforeground="#ffffff",
                          relief="solid",bd=1,highlightthickness=1,highlightbackground="#3b5872",
                          highlightcolor="#3b9ee8",font=("DejaVu Sans",10,"bold"),padx=8,pady=4)
        menu=tk.Menu(btn,tearoff=False,bg="#14202c",fg="#e8eef5",activebackground="#1769aa",
                     activeforeground="#ffffff",font=("DejaVu Sans",10),relief="solid",bd=1)
        for value in values:
            menu.add_radiobutton(label=value,variable=variable,value=value,command=command,selectcolor="#1769aa")
        btn.configure(menu=menu)
        btn.pack(side="left",padx=5)
        return btn

    def style_combobox_popup(self,event=None):
        combo=event.widget if event is not None else None
        if combo is None: return
        def apply():
            try:
                popdown=self.tk.call("ttk::combobox::PopdownWindow",str(combo)); listbox=popdown+".f.l"
                self.tk.call(listbox,"configure","-background","#14202c","-foreground","#e8eef5","-selectbackground","#1769aa","-selectforeground","#ffffff","-font",("DejaVu Sans",10))
            except tk.TclError: pass
        self.after_idle(apply)

    def refresh(self):
        try: ports=[p.device for p in serial.tools.list_ports.comports()]
        except Exception as e: ports=[]; self.info.set(f"Błąd listy portów: {e}")
        self.combo["values"] = ports
        current = self.port.get().strip()
        if current in ports:
            self.port.set(current)
        elif ports:
            # Automatycznie wybierz pierwszy rzeczywiście wykryty port.
            # Dzięki temu /dev/ttyUSB1 zostanie wybrany, jeśli ttyUSB0 nie istnieje.
            self.port.set(ports[0])
        else:
            self.port.set("")

    def ui(self, fn, *args): self.ui_queue.put((fn,args))

    def process_ui_queue(self):
        try:
            while True:
                fn,args=self.ui_queue.get_nowait(); fn(*args)
        except queue.Empty: pass
        self.after(50,self.process_ui_queue)

    def toggle(self):
        if self.connecting: return
        if self.psu:
            self.running=False
            self.stop_recording()
            psu=self.psu; self.psu=None
            psu.close()
            self.status.set("Rozłączony"); self.mode.set("—"); self.output_var.set("OUTPUT —"); self.connect_btn.config(text="Połącz",state="normal",style="Green.TButton"); self.header_status.config(fg="#ff6b6b"); self.info.set("Port zamknięty.")
            return
        port=self.port.get().strip()
        if not port: return
        self.connecting=True; self.connect_btn.config(text="Łączenie…",state="disabled"); self.status.set("Łączenie…"); self.info.set(f"Łączenie z {port}…")
        threading.Thread(target=self._connect_worker,args=(port,),daemon=True).start()

    def _connect_worker(self,port):
        psu=PSU(port)
        try:
            psu.connect()
            v,mode=psu.voltage(); a,_=psu.current()
            self.ui(self._connected,psu,v,a,mode)
        except Exception as e:
            psu.close()
            # Dla niedostępnego portu pokazujemy prosty komunikat zamiast surowego
            # wyjątku pyserial, ale zachowujemy szczegóły w pasku informacji.
            if isinstance(e, (serial.SerialException, OSError)):
                msg = f"Brak urządzenia na porcie {port}. Sprawdź wybór portu USB."
            else:
                msg = str(e)
            self.ui(self._connect_failed, msg)

    def _connected(self,psu,v,a,mode):
        self.connecting=False; self.psu=psu; self.running=True; self.t0=time.monotonic(); self.t.clear(); self.vdata.clear(); self.idata.clear(); self.pdata.clear()
        self.status.set("Połączony"); self.header_status.config(fg="#39ff6a"); self.mode.set(mode); self.connect_btn.config(text="Rozłącz",state="normal",style="Red.TButton"); self.update_measurements(v,a); self.info.set(f"Połączenie OK. Odczyt co {self.sample_period_label()}.")
        self.poll_thread=threading.Thread(target=self.poll,daemon=True); self.poll_thread.start()

    def _connect_failed(self,msg):
        self.connecting=False; self.psu=None; self.status.set("Rozłączony"); self.connect_btn.config(text="Połącz",state="normal",style="Green.TButton"); self.info.set("Błąd połączenia."); messagebox.showerror("Błąd połączenia",msg,parent=self)

    def update_measurements(self,v,a): self.v.set(f"{v:.3f} V"); self.i.set(f"{a:.3f} A"); self.p.set(f"{v*a:.3f} W")

    def poll(self):
        psu=self.psu
        while self.running and psu is self.psu:
            try:
                v,mode=psu.voltage(); a,_=psu.current(); elapsed=time.monotonic()-self.t0
                self.t.append(elapsed); self.vdata.append(v); self.idata.append(a); self.pdata.append(v*a)
                if self.csv_writer:
                    self.csv_writer.writerow([datetime.now().isoformat(timespec="seconds"),f"{v:.3f}",f"{a:.3f}",f"{v*a:.3f}",mode]); self.csv_handle.flush()
                self.ui(self.update_measurements,v,a); self.ui(self.mode.set,mode); self.ui(self.draw_chart)
            except Exception as e:
                if self.running and psu is self.psu: self.ui(self.info.set,f"Błąd odczytu: {e}")
            interval = self.sample_period_seconds()
            deadline = time.monotonic() + interval
            while self.running and psu is self.psu and time.monotonic() < deadline:
                time.sleep(min(0.02, max(0.001, deadline - time.monotonic())))

    def selected_history(self): return {"1 min":60,"5 min":300,"15 min":900,"30 min":1800,"60 min":3600}[self.history_choice.get()]
    def sample_period_seconds(self):
        return {"100 ms":0.10,"250 ms":0.25,"500 ms":0.50,"1 s":1.0,"2 s":2.0}[self.sample_rate_choice.get()]

    def sample_period_label(self):
        return self.sample_rate_choice.get()

    def on_sample_rate_change(self):
        self.info.set(f"Częstotliwość odczytu: {self.sample_period_label()}")


    def draw_chart(self):
        if not Figure or not hasattr(self,"canvas"): return
        if not self.t:
            self.fig.clear()
            self.ax=self.fig.add_subplot(111)
            self.ax.set_facecolor("#05080c")
            self.ax.grid(True,color="#526273",alpha=.38,linestyle="--",linewidth=.8)
            self.canvas.draw_idle()
            return
        limit=self.selected_history(); end=self.t[-1]; start=max(0,end-limit)
        rows=[r for r in zip(self.t,self.vdata,self.idata,self.pdata) if r[0]>=start]
        x=[r[0] for r in rows]; unit=self.chart_unit.get()
        GREEN,BLUE,ORANGE="#39ff6a","#20b8ff","#ff9f1c"

        # Jeden wspólny wykres: wszystkie przebiegi są widoczne razem, ale
        # każda wielkość ma własną skalę Y. Dla czytelności używamy też różnych
        # stylów linii i markerów, więc nawet podobne przebiegi nie zlewają się.
        self.fig.clear()
        self.ax = self.fig.add_subplot(111)
        self.ax2 = self.ax.twinx()
        self.ax3 = self.ax.twinx()
        self.ax3.spines["right"].set_position(("axes", 1.10))
        self.ax3.set_frame_on(True)
        self.ax3.patch.set_visible(False)

        series = []
        if unit in ("V + A", "V + A + W", "V"):
            series.append((self.ax,[r[1] for r in rows],GREEN,"Napięcie (V)","Napięcie [V]","-","o"))
        if unit in ("V + A", "V + A + W", "A"):
            series.append((self.ax2,[r[2] for r in rows],BLUE,"Prąd (A)","Prąd [A]","-","o"))
        if unit in ("V + A + W", "W"):
            series.append((self.ax3,[r[3] for r in rows],ORANGE,"Moc (W)","Moc [W]","-","o"))

        for ax,y,color,label,ylabel,linestyle,marker in series:
            ax.set_facecolor("#05080c")
            step=max(1,len(x)//30)
            ax.plot(x,y,color=color,linewidth=2.3,linestyle=linestyle,
                    marker=marker,markersize=3.5,markevery=step,label=label,zorder=4)
            ax.set_ylabel(ylabel,color=color,labelpad=8)
            ax.tick_params(axis="y",colors=color,pad=4)
            ax.spines["left" if ax is self.ax else "right"].set_color(color)
            if ax is self.ax3:
                ax.spines["right"].set_color(color)
            if self.auto_scale.get():
                ax.relim(); ax.autoscale_view()

        if not self.auto_scale.get():
            if self.ax in [s[0] for s in series]: self.ax.set_ylim(0,V_MAX)
            if self.ax2 in [s[0] for s in series]: self.ax2.set_ylim(0,I_MAX)
            if self.ax3 in [s[0] for s in series]: self.ax3.set_ylim(0,V_MAX*I_MAX)

        self.ax.grid(True,color="#526273",alpha=.30,linestyle="--",linewidth=.7)
        self.ax.set_xlabel("Czas od uruchomienia [s]",color="#b7c5d4")
        self.ax.tick_params(axis="x",colors="#b7c5d4")
        handles=[]
        for ax in (self.ax,self.ax2,self.ax3):
            if ax is not None:
                h,l=ax.get_legend_handles_labels()
                handles.extend(zip(h,l))
        if handles:
            self.ax.legend([h for h,l in handles],[l for h,l in handles],loc="upper left",
                           facecolor="#0b1118",edgecolor="#294158",framealpha=.95)
            for txt in self.ax.get_legend().get_texts(): txt.set_color("#e8eef5")
        self.fig.patch.set_facecolor("#05080c")
        self.fig.subplots_adjust(left=.09,right=.86,bottom=.14,top=.94)
        self.canvas.draw_idle()

    def clear_chart(self):
        self.t.clear(); self.vdata.clear(); self.idata.clear(); self.pdata.clear(); self.info.set("Historia wykresu wyczyszczona.")
        self.draw_chart()

    def need(self):
        if not self.psu: messagebox.showwarning("Brak połączenia","Najpierw kliknij „Połącz”.",parent=self); return False
        return True

    def action(self, title, func, success):
        if not self.need(): return
        psu=self.psu
        def worker():
            try:
                result=func(psu); self.ui(lambda: success(result))
            except Exception as e: self.ui(lambda: messagebox.showerror(title,str(e),parent=self))
        threading.Thread(target=worker,daemon=True).start()

    def set_v(self):
        try: v=float(self.vset.get().replace(",","."))
        except Exception as e: messagebox.showerror("Napięcie",str(e),parent=self); return
        self.action("Napięcie",lambda psu:(psu.remote(),psu.set_voltage(v))[1],lambda ok:self.info.set(f"Napięcie {v:.3f} V — {'OK' if ok else 'brak potwierdzenia'}"))

    def set_i(self):
        try: a=float(self.iset.get().replace(",","."))
        except Exception as e: messagebox.showerror("Prąd",str(e),parent=self); return
        self.action("Prąd",lambda psu:(psu.remote(),psu.set_current(a))[1],lambda ok:self.info.set(f"Limit {a:.3f} A — {'OK' if ok else 'brak potwierdzenia'}"))

    def output_on(self): self.action("OUTPUT ON",lambda psu:psu.output_on(),lambda ok:(self.output_var.set("OUTPUT ON"),self.info.set(f"Wyjście ON — {'OK' if ok else 'brak potwierdzenia'}")))
    def output_off(self): self.action("OUTPUT OFF",lambda psu:psu.output_off(),lambda ok:(self.output_var.set("OUTPUT OFF"),self.info.set(f"Wyjście OFF — {'OK' if ok else 'brak potwierdzenia'}")))
    def remote(self): self.action("REMOTE",lambda psu:psu.remote(),lambda ok:(self.mode.set("REMOTE / PC"),self.info.set("REMOTE: komputer przejął sterowanie.")))
    def local(self): self.action("LOCAL",lambda psu:psu.local(),lambda ok:(self.mode.set("LOCAL / PANEL"),self.info.set("LOCAL: sterowanie wróciło do panelu zasilacza.")))

    def toggle_recording(self):
        if self.csv_writer: self.stop_recording(); return
        path=filedialog.asksaveasfilename(title="Zapis pomiarów",defaultextension=".csv",filetypes=[("CSV","*.csv")],parent=self)
        if not path:return
        try:
            self.csv_handle=open(path,"w",newline="",encoding="utf-8"); self.csv_writer=csv.writer(self.csv_handle); self.csv_writer.writerow(["timestamp","voltage_V","current_A","power_W","mode"]); self.rec_btn.config(text="■  Zatrzymaj CSV"); self.info.set(f"Nagrywanie CSV: {path}")
        except Exception as e:
            self.csv_writer=None; self.csv_handle=None; messagebox.showerror("CSV",str(e),parent=self)

    def stop_recording(self):
        if self.csv_handle:
            try:self.csv_handle.close()
            except Exception:pass
        self.csv_handle=None; self.csv_writer=None
        if hasattr(self,"rec_btn"): self.rec_btn.config(text="●  Nagrywaj CSV")

    def export_csv(self):
        if not self.t: messagebox.showinfo("CSV","Brak danych do eksportu.",parent=self); return
        path=filedialog.asksaveasfilename(title="Eksport historii",defaultextension=".csv",filetypes=[("CSV","*.csv")],parent=self)
        if not path:return
        try:
            with open(path,"w",newline="",encoding="utf-8") as f:
                w=csv.writer(f); w.writerow(["time_s","voltage_V","current_A","power_W"])
                for row in zip(self.t,self.vdata,self.idata,self.pdata): w.writerow([f"{row[0]:.1f}",f"{row[1]:.3f}",f"{row[2]:.3f}",f"{row[3]:.3f}"])
            self.info.set(f"Wyeksportowano {len(self.t)} próbek do {path}")
        except Exception as e: messagebox.showerror("Eksport CSV",str(e),parent=self)

    def show_info(self):
        messagebox.showinfo("O programie",f"NICE-POWER / KUAIQU SPPS-A3010D\n\nWersja: {self.VERSION}\nAutor: {self.AUTHOR}\n\nGraficzne sterowanie zasilaczem laboratoryjnym przez USB.\nOdczyt V/A/W, nastawy V/I, OUTPUT, REMOTE/LOCAL,\nwykres na żywo oraz zapis i eksport CSV.\n\n© {self.AUTHOR}",parent=self)

    def close(self):
        self.running=False; self.stop_recording(); psu=self.psu; self.psu=None
        if psu: psu.close()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
