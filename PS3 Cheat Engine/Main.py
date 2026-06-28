import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import ctypes as ct
import threading
import time
import sys
import os

from scanner_engine import PS3Scanner
from table_manager import CheatTableManager
from memory_viewer import MemoryViewer
from config_manager import ConfigManager 

def get_resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class PS3CheatEngineUI(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.title("PS3 Cheat Engine 1.7.3")
        self.geometry("950x700")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        try:
            self.iconbitmap(get_resource_path("icon.ico"))
        except Exception:
            pass 
            
        self.engine = PS3Scanner()
        
        self.create_custom_menu()
        self.create_widgets()
        self.create_context_menus()
        
        self.config_manager = ConfigManager(self) 
        self.config_manager.apply_theme(self.config_manager.data.get("theme", "dark"))
        
        if self.config_manager.data.get("ip"):
            self.ent_ip.delete(0, tk.END)
            self.ent_ip.insert(0, self.config_manager.data["ip"])
            
            if self.config_manager.data.get("auto_connect", False):
                self.after(500, self.connect_target)

        if len(sys.argv) > 1:
            filepath = sys.argv[1]
            if filepath.lower().endswith(".ps3ct") and os.path.exists(filepath):
                self.after(600, lambda: self.load_table_from_file(filepath))

    def apply_titlebar_theme(self, window, is_dark):
        """Applies Windows immersive dark mode to a specific window."""
        try:
            window.update()
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            set_window_attribute = ct.windll.dwmapi.DwmSetWindowAttribute
            get_parent = ct.windll.user32.GetParent
            hwnd = get_parent(window.winfo_id())
            rendering_policy = DWMWA_USE_IMMERSIVE_DARK_MODE
            value = ct.c_int(2 if is_dark else 0)
            set_window_attribute(hwnd, rendering_policy, ct.byref(value), ct.sizeof(value))
        except Exception:
            pass

    def set_titlebar_theme(self, is_dark):
        self.apply_titlebar_theme(self, is_dark)

    def update_all_windows_theme(self, theme_name):
        """Called by ConfigManager when a theme changes to update all active UIs."""
        is_dark = (theme_name == "dark")
        self.set_titlebar_theme(is_dark)
        
        if hasattr(self, 'update_menu_colors'):
            self.update_menu_colors(self.config_manager.bg_color, self.config_manager.fg_color, self.config_manager.btn_active)
            
        # Loop over all active child windows (Popups) and enforce theme
        for widget in self.winfo_children():
            if isinstance(widget, tk.Toplevel):
                widget.configure(bg=self.config_manager.bg_color)
                self.apply_titlebar_theme(widget, is_dark)
                
                # Check if it's the Memory Viewer specifically to update the hex text area
                if hasattr(widget, 'txt_dump'):
                    widget.txt_dump.config(
                        bg=self.config_manager.field_bg, 
                        fg=self.config_manager.field_fg, 
                        insertbackground=self.config_manager.field_fg
                    )

    def create_custom_menu(self):
        self.menu_frame = tk.Frame(self)
        self.menu_frame.pack(side="top", fill="x")

        self.btn_file = tk.Menubutton(self.menu_frame, text="File", relief="flat", padx=5, pady=2)
        self.btn_file.pack(side="left")
        self.menu_file = tk.Menu(self.btn_file, tearoff=0)
        self.menu_file.add_command(label="Load Table...", command=self.load_table)
        self.menu_file.add_command(label="Save Table...", command=self.save_table)
        self.menu_file.add_separator()
        self.menu_file.add_command(label="Exit", command=self.on_close)
        self.btn_file.config(menu=self.menu_file)

        self.btn_opts = tk.Menubutton(self.menu_frame, text="Options", relief="flat", padx=5, pady=2)
        self.btn_opts.pack(side="left")
        self.menu_opts = tk.Menu(self.btn_opts, tearoff=0)

        self.theme_menu = tk.Menu(self.menu_opts, tearoff=0)
        self.theme_menu.add_command(label="Dark Mode", command=lambda: self.config_manager.apply_theme("dark"))
        self.theme_menu.add_command(label="Light Mode", command=lambda: self.config_manager.apply_theme("light"))
        self.menu_opts.add_cascade(label="Theme", menu=self.theme_menu)
        
        self.var_autoconnect = tk.BooleanVar()
        self.menu_opts.add_checkbutton(label="Auto-Connect on Startup", variable=self.var_autoconnect, 
                                  command=lambda: self.config_manager.save_config("auto_connect", self.var_autoconnect.get()))
        self.btn_opts.config(menu=self.menu_opts)
        
    def update_menu_colors(self, bg_color, fg_color, active_bg):
        if hasattr(self, 'menu_frame'):
            self.menu_frame.config(bg=bg_color)
            self.btn_file.config(bg=bg_color, fg=fg_color, activebackground=active_bg, activeforeground=fg_color)
            self.btn_opts.config(bg=bg_color, fg=fg_color, activebackground=active_bg, activeforeground=fg_color)
            
            self.menu_file.config(bg=bg_color, fg=fg_color)
            self.menu_opts.config(bg=bg_color, fg=fg_color)
            self.theme_menu.config(bg=bg_color, fg=fg_color)

    def create_widgets(self):
        top_frame = ttk.Frame(self)
        top_frame.pack(side="top", fill="x", padx=10, pady=5)
        
        ttk.Label(top_frame, text="PS3 IP:").pack(side="left")
        self.ent_ip = ttk.Entry(top_frame, width=15)
        self.ent_ip.pack(side="left", padx=5)
        ttk.Button(top_frame, text="Connect", command=self.connect_target, width=10).pack(side="left", padx=5)
        
        self.lbl_status = ttk.Label(top_frame, text="Not Connected", foreground="#ff5555", font=("Segoe UI", 9, "bold"))
        self.lbl_status.pack(side="left", padx=10)
        
        self.drop_proc = ttk.Combobox(top_frame, state="readonly")
        self.drop_proc.pack(side="left", padx=5, fill="x", expand=True)
        
        self.btn_attach = ttk.Button(top_frame, text="Attach", command=self.attach_process, state="disabled", width=10)
        self.btn_attach.pack(side="left", padx=5)

        main_paned = ttk.PanedWindow(self, orient="horizontal")
        main_paned.pack(fill="both", expand=True, padx=10, pady=5)
        
        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=1)
        self.lbl_found_count = ttk.Label(left_frame, text="Found: 0")
        self.lbl_found_count.pack(anchor="w")
        self.tree_found = ttk.Treeview(left_frame, columns=("Address", "Value"), show="headings", height=15)
        self.tree_found.heading("Address", text="Address")
        self.tree_found.heading("Value", text="Value")
        self.tree_found.column("Address", width=100, anchor="w")
        self.tree_found.column("Value", width=100, anchor="w")
        self.tree_found.pack(fill="both", expand=True)
        
        self.tree_found.bind("<ButtonPress-1>", self.on_drag_start_found)
        self.tree_found.bind("<ButtonRelease-1>", self.on_drag_release_found)
        
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=2)
        
        scan_input_frame = ttk.Frame(right_frame)
        scan_input_frame.pack(fill="x", pady=10)
        ttk.Label(scan_input_frame, text="Value:").grid(row=0, column=0, sticky="w", pady=2)
        self.ent_value = ttk.Entry(scan_input_frame, width=25)
        self.ent_value.grid(row=0, column=1, padx=5, pady=2, sticky="w")
        
        self.var_hex = tk.BooleanVar(value=False)
        ttk.Checkbutton(scan_input_frame, text="Hex", variable=self.var_hex).grid(row=0, column=2, sticky="w")
        
        ttk.Label(scan_input_frame, text="Scan Type:").grid(row=1, column=0, sticky="w", pady=2)
        
        scan_options = ["Exact Value", "Unknown Initial Value", "Increased Value", "Decreased Value", "Changed Value", "Unchanged Value", "Bigger than", "Smaller than"]
        self.drop_scan_type = ttk.Combobox(scan_input_frame, values=scan_options, state="readonly", width=22)
        self.drop_scan_type.current(0)
        self.drop_scan_type.grid(row=1, column=1, padx=5, pady=2, sticky="w")
        self.drop_scan_type.bind("<<ComboboxSelected>>", self.on_scan_type_change)
        
        ttk.Label(scan_input_frame, text="Value Type:").grid(row=2, column=0, sticky="w", pady=2)
        self.drop_value_type = ttk.Combobox(scan_input_frame, values=["4 Bytes (Big Endian)", "Float (Big Endian)", "String (ASCII)", "String (UTF-16 BE)", "Array of byte"], state="readonly", width=22)
        self.drop_value_type.current(0)
        self.drop_value_type.grid(row=2, column=1, padx=5, pady=2, sticky="w")
        self.drop_value_type.bind("<<ComboboxSelected>>", self.on_value_type_change)
        
        ttk.Label(scan_input_frame, text="Rounding:").grid(row=3, column=0, sticky="w", pady=2)
        self.drop_rounding = ttk.Combobox(scan_input_frame, values=["Off", "Normal", "Truncated", "Extreme"], state="disabled", width=22)
        self.drop_rounding.current(0)
        self.drop_rounding.grid(row=3, column=1, padx=5, pady=2, sticky="w")
        
        mem_frame = ttk.LabelFrame(right_frame, text="Memory Scan Options")
        mem_frame.pack(fill="x", pady=10)
        ttk.Label(mem_frame, text="Start:").grid(row=0, column=0, padx=5, pady=5)
        self.ent_start = ttk.Entry(mem_frame, width=12)
        self.ent_start.insert(0, "30000000")
        self.ent_start.grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(mem_frame, text="Stop:").grid(row=0, column=2, padx=5, pady=5)
        self.ent_end = ttk.Entry(mem_frame, width=12)
        self.ent_end.insert(0, "31000000")
        self.ent_end.grid(row=0, column=3, padx=5, pady=5)
        
        btn_frame = ttk.Frame(right_frame)
        btn_frame.pack(fill="x", pady=10)
        self.btn_first_scan = ttk.Button(btn_frame, text="First Scan", command=self.start_first_scan, state="disabled")
        self.btn_first_scan.pack(side="left", padx=5)
        self.btn_next_scan = ttk.Button(btn_frame, text="Next Scan", command=self.start_next_scan, state="disabled")
        self.btn_next_scan.pack(side="left", padx=5)
        
        status_frame = ttk.Frame(right_frame)
        status_frame.pack(fill="x", pady=5)
        self.progress_bar = ttk.Progressbar(status_frame, orient="horizontal", mode="determinate")
        self.progress_bar.pack(fill="x", pady=5)
        self.lbl_scan_status = ttk.Label(status_frame, text="", foreground="#aaaaaa", font=("Segoe UI", 9))
        self.lbl_scan_status.pack(anchor="w")

        bottom_frame = ttk.Frame(self)
        bottom_frame.pack(side="bottom", fill="both", expand=True, padx=10, pady=10)
        
        tbl_btn_frame = ttk.Frame(bottom_frame)
        tbl_btn_frame.pack(fill="x", pady=(0, 5))
        self.btn_refresh = ttk.Button(tbl_btn_frame, text="Refresh List", command=self.start_refresh_table)
        self.btn_refresh.pack(side="left")
        
        cols = ("Active", "Description", "Address", "Type", "Value", "EnableVal", "DisableVal", "Len")
        self.tree_table = ttk.Treeview(bottom_frame, columns=cols, show="tree headings", height=8)
        for col in cols: self.tree_table.heading(col, text=col)
        
        self.tree_table.column("#0", width=40, stretch=False)
        self.tree_table.column("Active", width=50, anchor="center")
        self.tree_table.column("Description", width=150, anchor="w")
        self.tree_table.column("Address", width=100, anchor="w")
        self.tree_table.column("Type", width=130, anchor="w")
        self.tree_table.column("Value", width=100, anchor="w")
        self.tree_table.column("EnableVal", width=80, anchor="w")
        self.tree_table.column("DisableVal", width=80, anchor="w")
        self.tree_table.column("Len", width=40, anchor="center")
        self.tree_table.pack(fill="both", expand=True)

        self.tree_table.bind("<ButtonPress-1>", self.on_drag_start_table)
        self.tree_table.bind("<ButtonRelease-1>", self.on_drag_release_table)

    def create_context_menus(self):
        self.menu_found = tk.Menu(self, tearoff=0)
        self.menu_found.add_command(label="Add selected to Cheat Table", command=self.add_to_cheat_table)
        self.menu_found.add_command(label="Change values of selected...", command=self.change_found_values)
        self.menu_found.add_separator()
        self.menu_found.add_command(label="Browse Memory Region", command=self.browse_memory_found)
        self.tree_found.bind("<Button-3>", self.show_found_menu)

        self.menu_table = tk.Menu(self, tearoff=0)
        self.menu_table.add_command(label="Toggle Active", command=self.toggle_table_active)
        self.menu_table.add_separator()
        self.menu_table.add_command(label="Edit Record", command=self.show_edit_record_dialog)
        self.menu_table.add_command(label="Change Value Live", command=self.change_table_value)
        self.menu_table.add_command(label="Browse Memory Region", command=self.browse_memory_table)
        self.menu_table.add_separator()
        self.menu_table.add_command(label="Add Group Header", command=self.add_group_header)
        self.menu_table.add_command(label="Make Child of Selected Folder", command=self.make_child_node)
        self.menu_table.add_separator()
        self.menu_table.add_command(label="Delete Record", command=self.delete_table_record)
        
        self.tree_table.bind("<Button-3>", self.show_table_menu)
        self.tree_table.bind("<Double-1>", lambda e: self.toggle_table_active())

    def on_drag_start_found(self, event):
        self._drag_data_found = self.tree_found.selection()

    def on_drag_release_found(self, event):
        if not hasattr(self, '_drag_data_found') or not self._drag_data_found: return
        x, y = self.winfo_pointerxy()
        widget = self.winfo_containing(x, y)
        if widget == self.tree_table:
            rel_y = y - self.tree_table.winfo_rooty()
            target = self.tree_table.identify_row(rel_y)
            
            parent = ""
            if target:
                vals = self.tree_table.item(target, "values")
                if "Group" in vals[3]: parent = target
                
            val_type = self.drop_value_type.get()
            default_len = str(self.engine.current_size)
            for s in self._drag_data_found:
                item = self.tree_found.item(s)
                self.tree_table.insert(parent, "end", text="", values=("[]", "No Description", item['values'][0], val_type, item['values'][1], "", "", default_len))
            
            if parent: self.tree_table.item(parent, open=True)
        self._drag_data_found = None

    def on_drag_start_table(self, event):
        self._drag_data_table = self.tree_table.selection()

    def on_drag_release_table(self, event):
        if not hasattr(self, '_drag_data_table') or not self._drag_data_table: return
        target = self.tree_table.identify_row(event.y)
        
        if target:
            vals = self.tree_table.item(target, "values")
            if "Group" in vals[3]:
                for item in self._drag_data_table:
                    if item != target: self.tree_table.move(item, target, "end")
            else:
                parent = self.tree_table.parent(target)
                for item in self._drag_data_table:
                    if item != target: self.tree_table.move(item, parent, self.tree_table.index(target))
        else:
            for item in self._drag_data_table: self.tree_table.move(item, "", "end")
        self._drag_data_table = None

    def on_scan_type_change(self, event):
        if self.drop_scan_type.get() == "Unknown Initial Value":
            self.ent_value.config(state="disabled")
        else:
            self.ent_value.config(state="normal")
            
    def on_value_type_change(self, event):
        if "Float" in self.drop_value_type.get():
            self.drop_rounding.config(state="readonly")
        else:
            self.drop_rounding.set("Off")
            self.drop_rounding.config(state="disabled")

    def show_found_menu(self, event):
        iid = self.tree_found.identify_row(event.y)
        if iid and iid not in self.tree_found.selection():
            self.tree_found.selection_set(iid)
        if self.tree_found.selection():
            self.menu_found.post(event.x_root, event.y_root)

    def show_table_menu(self, event):
        iid = self.tree_table.identify_row(event.y)
        if iid and iid not in self.tree_table.selection():
            self.tree_table.selection_set(iid)
        if self.tree_table.selection() or iid == "":
            self.menu_table.post(event.x_root, event.y_root)

    def browse_memory_found(self):
        sel = self.tree_found.selection()
        if sel: MemoryViewer(self, self.engine, self.tree_found.item(sel[0], "values")[0])

    def browse_memory_table(self):
        sel = self.tree_table.selection()
        if sel and "Group" not in self.tree_table.item(sel[0], "values")[3]: 
            MemoryViewer(self, self.engine, self.tree_table.item(sel[0], "values")[2])

    def toggle_table_active(self):
        sel = self.tree_table.selection()
        if not sel: return
        item = sel[0]
        vals = list(self.tree_table.item(item, "values"))
        
        is_active = (vals[0] == "[X]")
        
        if "Group" in vals[3]:
            vals[0] = "[]" if is_active else "[X]"
            self.tree_table.item(item, values=vals)
            return

        target_addr = int(vals[2], 16)
        v_type = vals[3]
        
        if is_active:
            vals[0] = "[]"
            if vals[6].strip():
                try: self.engine.write_value(target_addr, vals[6], v_type, False)
                except Exception as e: messagebox.showerror("Write Error", f"Failed applying disable value: {e}")
        else:
            vals[0] = "[X]"
            if vals[5].strip():
                try: self.engine.write_value(target_addr, vals[5], v_type, False)
                except Exception as e: messagebox.showerror("Write Error", f"Failed applying enable value: {e}")
                
        self.tree_table.item(item, values=vals)
        self.start_refresh_table()

    def add_group_header(self):
        group_name = simpledialog.askstring("New Group", "Enter Header/Group Name:")
        if group_name:
            self.tree_table.insert("", "end", values=("[]", group_name, "", "Group Header", "", "", "", ""))

    def make_child_node(self):
        sel = self.tree_table.selection()
        if not sel or len(sel) != 1: 
            messagebox.showinfo("Select Node", "Please select the target group folder first.")
            return
            
        parent_item = sel[0]
        if "Group" not in self.tree_table.item(parent_item, "values")[3]:
            messagebox.showerror("Invalid Parent", "You can only nest items under a Group Header.")
            return

        found_sel = self.tree_found.selection()
        if not found_sel:
            messagebox.showinfo("Action Required", "Select an item from the top 'Found' list to nest it into this group.")
            return
            
        for s in found_sel:
            item = self.tree_found.item(s)
            val_type = self.drop_value_type.get()
            default_len = str(self.engine.current_size)
            self.tree_table.insert(parent_item, "end", text="", values=("[]", "No Description", item['values'][0], val_type, item['values'][1], "", "", default_len))
        
        self.tree_table.item(parent_item, open=True)

    def show_edit_record_dialog(self):
        sel = self.tree_table.selection()
        if not sel: return
        item = sel[0]
        vals = list(self.tree_table.item(item, "values"))
        
        dialog = tk.Toplevel(self)
        dialog.title("Edit Record")
        dialog.geometry("320x350")
        
        # Apply the actual window background and Titlebar theme explicitly
        dialog.configure(bg=self.config_manager.bg_color)
        self.apply_titlebar_theme(dialog, self.config_manager.data.get("theme", "dark") == "dark")
        
        fields = [("Description:", vals[1]), ("Type:", vals[3]), ("Enable Value:", vals[5]), 
                  ("Disable Value:", vals[6]), ("Length (Bytes):", vals[7])]
        entries = []
        
        for i, (label_text, current_val) in enumerate(fields):
            ttk.Label(dialog, text=label_text).pack(pady=(10, 0), anchor="w", padx=20)
            if label_text == "Type:":
                ent = ttk.Combobox(dialog, values=["4 Bytes (Big Endian)", "Float (Big Endian)", "String (ASCII)", "String (UTF-16 BE)", "Array of byte", "Group Header"], state="readonly")
                ent.set(current_val)
            else:
                ent = ttk.Entry(dialog)
                ent.insert(0, current_val)
            ent.pack(fill="x", padx=20)
            entries.append(ent)
            
        def save_changes():
            vals[1] = entries[0].get()
            vals[3] = entries[1].get()
            vals[5] = entries[2].get()
            vals[6] = entries[3].get()
            vals[7] = entries[4].get()
            self.tree_table.item(item, values=vals)
            dialog.destroy()
            
        ttk.Button(dialog, text="Save Settings", command=save_changes).pack(pady=20)

    def change_found_values(self):
        sel = self.tree_found.selection()
        if not sel: return
        new_val = simpledialog.askstring("Change Values", f"Enter new value for {len(sel)} items:")
        if new_val is not None:
            threading.Thread(target=self._change_found_values_worker, args=(sel, new_val), daemon=True).start()

    def _change_found_values_worker(self, sel, new_val):
        val_type = self.drop_value_type.get()
        is_hex = self.var_hex.get()
        for s in sel:
            addr = int(self.tree_found.item(s, "values")[0], 16)
            try: self.engine.write_value(addr, new_val, val_type, is_hex)
            except Exception as e: print(f"Error writing: {e}")
            time.sleep(1) 
            
        self.after(0, messagebox.showinfo, "Finished", "Batch value change completed.")
        self.start_refresh_table()

    def change_table_value(self):
        sel = self.tree_table.selection()
        if not sel: return
        item = sel[0]
        vals = list(self.tree_table.item(item, "values"))
        if "Group" in vals[3]: return
        
        new_val = simpledialog.askstring("Change Value", "Enter new memory value directly:", initialvalue=vals[4])
        if new_val is not None:
            try:
                self.engine.write_value(int(vals[2], 16), new_val, vals[3], False)
                vals[4] = new_val
                self.tree_table.item(item, values=vals)
            except Exception as e:
                messagebox.showerror("Write Error", f"Failed to write memory:\n{e}")

    def delete_table_record(self):
        for item in self.tree_table.selection(): self.tree_table.delete(item)

    def start_refresh_table(self):
        if not self.engine.ps3 or not self.engine.pid: return
        threading.Thread(target=self.refresh_table_worker, daemon=True).start()

    def refresh_table_worker(self):
        def recurse_refresh(parent=""):
            for item in self.tree_table.get_children(parent):
                vals = list(self.tree_table.item(item, "values"))
                if "Group" not in vals[3]:
                    try:
                        addr = int(vals[2], 16)
                        v_type = vals[3]
                        length = int(vals[7]) if vals[7].isdigit() else 4
                        size = length if "String" in v_type or "Array" in v_type else (4 if "Float" in v_type or "4 Bytes" in v_type else 1)
                        
                        data = self.engine.read_block(addr, size)
                        if data:
                            new_val_str = self.engine.format_value(data, v_type, self.var_hex.get())
                            vals[4] = new_val_str
                            self.after(0, self.tree_table.item, item, {"values": vals})
                    except Exception: pass
                    time.sleep(0.01) 
                recurse_refresh(item) 
        recurse_refresh()

    def _extract_tree_data(self, parent=""):
        data = []
        for child in self.tree_table.get_children(parent):
            vals = list(self.tree_table.item(child, "values"))
            kids = self._extract_tree_data(child)
            data.append({"values": vals, "children": kids})
        return data

    def _insert_tree_data(self, data_list, parent=""):
        for item_dict in data_list:
            child_id = self.tree_table.insert(parent, "end", text="", values=item_dict["values"])
            if item_dict["children"]:
                self._insert_tree_data(item_dict["children"], child_id)
                self.tree_table.item(child_id, open=True)

    def save_table(self):
        filepath = filedialog.asksaveasfilename(defaultextension=".PS3CT", filetypes=[("PS3 Cheat Tables", "*.PS3CT")])
        if not filepath: return
        try:
            hierarchical_data = self._extract_tree_data()
            CheatTableManager.save_table(filepath, hierarchical_data)
            messagebox.showinfo("Saved", "Table saved successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save:\n{e}")

    def load_table(self):
        filepath = filedialog.askopenfilename(filetypes=[("PS3 Cheat Tables", "*.PS3CT")])
        if filepath:
            self.load_table_from_file(filepath)

    def load_table_from_file(self, filepath):
        try:
            records = CheatTableManager.load_table(filepath)
            for item in self.tree_table.get_children(): self.tree_table.delete(item)
            self._insert_tree_data(records)
            self.start_refresh_table()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load file:\n{e}")

    def connect_target(self):
        ip = self.ent_ip.get().strip()
        if not ip: return
        try:
            self.config_manager.save_config("ip", ip)
            processes = self.engine.connect(ip)
            self.lbl_status.config(text="Connected", foreground="#55ff55")
            self.btn_attach.config(state="normal")
            dropdown_strings = [f"{p:#010x} | {name}" for (p, name) in processes]
            if dropdown_strings:
                self.drop_proc['values'] = dropdown_strings
                self.drop_proc.current(0)
        except Exception as e:
            messagebox.showerror("Connection Error", str(e))

    def attach_process(self):
        try:
            selected_idx = self.drop_proc.get()
            if not selected_idx: return
            raw_hex = selected_idx.split(" | ")[0]
            self.engine.attach(int(raw_hex, 16))
            self.btn_first_scan.config(state="normal")
            messagebox.showinfo("Success", f"Attached to {raw_hex}")
        except Exception as e:
            messagebox.showerror("Attach Error", str(e))

    def add_to_cheat_table(self, event=None):
        sel = self.tree_found.selection()
        if not sel: return
        val_type = self.drop_value_type.get()
        default_len = str(self.engine.current_size)
        for s in sel:
            item = self.tree_found.item(s)
            self.tree_table.insert("", "end", text="", values=("[]", "No Description", item['values'][0], val_type, item['values'][1], "", "", default_len))

    def update_progress_ui(self, status_text, progress_pct):
        self.after(0, self.lbl_scan_status.config, {"text": status_text, "foreground": "#ffff55"})
        self.after(0, self.progress_bar.config, {"value": progress_pct})

    def update_results_list(self):
        for item in self.tree_found.get_children(): self.tree_found.delete(item)
        display_results = self.engine.get_ui_results(limit=1000)
        for hex_addr, val_str in display_results:
            self.tree_found.insert("", "end", values=(hex_addr, val_str))
        self.lbl_found_count.config(text=f"Found: {self.engine.result_count:,}")

    def finalize_scan(self, success_msg):
        self.btn_first_scan.config(state="normal")
        if self.engine.result_count > 0: self.btn_next_scan.config(state="normal")
        self.progress_bar.config(value=0)
        self.update_results_list()
        self.lbl_scan_status.config(text=success_msg, foreground="#55ff55")
        self.start_refresh_table()

    def start_first_scan(self):
        if self.engine.scanning: return
        threading.Thread(target=self.run_first_scan_thread, daemon=True).start()

    def run_first_scan_thread(self):
        self.after(0, self.btn_first_scan.config, {"state": "disabled"})
        self.after(0, self.btn_next_scan.config, {"state": "disabled"})
        try:
            start_addr = max(0, min(int(self.ent_start.get().strip().replace("0x", "").replace(" ", ""), 16), 0xFFFFFFFF))
            end_addr = max(0, min(int(self.ent_end.get().strip().replace("0x", "").replace(" ", ""), 16), 0xFFFFFFFF))
            
            scan_type = self.drop_scan_type.get()
            val_type = self.drop_value_type.get()
            is_hex = self.var_hex.get()
            rounding = self.drop_rounding.get()
            
            target_bytes = None
            if scan_type != "Unknown Initial Value":
                val_str = self.ent_value.get().strip()
                target_bytes = self.engine.compile_bytes(val_str, val_type, is_hex)
            
            self.engine.first_scan(scan_type, start_addr, end_addr, target_bytes, val_type, is_hex, rounding, self.update_progress_ui)
            
            if not self.engine.scanning: 
                self.after(0, self.finalize_scan, "First Scan Finished!")
        except Exception as e:
            self.after(0, messagebox.showerror, "Error", str(e))
            self.engine.stop()
            self.after(0, self.finalize_scan, "Scan Error")

    def start_next_scan(self):
        if self.engine.scanning: return
        threading.Thread(target=self.run_next_scan_thread, daemon=True).start()

    def run_next_scan_thread(self):
        self.after(0, self.btn_first_scan.config, {"state": "disabled"})
        self.after(0, self.btn_next_scan.config, {"state": "disabled"})
        try:
            scan_type = self.drop_scan_type.get()
            rounding = self.drop_rounding.get()
            target_bytes = None
            
            if scan_type in ["Exact Value", "Bigger than", "Smaller than"]:
                val_str = self.ent_value.get().strip()
                target_bytes = self.engine.compile_bytes(val_str, self.engine.current_type, self.engine.current_is_hex)
            
            self.engine.next_scan(scan_type, target_bytes, rounding, self.update_progress_ui)
            
            if not self.engine.scanning:
                self.after(0, self.finalize_scan, "Next Scan Finished!")
        except Exception as e:
            self.after(0, messagebox.showerror, "Error", str(e))
            self.engine.stop()
            self.after(0, self.finalize_scan, "Scan Error")

    def on_close(self):
        self.engine.stop()
        self.engine.disconnect()
        self.destroy()

if __name__ == "__main__":
    app = PS3CheatEngineUI()
    app.mainloop()