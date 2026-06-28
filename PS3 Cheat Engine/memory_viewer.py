import tkinter as tk
from tkinter import ttk, messagebox

class MemoryViewer(tk.Toplevel):
    def __init__(self, parent, engine, initial_address="30000000"):
        super().__init__(parent)
        self.title("Memory Viewer")
        self.geometry("600x450")
        self.engine = engine
        self.parent_ui = parent # Reference back to Main.py to pull the theme
        
        # Pull global config
        cm = self.parent_ui.config_manager
        self.configure(bg=cm.bg_color)
        
        if hasattr(self.parent_ui, 'apply_titlebar_theme'):
            self.parent_ui.apply_titlebar_theme(self, cm.data.get("theme", "dark") == "dark")
            
        self.create_widgets(initial_address, cm)

    def create_widgets(self, initial_address, cm):
        # Switched to ttk.Frame so it inherits the master style properly
        top_frame = ttk.Frame(self)
        top_frame.pack(side="top", fill="x", padx=10, pady=10)
        
        # Switched to ttk.Label
        ttk.Label(top_frame, text="Address (Hex):").pack(side="left")
        
        self.ent_address = ttk.Entry(top_frame, width=15)
        self.ent_address.insert(0, initial_address)
        self.ent_address.pack(side="left", padx=5)
        
        ttk.Button(top_frame, text="Refresh", command=self.refresh_memory).pack(side="left", padx=5)
        
        # Using colors mapped directly from config_manager
        self.txt_dump = tk.Text(
            self, 
            bg=cm.field_bg, 
            fg=cm.field_fg, 
            insertbackground=cm.field_fg, 
            font=("Courier", 10), 
            state="disabled"
        )
        self.txt_dump.pack(fill="both", expand=True, padx=10, pady=10)
        
        if self.engine.ps3 and self.engine.pid:
            self.refresh_memory()

    def refresh_memory(self):
        if not self.engine.ps3 or not self.engine.pid:
            messagebox.showwarning("Warning", "Not attached to a process.", parent=self)
            return
            
        try:
            addr_str = self.ent_address.get().strip().replace("0x", "")
            start_addr = int(addr_str, 16)
            
            read_size = 256
            data = self.engine.read_block(start_addr, read_size)
            
            if not data:
                raise ValueError("Failed to read memory at this address.")
                
            dump_text = self.format_hex_dump(start_addr, data)
            
            self.txt_dump.config(state="normal")
            self.txt_dump.delete("1.0", "end")
            self.txt_dump.insert("end", dump_text)
            self.txt_dump.config(state="disabled")
            
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def format_hex_dump(self, start_addr, data):
        lines = []
        for i in range(0, len(data), 16):
            chunk = data[i:i+16]
            hex_str = " ".join(f"{b:02X}" for b in chunk)
            hex_str = hex_str.ljust(47) 
            ascii_str = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
            lines.append(f"{start_addr + i:08X} - {hex_str} - {ascii_str}")
        return "\n".join(lines)