import time
import struct
import ctypes
import os
import PS3MAPI
import sys

def get_resource_path(relative_path):
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class PS3Scanner:
    def __init__(self):
        self.ps3 = None
        self.pid = 0
        self.scanning = False
        
        self.current_type = "4 Bytes (Big Endian)"
        self.current_size = 4
        self.current_is_hex = False
        
        self.max_results = 75_000_000
        self.result_count = 0
        self.addresses = (ctypes.c_uint32 * self.max_results)()
        self.values = None 
        
        self.load_cpp_backend()

    def load_cpp_backend(self):
        self.cpp = None
        dll_path = get_resource_path("scanner_core.dll")
        try:
            if os.path.exists(dll_path):
                self.cpp = ctypes.CDLL(dll_path)
                self.cpp.first_scan_value.restype = ctypes.c_int
                self.cpp.first_scan_unknown.restype = ctypes.c_int
                self.cpp.next_scan.restype = ctypes.c_int
                print("C++ Backend Loaded Successfully.")
            else:
                print("WARNING: scanner_core.dll not found. Using slower Python fallback.")
        except Exception as e:
            print(f"C++ Load Error: {e}")

    def connect(self, ip):
        self.ps3 = PS3MAPI.PS3MAPI()
        self.ps3.ConnectTarget(ip)
        return [(p, self.ps3.Process.GetName(p)) for p in self.ps3.Process.GetPidProcesses()]

    def attach(self, pid):
        self.ps3.AttachProcess(pid)
        self.pid = pid

    def stop(self):
        self.scanning = False

    def compile_bytes(self, val_str, type_str, is_hex):
        if not val_str: return b""
        target_bytes = b""
        if type_str == "4 Bytes (Big Endian)":
            base = 16 if is_hex else 10
            target_bytes = struct.pack(">I", int(val_str, base))
        elif type_str == "Float (Big Endian)":
            target_bytes = struct.pack(">f", float(val_str))
        elif type_str == "String (ASCII)":
            target_bytes = val_str.encode("ascii")
        elif type_str == "String (UTF-16 BE)":
            target_bytes = val_str.encode("utf-16-be")
        elif type_str == "Array of byte":
            clean_hex = val_str.replace(" ", "").replace("0x", "")
            target_bytes = bytes.fromhex(clean_hex)
        return target_bytes

    def unpack_bytes(self, byte_data, type_str):
        try:
            if type_str == "4 Bytes (Big Endian)": return struct.unpack(">I", byte_data)[0]
            elif type_str == "Float (Big Endian)": return struct.unpack(">f", byte_data)[0]
        except: pass
        return None

    def format_value(self, byte_data, type_str, is_hex):
        try:
            if type_str == "Array of byte": return " ".join(f"{b:02X}" for b in byte_data)
            elif type_str == "String (ASCII)": return byte_data.decode("ascii", errors="replace")
            elif type_str == "String (UTF-16 BE)": return byte_data.decode("utf-16-be", errors="replace")
            val = self.unpack_bytes(byte_data, type_str)
            if val is None: return "?"
            if type_str == "4 Bytes (Big Endian)" and is_hex: return f"{val:X}"
            elif type_str == "Float (Big Endian)": return f"{val:.4f}"
            return str(val)
        except: return "?"

    def read_block(self, address, size):
        try: return self.ps3.Process.Memory.Get(self.pid, address, size)
        except: return b""

    def write_value(self, address, val_str, type_str, is_hex):
        target_bytes = self.compile_bytes(val_str, type_str, is_hex)
        self.ps3.Process.Memory.Set(self.pid, address, target_bytes)

    def get_ui_results(self, limit=1000):
        results = []
        count = min(self.result_count, limit)
        for i in range(count):
            addr = self.addresses[i]
            val_bytes = bytes(self.values[i*self.current_size : (i+1)*self.current_size])
            val_str = self.format_value(val_bytes, self.current_type, self.current_is_hex)
            results.append((f"{addr:08X}", val_str))
        return results

    # --- Match Engine ---
    def check_float_rounding(self, cur_val, target_numeric, rounding):
        if rounding == "Truncated": return int(cur_val) == int(target_numeric)
        elif rounding == "Normal": return abs(cur_val - target_numeric) <= 0.5 
        elif rounding == "Extreme": return abs(cur_val - target_numeric) <= 0.0001
        return False

    def first_scan(self, scan_type, start_addr, end_addr, target_bytes, type_str, is_hex, rounding="Off", progress_callback=None):
        self.scanning = True
        self.current_type = type_str
        self.current_size = len(target_bytes) if target_bytes else (4 if "Float" in type_str or "4 Bytes" in type_str else 1)
        self.current_is_hex = is_hex
        self.result_count = 0
        
        self.values = (ctypes.c_uint8 * (self.max_results * self.current_size))()
        alignment = 1 
        
        scan_map = {"Exact Value": 0, "Changed Value": 1, "Unchanged Value": 2, "Increased Value": 3, "Decreased Value": 4, "Bigger than": 5, "Smaller than": 6}
        val_map = {"4 Bytes (Big Endian)": 0, "Float (Big Endian)": 1}
        round_map = {"Off": 0, "Normal": 1, "Truncated": 2, "Extreme": 3}
        
        c_scan_type = scan_map.get(scan_type, -1)
        c_val_type = val_map.get(type_str, 2)
        c_rounding = round_map.get(rounding, 0)
        c_target = ctypes.create_string_buffer(target_bytes) if target_bytes else None
        
        self.ps3.Server.Timeout = 30000 
        chunk_size = 16 * 1024 * 1024 
        overlap = self.current_size - 1 
        total_size = end_addr - start_addr
        
        total_chunks = 0
        temp_curr = start_addr
        while temp_curr < end_addr:
            b_read = min(chunk_size, end_addr - temp_curr)
            total_chunks += 1
            if temp_curr + b_read >= end_addr: break
            temp_curr += (b_read - overlap)
            
        current = start_addr
        chunk_idx = 1
        
        target_numeric = self.unpack_bytes(target_bytes, type_str) if target_bytes else 0
        use_cpp = (self.cpp and c_scan_type != -1)

        while current < end_addr:
            if not self.scanning: break
            
            bytes_to_read = min(chunk_size, end_addr - current)
            progress_pct = ((current - start_addr) / total_size) * 100
            
            eta_seconds = (total_chunks - chunk_idx) * 7
            if progress_callback: progress_callback(f"Scanning {chunk_idx}/{total_chunks} | ETA: ~{eta_seconds}s", progress_pct)
            
            data = self.read_block(current, bytes_to_read)
            if not data:
                current += bytes_to_read if current + bytes_to_read >= end_addr else (bytes_to_read - overlap)
                chunk_idx += 1
                continue
            
            if progress_callback: progress_callback(f"Processing Filter {chunk_idx}/{total_chunks}...", progress_pct)
            
            if use_cpp:
                c_buffer = ctypes.create_string_buffer(data, len(data))
                if scan_type == "Unknown Initial Value":
                    self.result_count = self.cpp.first_scan_unknown(
                        c_buffer, current, len(data), self.current_size, alignment,
                        self.addresses, self.values, self.max_results, self.result_count
                    )
                else:
                    self.result_count = self.cpp.first_scan_value(
                        c_buffer, current, len(data), c_target, self.current_size, alignment,
                        c_scan_type, c_val_type, c_rounding,
                        self.addresses, self.values, self.max_results, self.result_count
                    )
            else:
                offset = 0
                while True:
                    if offset > len(data) - self.current_size: break
                    match = False
                    val = self.unpack_bytes(data[offset:offset+self.current_size], self.current_type)
                    
                    if scan_type in ["Bigger than", "Smaller than"]:
                        if val is not None and target_numeric is not None:
                            if scan_type == "Bigger than": match = val > target_numeric
                            elif scan_type == "Smaller than": match = val < target_numeric
                    elif c_rounding > 0 and scan_type == "Exact Value":
                        if val is not None and target_numeric is not None:
                            match = self.check_float_rounding(val, target_numeric, rounding)
                    else:
                        if scan_type == "Unknown Initial Value": match = True
                        else:
                            offset = data.find(target_bytes, offset)
                            if offset == -1: break
                            match = True
                            
                    if match and self.result_count < self.max_results:
                        self.addresses[self.result_count] = current + offset
                        for b_i in range(self.current_size):
                            self.values[(self.result_count * self.current_size) + b_i] = data[offset + b_i]
                        self.result_count += 1
                    offset += 1
            
            if current + bytes_to_read >= end_addr: current = end_addr
            else: current += (bytes_to_read - overlap)
            
            if current < end_addr:
                for _ in range(50):
                    if not self.scanning: break
                    time.sleep(0.1)
            chunk_idx += 1
            
        try: self.ps3.Server.Timeout = 5000
        except: pass
        self.scanning = False

    def next_scan(self, scan_type, target_bytes=None, rounding="Off", progress_callback=None):
        self.scanning = True
        self.ps3.Server.Timeout = 30000 
        
        chunk_size = 16 * 1024 * 1024
        overlap = self.current_size
        
        if self.result_count == 0:
            self.scanning = False
            raise ValueError("No addresses to filter.")

        new_addresses = (ctypes.c_uint32 * self.max_results)()
        new_values = (ctypes.c_uint8 * (self.max_results * self.current_size))()
        new_count = 0

        scan_map = {"Exact Value": 0, "Changed Value": 1, "Unchanged Value": 2, "Increased Value": 3, "Decreased Value": 4, "Bigger than": 5, "Smaller than": 6}
        val_map = {"4 Bytes (Big Endian)": 0, "Float (Big Endian)": 1}
        round_map = {"Off": 0, "Normal": 1, "Truncated": 2, "Extreme": 3}
        
        c_scan_type = scan_map.get(scan_type, -1)
        c_val_type = val_map.get(self.current_type, 2)
        c_rounding = round_map.get(rounding, 0)
        c_target = ctypes.create_string_buffer(target_bytes) if target_bytes else None
        
        target_numeric = self.unpack_bytes(target_bytes, self.current_type) if target_bytes else 0
        use_cpp = (self.cpp and c_scan_type != -1) 

        cluster_start_idx = 0
        
        while cluster_start_idx < self.result_count:
            if not self.scanning: break
            start_addr = self.addresses[cluster_start_idx]
            
            cluster_end_idx = cluster_start_idx
            while cluster_end_idx < self.result_count and (self.addresses[cluster_end_idx] - start_addr) <= chunk_size:
                cluster_end_idx += 1
                
            in_count = cluster_end_idx - cluster_start_idx
            read_length = (self.addresses[cluster_end_idx - 1] - start_addr) + overlap
            
            progress_pct = (cluster_end_idx / self.result_count) * 100
            if progress_callback: progress_callback(f"Reading Filter Cluster ({read_length/1024/1024:.2f} MB)...", progress_pct)
            
            data = self.read_block(start_addr, read_length)
            if not data or len(data) < read_length:
                cluster_start_idx = cluster_end_idx
                time.sleep(0.05)
                continue
                
            if progress_callback: progress_callback(f"Filtering Engine...", progress_pct)

            if use_cpp:
                c_buffer = ctypes.create_string_buffer(data, len(data))
                new_count = self.cpp.next_scan(
                    ctypes.byref(self.addresses, cluster_start_idx * 4),
                    ctypes.byref(self.values, cluster_start_idx * self.current_size),
                    in_count, c_buffer, start_addr, read_length,
                    c_scan_type, c_val_type, c_target, self.current_size, c_rounding,
                    new_addresses, new_values, new_count
                )
            else:
                for i in range(cluster_start_idx, cluster_end_idx):
                    addr = self.addresses[i]
                    offset = addr - start_addr
                    cur_b = data[offset : offset + overlap]
                    old_b = bytes(self.values[i*self.current_size : (i+1)*self.current_size])
                    match = False
                    
                    if c_rounding > 0 and scan_type == "Exact Value":
                        cv = self.unpack_bytes(cur_b, self.current_type)
                        if cv is not None and target_numeric is not None:
                            match = self.check_float_rounding(cv, target_numeric, rounding)
                    elif scan_type == "Exact Value": match = (cur_b == target_bytes)
                    elif scan_type == "Changed Value": match = (cur_b != old_b)
                    elif scan_type == "Unchanged Value": match = (cur_b == old_b)
                    elif scan_type in ["Bigger than", "Smaller than"]:
                        cv = self.unpack_bytes(cur_b, self.current_type)
                        if cv is not None and target_numeric is not None:
                            if scan_type == "Bigger than": match = cv > target_numeric
                            elif scan_type == "Smaller than": match = cv < target_numeric
                    elif scan_type in ["Increased Value", "Decreased Value"]:
                        cv = self.unpack_bytes(cur_b, self.current_type)
                        ov = self.unpack_bytes(old_b, self.current_type)
                        if cv is not None and ov is not None:
                            if scan_type == "Increased Value": match = (cv > ov)
                            else: match = (cv < ov)
                            
                    if match:
                        new_addresses[new_count] = addr
                        for b_i in range(self.current_size):
                            new_values[(new_count * self.current_size) + b_i] = cur_b[b_i]
                        new_count += 1

            cluster_start_idx = cluster_end_idx
            if cluster_end_idx < self.result_count:
                for _ in range(50):
                    if not self.scanning: break
                    time.sleep(0.1)

        self.addresses = new_addresses
        self.values = new_values
        self.result_count = new_count
        
        try: self.ps3.Server.Timeout = 5000
        except: pass
        self.scanning = False

    def disconnect(self):
        if self.ps3:
            try: self.ps3.DisconnectTarget()
            except: pass