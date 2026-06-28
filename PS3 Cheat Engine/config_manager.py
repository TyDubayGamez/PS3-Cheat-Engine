import json
import os
import sys
from tkinter import ttk

if getattr(sys, 'frozen', False):
    base_path = os.path.dirname(sys.executable)
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(base_path, "config.json")

class ConfigManager:
    def __init__(self, root):
        self.root = root
        self.data = self.load_config()

        # Define default class variables for colors so other windows can query them
        self.bg_color = "#2b2b2b"
        self.fg_color = "#ffffff"
        self.field_bg = "#1e1e1e"
        self.field_fg = "#ffffff"
        self.btn_bg = "#3c3c3c"
        self.btn_active = "#505050"
        self.select_bg = "#005a9e"

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f: 
                    return json.load(f)
            except: pass
        return {"ip": "", "theme": "dark", "auto_connect": False}

    def save_config(self, key=None, value=None):
        if key and value is not None:
            self.data[key] = value

        save_data = {
            "ip": self.data.get("ip", ""),
            "theme": self.data.get("theme", "dark"),
            "auto_connect": self.data.get("auto_connect", False)
        }
        
        try:
            with open(CONFIG_FILE, "w") as f: 
                json.dump(save_data, f, indent=4)
        except Exception as e: 
            print(f"Failed to save config: {e}")

    def apply_theme(self, theme_name):
        self.save_config("theme", theme_name)
        
        if theme_name == "dark":
            self.bg_color, self.fg_color = "#2b2b2b", "#ffffff"
            self.field_bg, self.field_fg = "#1e1e1e", "#ffffff"
            self.btn_bg, self.btn_active = "#3c3c3c", "#505050"
            self.select_bg = "#005a9e"
        else:
            self.bg_color, self.fg_color = "#f0f0f0", "#000000"
            self.field_bg, self.field_fg = "#ffffff", "#000000"
            self.btn_bg, self.btn_active = "#e0e0e0", "#d0d0d0"
            self.select_bg = "#0078d7"
            
        self.root.configure(bg=self.bg_color)
        style = ttk.Style(self.root)
        style.theme_use('clam')
        
        style.configure(".", background=self.bg_color, foreground=self.fg_color, darkcolor=self.bg_color, lightcolor=self.bg_color)
        style.configure("TButton", background=self.btn_bg, borderwidth=1)
        style.map("TButton", background=[("active", self.btn_active), ("disabled", self.bg_color)])
        
        style.configure("TCombobox", fieldbackground=self.field_bg, background=self.btn_bg, foreground=self.field_fg)
        style.map("TCombobox", fieldbackground=[("readonly", self.field_bg)], selectbackground=[("readonly", self.select_bg)], selectforeground=[("readonly", "#ffffff")])
        self.root.option_add('*TCombobox*Listbox.background', self.field_bg)
        self.root.option_add('*TCombobox*Listbox.foreground', self.field_fg)
        self.root.option_add('*TCombobox*Listbox.selectBackground', self.select_bg)
        
        style.configure("TEntry", fieldbackground=self.field_bg, foreground=self.field_fg, borderwidth=1)
        
        style.configure("Treeview", background=self.field_bg, fieldbackground=self.field_bg, foreground=self.field_fg, borderwidth=1, rowheight=20)
        style.map("Treeview", background=[("selected", self.select_bg)], foreground=[("selected", "#ffffff")])
        style.configure("Treeview.Heading", background=self.btn_bg, foreground=self.fg_color, relief="flat")
        style.map("Treeview.Heading", background=[("active", self.btn_active)])
        
        style.configure("TLabelframe", background=self.bg_color, borderwidth=1, bordercolor=self.btn_active)
        style.configure("TLabelframe.Label", background=self.bg_color, foreground=self.fg_color)
        
        # Trigger updates across Main.py and ALL open Toplevels dynamically
        if hasattr(self.root, 'update_all_windows_theme'):
            self.root.update_all_windows_theme(theme_name)