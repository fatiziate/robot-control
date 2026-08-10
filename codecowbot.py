import tkinter as tk
import json
import os

# Fichier de sauvegarde persistante pour les positions et les liaisons
DATA_FILE = "data.json"


class CardListbox(tk.Frame):
    """
    Liste façon 'cartes' : chaque élément est affiché dans sa propre case
    bien cadrée avec une grande police, au lieu d'un Listbox classique.
    Expose une API compatible avec le sous-ensemble de tk.Listbox utilisé
    dans l'application (insert, delete, get, curselection, size).
    """

    def __init__(self, parent, font=("Segoe UI", 20, "bold"),
                 selectbackground="#f48fb1", bg="white",
                 fg="#2d2d2d", item_bg="#fdfbfc", border_color="#d9a5b8",
                 **kwargs):
        super().__init__(parent, bg=bg)
        self.font = font
        self.selectbackground = selectbackground
        self.item_bg = item_bg
        self.fg = fg
        self.border_color = border_color

        self.items = []
        self.selected_index = None

        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)

        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas_window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.bind("<Configure>", self._on_canvas_resize)

    def _on_canvas_resize(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def insert(self, index, value):
        self.items.append(value)
        self._render()

    def delete(self, start, end=None):
        if end == tk.END:
            self.items = []
            self.selected_index = None
        else:
            idx = start
            if 0 <= idx < len(self.items):
                del self.items[idx]
                if self.selected_index == idx:
                    self.selected_index = None
                elif self.selected_index is not None and self.selected_index > idx:
                    self.selected_index -= 1
        self._render()

    def get(self, start, end=None):
        if end is None:
            return self.items[start]
        return tuple(self.items)

    def curselection(self):
        return (self.selected_index,) if self.selected_index is not None else ()

    def size(self):
        return len(self.items)

    def _select(self, idx):
        self.selected_index = idx
        self._render()

    def _render(self):
        for w in self.inner.winfo_children():
            w.destroy()
        for i, val in enumerate(self.items):
            is_sel = (i == self.selected_index)
            card_bg = self.selectbackground if is_sel else self.item_bg
            card = tk.Frame(self.inner, bg=card_bg, bd=1, relief="solid",
                             highlightbackground=self.border_color, highlightthickness=1)
            card.pack(fill="x", padx=8, pady=5)
            lbl = tk.Label(card, text=val, font=self.font, bg=card_bg, fg=self.fg,
                            anchor="w", padx=16, pady=14, cursor="hand2")
            lbl.pack(fill="x")
            lbl.bind("<Button-1>", lambda e, i=i: self._select(i))
            card.bind("<Button-1>", lambda e, i=i: self._select(i))


class RobotControlApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Robot Control Panel - eRobot 3Kg")
        self.root.attributes("-fullscreen", True)
        
        # Passage automatique en plein écran / zoomé
        try:
            self.root.state("zoomed")
        except tk.TclError:
            try:
                self.root.attributes("-zoomed", True)
            except tk.TclError:
                pass
                
        self.root.overrideredirect(True) # Supprime la barre système supérieure pour l'intégration tactile
        self.root.bind("<Escape>", lambda e: self.root.destroy()) # Permet de quitter avec la touche Échap
        self.root.configure(bg="#f4f6f8")

        self.axis_names = {
            1: "J1 Base", 2: "J2 Shoulder", 3: "J3 Elbow",
            4: "J4 Wrist 1", 5: "J5 Wrist 2", 6: "J6 Tool"
        }

        self.axis_vars = {}
        self.angle_entries = {}
        self.saved_positions = {}
        self.saved_links = {}
        self.link_delay_ms = 2000 # Délai d'attente entre deux positions lors d'une liaison

        self.colors = {
            "bg_main": "#f4f6f8", "header": "#7b1e3a", "header_text": "#ffffff",
            "card_bg": "#ffffff", "section_title": "#6d1533", "table_header": "#f7d6e2",
            "table_row": "#fffafb", "row_gray": "#e5e7eb", "row_selected": "#f48fb1",
            "button_primary": "#c2185b", "button_secondary": "#ec407a", "button_clear": "#ff80ab",
            "button_dark": "#8e244d", "button_green": "#2e7d32", "button_orange": "#ef6c00",
            "button_red": "#c62828", "button_gray": "#5f6b7a", "text_dark": "#2d2d2d",
            "text_muted": "#6b7280", "entry_bg": "#ffffff", "log_bg": "#1f1f1f",
            "log_fg": "#f8d7e3", "check_bg": "#ffe4ee"
        }

        # Garde en mémoire le panneau actif (overlay) qui recouvre temporairement la zone centrale
        self.active_overlay = None

        self.load_data_from_file()
        self.build_ui()

    def load_data_from_file(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.saved_positions = {
                        pos_name: {int(k): v for k, v in pos_data.items()}
                        for pos_name, pos_data in data.get("positions", {}).items()
                    }
                    self.saved_links = data.get("links", {})
            except Exception as e:
                self.log(f"Erreur de lecture : {e}")

    def save_data_to_file(self):
        try:
            data = {"positions": self.saved_positions, "links": self.saved_links}
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            self.log(f"Erreur d'écriture : {e}")

    def build_ui(self):
        self.build_top_bar()
        
        # Conteneur principal de la grille
        self.body_container = tk.Frame(self.root, bg=self.colors["bg_main"])
        self.body_container.pack(fill="both", expand=True)

        self.build_table_view()

    def build_top_bar(self):
        top_bar = tk.Frame(self.root, bg=self.colors["header"], height=90)
        top_bar.pack(fill="x")
        top_bar.pack_propagate(False)

        left_buttons = [
            ("Save Position", self.colors["button_clear"], self.save_current_position),
            ("Load Position", self.colors["button_primary"], self.load_saved_position),
            ("Create Link", self.colors["button_secondary"], self.create_link),
            ("Run Link", self.colors["button_gray"], self.run_link),
        ]

        right_buttons = [
            ("Start", self.colors["button_green"], self.move_all_selected),
            ("Stop", self.colors["button_red"], self.stop_all_motors),
        ]

        def make_top_bar_button(text, color, cmd):
            fg_color = "black" if color == self.colors["button_clear"] else "white"
            return tk.Button(top_bar, text=text, command=cmd, bg=color, fg=fg_color, font=("Segoe UI", 14, "bold"),
                             relief="flat", bd=0, padx=16, pady=16, cursor="hand2")

        for text, color, cmd in left_buttons:
            make_top_bar_button(text, color, cmd).pack(side="left", padx=8, pady=16)

        for text, color, cmd in reversed(right_buttons):
            make_top_bar_button(text, color, cmd).pack(side="right", padx=8, pady=16)

    def build_table_view(self):
        self.table_view_frame = tk.Frame(self.body_container, bg=self.colors["card_bg"], bd=1, relief="solid")
        self.table_view_frame.pack(fill="both", expand=True, padx=0, pady=0)

        # Création de la grille principale
        self.table_container = tk.Frame(self.table_view_frame, bg=self.colors["card_bg"])
        self.table_container.pack(fill="both", expand=True, padx=8, pady=8)

        # En-têtes (Ligne 0) - Resteront toujours visibles !
        headers = ["Select", "Axis", "Jog -", "Jog +", "Angle"]
        for col, header in enumerate(headers):
            tk.Label(self.table_container, text=header, font=("Segoe UI", 18, "bold"), bg=self.colors["table_header"],
                     fg=self.colors["text_dark"], pady=18, relief="groove", bd=1).grid(row=0, column=col, sticky="nsew",
                                                                                       padx=1, pady=1)

        for motor_id in range(1, 7):
            selected_var = tk.BooleanVar(value=False)
            self.axis_vars[motor_id] = {"selected": selected_var}

            row_bg = self.colors["row_gray"]

            select_cell = tk.Frame(self.table_container, bg=row_bg, relief="groove", bd=1)
            select_cell.grid(row=motor_id, column=0, sticky="nsew", padx=1, pady=1)

            select_cb = tk.Checkbutton(
                select_cell, variable=selected_var, onvalue=True, offvalue=False, font=("Segoe UI", 16, "bold"),
                indicatoron=False, width=3, bg=row_bg, fg=self.colors["section_title"],
                selectcolor=self.colors["check_bg"],
                relief="raised", bd=2, highlightthickness=0, cursor="hand2",
                command=lambda m=motor_id: self.on_motor_toggle(m)
            )
            select_cb.pack(expand=True, ipadx=6, ipady=10, padx=8, pady=8)
            self.axis_vars[motor_id]["select_button"] = select_cb
            self.axis_vars[motor_id]["select_cell"] = select_cell

            axis_label = tk.Label(self.table_container, text=self.axis_names[motor_id], font=("Segoe UI", 16, "bold"),
                                  bg=row_bg, fg=self.colors["text_dark"], relief="groove", bd=1)
            axis_label.grid(row=motor_id, column=1, sticky="nsew", padx=1, pady=1)
            self.axis_vars[motor_id]["axis_label"] = axis_label

            jog_left_btn = self.make_button(self.table_container, "◀️", row_bg, lambda m=motor_id: self.jog_angle(m, -1),
                                            motor_id, 2)
            jog_right_btn = self.make_button(self.table_container, "▶️", row_bg, lambda m=motor_id: self.jog_angle(m, 1),
                                             motor_id, 3)

            self.axis_vars[motor_id]["jog_left_btn"] = jog_left_btn
            self.axis_vars[motor_id]["jog_right_btn"] = jog_right_btn

            # Colonne Angle (Colonne 4) - Restera toujours visible à droite !
            angle_entry = tk.Entry(self.table_container, width=6, font=("Consolas", 20, "bold"), justify="center", bg=row_bg,
                                   fg=self.colors["text_dark"], relief="solid", bd=2, cursor="hand2")
            angle_entry.insert(0, "0")
            angle_entry.grid(row=motor_id, column=4, padx=4, pady=4, ipady=14, sticky="nsew")

            angle_entry.bind("<Button-1>", lambda event, m=motor_id: self.open_keypad_if_active(m))
            self.angle_entries[motor_id] = angle_entry

            self.refresh_select_button(motor_id)

        for col in range(len(headers)):
            self.table_container.grid_columnconfigure(col, weight=1)
        self.table_container.grid_columnconfigure(0, weight=2)
        self.table_container.grid_columnconfigure(1, weight=2)
        for row in range(7):
            self.table_container.grid_rowconfigure(row, weight=1)

    def make_button(self, parent, text, color, command, row, col):
        btn = tk.Button(parent, text=text, command=command, bg=color, fg="white", font=("Segoe UI", 20, "bold"),
                        width=4, relief="flat", bd=0, cursor="hand2")
        btn.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")
        return btn

    def on_motor_toggle(self, motor_id):
        # Si le moteur vient d'être désélectionné, son angle repasse à 0
        if not self.axis_vars[motor_id]["selected"].get():
            entry = self.angle_entries[motor_id]
            entry.configure(state="normal")
            entry.delete(0, tk.END)
            entry.insert(0, "0")
        self.refresh_select_button(motor_id)

    def reset_all_motors(self):
        # Désélectionne tous les moteurs et remet tous les angles à 0
        for motor_id in range(1, 7):
            self.axis_vars[motor_id]["selected"].set(False)
            entry = self.angle_entries[motor_id]
            entry.configure(state="normal")
            entry.delete(0, tk.END)
            entry.insert(0, "0")
            self.refresh_select_button(motor_id)

    def stop_all_motors(self):
        self.send_command({"command": "stopAllMotors"})
        self.reset_all_motors()

    def refresh_select_button(self, motor_id):
        is_selected = self.axis_vars[motor_id]["selected"].get()

        button = self.axis_vars[motor_id]["select_button"]
        select_cell = self.axis_vars[motor_id]["select_cell"]
        axis_label = self.axis_vars[motor_id]["axis_label"]
        jog_left_btn = self.axis_vars[motor_id]["jog_left_btn"]
        jog_right_btn = self.axis_vars[motor_id]["jog_right_btn"]
        angle_entry = self.angle_entries[motor_id]

        button.configure(text="✓" if is_selected else "")

        if is_selected:
            row_color = self.colors["row_selected"]
            jog_color = self.colors["button_orange"]

            jog_left_btn.configure(state="normal", bg=jog_color, activebackground=jog_color)
            jog_right_btn.configure(state="normal", bg=jog_color, activebackground=jog_color)
            angle_entry.configure(state="normal", bg=row_color)
        else:
            row_color = self.colors["row_gray"]

            jog_left_btn.configure(state="disabled", bg=row_color)
            jog_right_btn.configure(state="disabled", bg=row_color)
            angle_entry.configure(state="disabled", bg=row_color)

        select_cell.configure(bg=row_color)
        button.configure(bg=row_color, activebackground=row_color)
        axis_label.configure(bg=row_color)

    def show_overlay(self):
        # Ne supprime plus la grille ! Utilise .place() pour se superposer uniquement sur les lignes d'axes (lignes 1 à 6, colonnes 0 à 3)
        if self.active_overlay:
            self.active_overlay.destroy()
        
        # On superpose sur la zone centrale (laisse la colonne angle libre à droite)
        self.active_overlay = tk.Frame(self.table_container, bg="white", bd=2, relief="solid")
        self.active_overlay.place(relx=0.005, rely=0.02, relwidth=0.85, relheight=0.97)
        return self.active_overlay

    def hide_overlay(self):
        # Retire simplement le clavier de l'écran pour dévoiler les commandes sous-jacentes
        if self.active_overlay:
            self.active_overlay.destroy()
            self.active_overlay = None

    def open_keypad_if_active(self, motor_id):
        if self.axis_vars[motor_id]["selected"].get():
            self.angle_entries[motor_id].configure(bg="#ffc107")
            self.show_numeric_keypad_overlay(motor_id)

    def show_numeric_keypad_overlay(self, motor_id):
        container = self.show_overlay()
        container.configure(bg="white")

        title = tk.Label(
            container,
            text=f"Saisir l'angle pour {self.axis_names[motor_id]}  (0 - 90)",
            font=("Segoe UI", 16, "bold"),
            bg=self.colors["header"],
            fg="white",
            pady=16
        )
        title.pack(fill="x", side="top")

        display_val = tk.StringVar(value=self.angle_entries[motor_id].get())

        display = tk.Entry(
            container,
            textvariable=display_val,
            font=("Consolas", 26, "bold"),
            justify="center",
            bd=0,
            relief="flat",
            bg="#fdfbf7",
            fg=self.colors["button_primary"],
            highlightthickness=2,
            highlightbackground=self.colors["header"],
            highlightcolor=self.colors["header"]
        )
        display.pack(fill="x", padx=150, pady=(20, 15), ipady=10)

        keypad_frame = tk.Frame(container, bg="white")
        keypad_frame.pack(padx=80, pady=(0, 20), fill="both", expand=True)

        buttons = [
            ("7", 0, 0), ("8", 0, 1), ("9", 0, 2),
            ("4", 1, 0), ("5", 1, 1), ("6", 1, 2),
            ("1", 2, 0), ("2", 2, 1), ("3", 2, 2),
            ("C", 3, 0), ("0", 3, 1), ("OK", 3, 2),
        ]

        def on_num_click(text):
            curr = display_val.get()
            if text == "C":
                display_val.set("")
            elif text == "OK":
                try:
                    val = float(curr) if curr.strip() != "" else 0.0
                    val = max(0, min(90, val))
                    self.angle_entries[motor_id].delete(0, tk.END)
                    if int(val) == val:
                        self.angle_entries[motor_id].insert(0, str(int(val)))
                    else:
                        self.angle_entries[motor_id].insert(0, str(val))
                except ValueError:
                    pass
                self.hide_overlay()
                self.refresh_select_button(motor_id)
            else:
                display_val.set(curr + text)

        for text, row, col in buttons:
            bg = self.colors["table_header"]
            fg = self.colors["text_dark"]
            active_bg = "#f0bcd2"
            if text == "C":
                bg = self.colors["button_red"]
                fg = "white"
                active_bg = "#a91f1f"
            elif text == "OK":
                bg = self.colors["button_green"]
                fg = "white"
                active_bg = "#245e26"

            btn = tk.Button(
                keypad_frame,
                text=text,
                font=("Segoe UI", 20, "bold"),
                bg=bg,
                fg=fg,
                activebackground=active_bg,
                activeforeground=fg,
                relief="solid",
                bd=1,
                highlightbackground=self.colors["header"],
                cursor="hand2",
                command=lambda t=text: on_num_click(t)
            )
            btn.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")

        for i in range(3):
            keypad_frame.grid_columnconfigure(i, weight=1)
        for i in range(4):
            keypad_frame.grid_rowconfigure(i, weight=1)

    def show_text_keypad_overlay(self, title_text, callback_action):
        container = self.show_overlay()
        container.configure(bg="white")

        title = tk.Label(
            container,
            text=title_text,
            font=("Segoe UI", 16, "bold"),
            bg=self.colors["header"],
            fg="white",
            pady=16
        )
        title.pack(fill="x", side="top")

        display_val = tk.StringVar()

        display = tk.Entry(
            container,
            textvariable=display_val,
            font=("Consolas", 22, "bold"),
            justify="center",
            bd=0,
            relief="flat",
            bg="#fdfbf7",
            fg=self.colors["section_title"],
            highlightthickness=2,
            highlightbackground=self.colors["header"],
            highlightcolor=self.colors["header"]
        )
        display.pack(fill="x", padx=100, pady=(16, 12), ipady=8)

        keypad_frame = tk.Frame(container, bg="white")
        keypad_frame.pack(padx=20, pady=(0, 16), fill="both", expand=True)

        for i in range(11):
            keypad_frame.grid_columnconfigure(i, weight=1)

        rows = [
            ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "_"],
            ["A", "Z", "E", "R", "T", "Y", "U", "I", "O", "P"],
            ["Q", "S", "D", "F", "G", "H", "J", "K", "L", "M"]
        ]

        def on_text_click(text):
            curr = display_val.get()
            if text == "CLR":
                display_val.set("")
            elif text == "ANNULER":
                self.hide_overlay()
            elif text == "OK":
                val = display_val.get().strip()
                self.hide_overlay()
                if val:
                    callback_action(val)
            else:
                display_val.set(curr + text)

        for row_idx, row_content in enumerate(rows):
            for col_idx, text in enumerate(row_content):
                btn = tk.Button(
                    keypad_frame,
                    text=text,
                    font=("Segoe UI", 14, "bold"),
                    bg=self.colors["table_header"],
                    fg=self.colors["text_dark"],
                    activebackground="#f0bcd2",
                    activeforeground=self.colors["text_dark"],
                    relief="solid",
                    bd=1,
                    highlightbackground=self.colors["header"],
                    cursor="hand2",
                    command=lambda t=text: on_text_click(t)
                )
                btn.grid(row=row_idx, column=col_idx, padx=4, pady=4, sticky="nsew")

        last_letters = ["W", "X", "C", "V", "B", "N"]
        for col_idx, text in enumerate(last_letters):
            btn = tk.Button(
                keypad_frame,
                text=text,
                font=("Segoe UI", 14, "bold"),
                bg=self.colors["table_header"],
                fg=self.colors["text_dark"],
                activebackground="#f0bcd2",
                activeforeground=self.colors["text_dark"],
                relief="solid",
                bd=1,
                highlightbackground=self.colors["header"],
                cursor="hand2",
                command=lambda t=text: on_text_click(t)
            )
            btn.grid(row=3, column=col_idx, padx=4, pady=4, sticky="nsew")

        btn_clr = tk.Button(
            keypad_frame, text="CLR", font=("Segoe UI", 14, "bold"),
            bg=self.colors["button_red"], fg="white", activebackground="#a91f1f", activeforeground="white",
            relief="solid", bd=1, highlightbackground=self.colors["header"], cursor="hand2",
            command=lambda: on_text_click("CLR")
        )
        btn_clr.grid(row=3, column=6, columnspan=1, padx=4, pady=4, sticky="nsew")

        btn_ok = tk.Button(
            keypad_frame, text="OK", font=("Segoe UI", 14, "bold"),
            bg=self.colors["button_green"], fg="white", activebackground="#245e26", activeforeground="white",
            relief="solid", bd=1, highlightbackground=self.colors["header"], cursor="hand2",
            command=lambda: on_text_click("OK")
        )
        btn_ok.grid(row=3, column=7, columnspan=2, padx=4, pady=4, sticky="nsew")

        btn_annuler = tk.Button(
            keypad_frame, text="ANNULER", font=("Segoe UI", 14, "bold"),
            bg=self.colors["button_gray"], fg="white", activebackground="#414a55", activeforeground="white",
            relief="solid", bd=1, highlightbackground=self.colors["header"], cursor="hand2",
            command=lambda: on_text_click("ANNULER")
        )
        btn_annuler.grid(row=3, column=9, columnspan=2, padx=4, pady=4, sticky="nsew")

        for i in range(4):
            keypad_frame.grid_rowconfigure(i, weight=1)

    def jog_angle(self, motor_id, step):
        if not self.axis_vars[motor_id]["selected"].get():
            return

        entry = self.angle_entries[motor_id]
        try:
            current_val = float(entry.get())
        except ValueError:
            current_val = 0.0

        new_val = current_val + step
        if new_val < 0: new_val = 0
        if new_val > 90: new_val = 90

        entry.delete(0, tk.END)
        if int(new_val) == new_val:
            entry.insert(0, str(int(new_val)))
        else:
            entry.insert(0, str(new_val))

        direction = "moveleft" if step < 0 else "moveright"
        self.send_command({"command": direction, "motorID": motor_id, "angle": new_val})

    def move_all_selected(self):
        selected_motors = []
        for motor_id in range(1, 7):
            if self.axis_vars[motor_id]["selected"].get():
                angle = float(self.angle_entries[motor_id].get())
                selected_motors.append((motor_id, angle))

        for motor_id, angle in selected_motors:
            self.send_command({"command": "moveMotor", "motorID": motor_id, "angle": angle})

    def save_current_position(self):
        def proceed_save(position_name):
            position_data = {}
            for motor_id in range(1, 7):
                val = self.angle_entries[motor_id].get()
                position_data[motor_id] = float(val) if val else 0.0

            self.saved_positions[position_name] = position_data
            self.save_data_to_file()
            self.reset_all_motors()

        self.show_text_keypad_overlay("Enregistrer la position sous le nom :", proceed_save)

    def load_saved_position(self):
        if not self.saved_positions: return
        
        container = self.show_overlay()

        title_label = tk.Label(container, text="Charger une position", font=("Segoe UI", 16, "bold"), bg="white", fg="#1f2937")
        title_label.pack(pady=5)

        main_frame = tk.Frame(container, bg="white", bd=1, relief="solid")
        main_frame.pack(fill="both", expand=True, padx=20, pady=5)

        listbox = CardListbox(main_frame, font=("Segoe UI", 20, "bold"),
                               selectbackground=self.colors["row_selected"], bg="white",
                               fg=self.colors["text_dark"])
        listbox.pack(fill="both", expand=True, padx=5, pady=5)

        def refresh_list():
            listbox.delete(0, tk.END)
            for pos in self.saved_positions.keys():
                listbox.insert(tk.END, pos)

        refresh_list()

        def apply_selected_position():
            selection = listbox.curselection()
            if not selection: return
            pos_name = listbox.get(selection[0])
            pos_data = self.saved_positions[pos_name]

            for motor_id, angle in pos_data.items():
                self.angle_entries[motor_id].configure(state="normal")
                self.angle_entries[motor_id].delete(0, tk.END)
                if int(angle) == angle:
                    self.angle_entries[motor_id].insert(0, str(int(angle)))
                else:
                    self.angle_entries[motor_id].insert(0, str(angle))
                self.refresh_select_button(motor_id)

            self.hide_overlay()

        def delete_selected_position():
            selection = listbox.curselection()
            if not selection: return
            pos_name = listbox.get(selection[0])

            if pos_name in self.saved_positions:
                del self.saved_positions[pos_name]
                for link_name in list(self.saved_links.keys()):
                    self.saved_links[link_name] = [p for p in self.saved_links[link_name] if p != pos_name]
                    if len(self.saved_links[link_name]) < 2:
                        del self.saved_links[link_name]
                self.save_data_to_file()
                refresh_list()

        btn_frame = tk.Frame(container, bg="white")
        btn_frame.pack(fill="x", pady=5)

        tk.Button(btn_frame, text="CHARGER", command=apply_selected_position, bg=self.colors["button_green"],
                  fg="white", font=("Segoe UI", 12, "bold"), padx=15, pady=8).pack(side="left", padx=20)
        
        tk.Button(btn_frame, text="RETOUR", command=self.hide_overlay, bg=self.colors["button_gray"],
                  fg="white", font=("Segoe UI", 12, "bold"), padx=15, pady=8).pack(side="left", padx=5)

        tk.Button(btn_frame, text="SUPPRIMER", command=delete_selected_position, bg=self.colors["button_red"],
                  fg="white", font=("Segoe UI", 12, "bold"), padx=15, pady=8).pack(side="right", padx=20)

    def create_link(self):
        if len(self.saved_positions) < 2: return
        
        def proceed_create_link(link_name):
            container = self.show_overlay()

            title_lbl = tk.Label(container, text=f"Liaison : {link_name}", font=("Segoe UI", 16, "bold"), bg="white")
            title_lbl.pack(pady=5)

            content = tk.Frame(container, bg="white")
            content.pack(fill="both", expand=True, padx=10, pady=5)

            left_frame = tk.LabelFrame(content, text=" Dispo ", font=("Segoe UI", 10, "bold"), bg="white")
            left_frame.pack(side="left", fill="both", expand=True, padx=5)
            
            center_frame = tk.Frame(content, bg="white")
            center_frame.pack(side="left", fill="y", padx=5)
            
            right_frame = tk.LabelFrame(content, text=" Ordre ", font=("Segoe UI", 10, "bold"), bg="white")
            right_frame.pack(side="left", fill="both", expand=True, padx=5)

            available_listbox = CardListbox(left_frame, font=("Segoe UI", 16, "bold"), bg="white",
                                             fg=self.colors["text_dark"], selectbackground="#f8bbd0")
            available_listbox.pack(fill="both", expand=True, padx=5, pady=5)
            for position_name in self.saved_positions.keys():
                available_listbox.insert(tk.END, position_name)

            ordered_listbox = CardListbox(right_frame, font=("Segoe UI", 16, "bold"), bg="white",
                                           fg=self.colors["text_dark"], selectbackground="#bbdefb")
            ordered_listbox.pack(fill="both", expand=True, padx=5, pady=5)

            def add_position():
                selection = available_listbox.curselection()
                if selection: ordered_listbox.insert(tk.END, available_listbox.get(selection[0]))

            def remove_position():
                selection = ordered_listbox.curselection()
                if selection: ordered_listbox.delete(selection[0])

            def save_link_selection():
                ordered_positions = list(ordered_listbox.get(0, tk.END))
                if len(ordered_positions) >= 2:
                    self.saved_links[link_name] = ordered_positions
                    self.save_data_to_file()
                self.hide_overlay()

            tk.Button(center_frame, text="Add ➔", command=add_position, bg=self.colors["button_primary"], fg="white", font=("Segoe UI", 14, "bold"), width=10, pady=14).pack(pady=10)
            tk.Button(center_frame, text="✕ Del", command=remove_position, bg=self.colors["button_red"], fg="white", font=("Segoe UI", 14, "bold"), width=10, pady=14).pack(pady=10)
            tk.Button(center_frame, text="SAVE", command=save_link_selection, bg=self.colors["button_green"], fg="white", font=("Segoe UI", 14, "bold"), width=10, pady=14).pack(pady=10)
            tk.Button(center_frame, text="RETOUR", command=self.hide_overlay, bg=self.colors["button_gray"], fg="white", font=("Segoe UI", 14, "bold"), width=10, pady=14).pack(pady=10)

        self.show_text_keypad_overlay("Nom de la liaison à créer :", proceed_create_link)

    def run_link(self):
        if not self.saved_links: return
        
        container = self.show_overlay()

        title_label = tk.Label(container, text="Lancer une liaison (Link)", font=("Segoe UI", 16, "bold"), bg="white", fg="#1f2937")
        title_label.pack(pady=5)

        main_frame = tk.Frame(container, bg="white", bd=1, relief="solid")
        main_frame.pack(fill="both", expand=True, padx=20, pady=5)

        listbox = CardListbox(main_frame, font=("Segoe UI", 20, "bold"),
                               selectbackground=self.colors["row_selected"], bg="white",
                               fg=self.colors["text_dark"])
        listbox.pack(fill="both", expand=True, padx=5, pady=5)

        def refresh_link_list():
            listbox.delete(0, tk.END)
            for link in self.saved_links.keys():
                listbox.insert(tk.END, link)

        refresh_link_list()

        def start_selected_link():
            selection = listbox.curselection()
            if not selection: return
            link_name = listbox.get(selection[0])
            self.hide_overlay()
            self.execute_link_sequence(self.saved_links[link_name], 0)

        def delete_selected_link():
            selection = listbox.curselection()
            if not selection: return
            link_name = listbox.get(selection[0])

            if link_name in self.saved_links:
                del self.saved_links[link_name]
                self.save_data_to_file()
                refresh_link_list()

        btn_frame = tk.Frame(container, bg="white")
        btn_frame.pack(fill="x", pady=5)

        tk.Button(btn_frame, text="LANCER", command=start_selected_link, bg=self.colors["button_green"], fg="white", font=("Segoe UI", 12, "bold"), padx=20, pady=8).pack(side="left", padx=20)
        tk.Button(btn_frame, text="RETOUR", command=self.hide_overlay, bg=self.colors["button_gray"], fg="white", font=("Segoe UI", 12, "bold"), padx=20, pady=8).pack(side="left", padx=5)
        tk.Button(btn_frame, text="SUPPRIMER", command=delete_selected_link, bg=self.colors["button_red"], fg="white", font=("Segoe UI", 12, "bold"), padx=20, pady=8).pack(side="right", padx=20)

    def execute_link_sequence(self, positions_sequence, index):
        if index >= len(positions_sequence): return
        position_name = positions_sequence[index]
        if position_name not in self.saved_positions: return

        position_data = self.saved_positions[position_name]
        motors_list = []

        for motor_id, angle in position_data.items():
            self.angle_entries[motor_id].configure(state="normal")
            self.angle_entries[motor_id].delete(0, tk.END)
            if int(angle) == angle:
                self.angle_entries[motor_id].insert(0, str(int(angle)))
            else:
                self.angle_entries[motor_id].insert(0, str(angle))
            self.refresh_select_button(motor_id)
            motors_list.append({"motorID": motor_id, "angle": angle})

        self.send_command({"command": "moveMotors", "motors": motors_list})
        self.root.after(self.link_delay_ms, lambda: self.execute_link_sequence(positions_sequence, index + 1))

    def log(self, message):
        print(message)

    def send_command(self, command_dict):
        json_command = json.dumps(command_dict, ensure_ascii=False)
        self.log(json_command)


if __name__ == "__main__":
    root = tk.Tk()
    app = RobotControlApp(root)
    root.mainloop()
