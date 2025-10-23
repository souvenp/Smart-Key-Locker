import os
import sys
import time
import json
import threading
from datetime import datetime
from PIL import Image, ImageDraw
import pystray
from pynput import keyboard, mouse
import tkinter as tk
from tkinter import messagebox, Toplevel, Label, Entry, Button, Frame, Scrollbar, Text, END

# --- 全局配置和状态变量 ---
CONFIG_FILE = "key_locker_config.json"
LOG_FILE = "lock_log.txt"

DEFAULT_SETTINGS = {
    "unlock_shortcut": "ctrl+alt+p",
    "lock_shortcut": "ctrl+alt+l",
    "inactivity_minutes": 5
}

class ScreenLockerApp:
    def __init__(self):
        self.settings = self.load_settings()
        self.is_locked = False
        self.last_activity_time = time.time()
        
        self.last_mouse_move_log_time = 0
        
        self.log_listener_kb = None
        self.log_listener_mouse = None
        self.lock_hotkey = None
        self.activity_listener_mouse = None
        self.activity_listener_kb = None # <<< ADDED: 初始化键盘活动监听器变量
        
        self.unlock_pressed_keys = set()
        
        self.icon = None
        self.settings_window = None
        self.root = tk.Tk()
        self.root.withdraw()

    # --- 辅助函数 ---
    def log(self, message):
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")
        except Exception as e: print(f"Error writing to log file: {e}")

    def load_settings(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f: return {**DEFAULT_SETTINGS, **json.load(f)}
            except (json.JSONDecodeError, IOError): return DEFAULT_SETTINGS
        else: self.save_settings(DEFAULT_SETTINGS); return DEFAULT_SETTINGS

    def save_settings(self, settings_to_save=None):
        if settings_to_save is None: settings_to_save = self.settings
        with open(CONFIG_FILE, "w") as f: json.dump(settings_to_save, f, indent=4)

    def format_shortcut_for_hotkey(self, shortcut_str):
        parts = shortcut_str.lower().split('+')
        formatted_parts = [f'<{part.strip()}>' if part.strip() in ['ctrl', 'alt', 'shift', 'cmd', 'win'] else part.strip() for part in parts]
        return "+".join(formatted_parts)
        
    def _normalize_key(self, key):
        # 仅供热键和非锁定状态使用
        if isinstance(key, keyboard.Key):
            name = key.name
            return name[:-2] if name.endswith(('_l', '_r')) else name
        elif isinstance(key, keyboard.KeyCode):
            if key.char: return key.char.lower()
        return None
        
    def _format_key_for_logging(self, key):
        # 用于日志输出，将 VK_code 翻译成字符
        if isinstance(key, keyboard.KeyCode):
            if key.char: return f"'{key.char}'"
            if hasattr(key, 'vk'):
                if 65 <= key.vk <= 90: return f"'{chr(key.vk)}'" # A-Z
                if 48 <= key.vk <= 57: return f"'{chr(key.vk)}'" # 0-9
                return f"VK_{key.vk}"
        if hasattr(key, 'name'): return key.name
        return str(key)
        
    # *** FIX: 最终的、最可靠的解锁按键识别函数 ***
    def _normalize_key_for_unlock(self, key):
        # 1. 识别功能键
        if isinstance(key, keyboard.Key):
            name = key.name
            return name[:-2] if name.endswith(('_l', '_r')) else name
            
        # 2. 识别字符键 (使用键码和字符双重验证)
        elif isinstance(key, keyboard.KeyCode):
            # 方案A: 优先使用 .char 属性
            if key.char: return key.char.lower()
            
            # 方案B: 使用 VK 码识别字母 a-z (97-122) 和 A-Z (65-90)
            if hasattr(key, 'vk'):
                vk = key.vk
                if 97 <= vk <= 122: return chr(vk) # a-z
                if 65 <= vk <= 90: return chr(vk).lower() # A-Z -> a-z
                if 48 <= vk <= 57: return chr(vk) # 0-9
        return None

    # --- 核心锁定与解锁 ---
    def lock_screen(self, *args):
        if self.is_locked: return
        self.stop_lock_hotkey()
        self.is_locked = True
        self.log("Screen Locked"); print("\n>>> SCREEN LOCKED <<<")
        self.update_tray_icon(); self.last_mouse_move_log_time = 0
        self.unlock_pressed_keys.clear()
        
        self.log_listener_mouse = mouse.Listener(on_click=self.on_locked_click, on_move=self.on_locked_move, suppress=True)
        self.log_listener_mouse.start()
        self.start_unlock_listener()

    def unlock_screen(self, *args):
        if not self.is_locked: return
        self.stop_unlock_listener()
        if self.log_listener_mouse: self.log_listener_mouse.stop(); self.log_listener_mouse = None
        self.is_locked = False
        self.log("Screen Unlocked"); print("\n>>> SCREEN UNLOCKED <<<")
        self.update_tray_icon(); self.update_last_activity()
        self.start_lock_hotkey()

    # --- 事件处理函数 ---
    def on_locked_click(self, x, y, button, pressed):
        if pressed: self.log(f"Blocked Mouse Click: {button} at ({x}, {y})")

    def on_locked_move(self, x, y):
        current_time = time.time()
        if current_time - self.last_mouse_move_log_time > 2:
            self.log(f"Blocked Mouse Move detected at ({x}, {y})"); self.last_mouse_move_log_time = current_time

    def start_lock_hotkey(self):
        shortcut = self.format_shortcut_for_hotkey(self.settings['lock_shortcut'])
        try:
            self.lock_hotkey = keyboard.GlobalHotKeys({shortcut: lambda: self.root.after(0, self.lock_screen)})
            self.lock_hotkey.start()
            print(f"Lock hotkey '{shortcut}' is active.")
        except Exception as e: print(f"Failed to start lock hotkey: {e}")

    def stop_lock_hotkey(self):
        if self.lock_hotkey: self.lock_hotkey.stop(); self.lock_hotkey = None; print("Lock hotkey deactivated.")

    def start_unlock_listener(self):
        self.log_listener_kb = keyboard.Listener(on_press=self.on_unlock_press, on_release=self.on_unlock_release, suppress=True)
        self.log_listener_kb.start()
        print(f"Unlock key listener is now active for '{self.settings['unlock_shortcut']}'. Waiting for key presses...")
        
    def stop_unlock_listener(self):
        if self.log_listener_kb: self.log_listener_kb.stop(); self.log_listener_kb = None; print("Unlock key listener deactivated.")
            
    def on_unlock_press(self, key):
        print(f"[DEBUG] Unlock listener heard a KEY PRESS: {key}")
        
        self.log(f"Blocked Keyboard Input: {self._format_key_for_logging(key)}")
        
        normalized_key = self._normalize_key_for_unlock(key)
        if normalized_key:
            self.unlock_pressed_keys.add(normalized_key)
            print(f"[DEBUG] Current unlock keys held: {self.unlock_pressed_keys}")
        
        unlock_keys_set = set(self.settings.get("unlock_shortcut").split('+'))
        if unlock_keys_set.issubset(self.unlock_pressed_keys):
            print("[DEBUG] --- UNLOCK COMBINATION MATCHED ---")
            self.root.after(0, self.unlock_screen)
        
    def on_unlock_release(self, key):
        print(f"[DEBUG] Unlock listener heard a KEY RELEASE: {key}")
        self.unlock_pressed_keys.discard(self._normalize_key_for_unlock(key))

    # --- 闲置监控 ---
    def update_last_activity(self, *args): self.last_activity_time = time.time()
            
    def start_inactivity_monitor(self):
        def loop():
            while True:
                time.sleep(5)
                timeout_seconds = self.settings.get("inactivity_minutes", 0) * 60
                if timeout_seconds > 0 and not self.is_locked:
                    if time.time() - self.last_activity_time > timeout_seconds: self.root.after(0, self.lock_screen)
        threading.Thread(target=loop, daemon=True).start()

    def start_activity_listeners(self):
        self.activity_listener_mouse = mouse.Listener(on_move=self.update_last_activity, on_click=self.update_last_activity, on_scroll=self.update_last_activity)
        self.activity_listener_mouse.start()
        # <<< ADDED: 创建并启动键盘活动监听器
        self.activity_listener_kb = keyboard.Listener(on_press=self.update_last_activity)
        self.activity_listener_kb.start()


    def stop_activity_listeners(self):
        if self.activity_listener_mouse: self.activity_listener_mouse.stop()
        if self.activity_listener_kb: self.activity_listener_kb.stop() # <<< ADDED: 停止键盘活动监听器

    # --- 系统托盘和UI (保持不变) ---
    def create_icon_image(self, locked=False):
        width, height = 64, 64; color1, color2 = "black", "red" if locked else "green"
        image = Image.new("RGB", (width, height), color1); dc = ImageDraw.Draw(image)
        dc.rectangle((width // 4, height // 4, width * 3 // 4, height * 3 // 4), fill=color2)
        return image
    
    def update_tray_icon(self):
        if self.icon: self.icon.icon = self.create_icon_image(self.is_locked); self.icon.menu = self.create_menu()

    def create_menu(self):
        lock_shortcut_text = self.settings.get('lock_shortcut').replace('+', '+').upper()
        return pystray.Menu(
            pystray.MenuItem(lambda item: "Status: Locked" if self.is_locked else "Status: Unlocked", None, enabled=False),
            pystray.MenuItem(f"Lock Now ({lock_shortcut_text})", self.lock_screen, visible=lambda item: not self.is_locked),
            pystray.MenuItem("Settings", self.schedule_settings_window, visible=lambda item: not self.is_locked),
            pystray.MenuItem("Exit", self.exit_app))

    def schedule_settings_window(self): self.root.after(0, self._create_settings_window)

    def _create_settings_window(self):
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.lift(); self.settings_window.focus_force(); return
        win = Toplevel(self.root); self.settings_window = win
        win.title("Settings & Log Viewer"); win.geometry("500x550"); win.resizable(True, True); win.attributes('-topmost', True)
        settings_frame = Frame(win, padx=10, pady=10); settings_frame.pack(fill='x')
        Label(settings_frame, text="Lock Shortcut:").grid(row=0, column=0, sticky='w')
        lock_entry = Entry(settings_frame); lock_entry.insert(0, self.settings.get("lock_shortcut", "")); lock_entry.grid(row=0, column=1, sticky='ew')
        Label(settings_frame, text="Unlock Shortcut:").grid(row=1, column=0, sticky='w', pady=5)
        unlock_entry = Entry(settings_frame); unlock_entry.insert(0, self.settings.get("unlock_shortcut", "")); unlock_entry.grid(row=1, column=1, sticky='ew')
        Label(settings_frame, text="Auto-lock (minutes):").grid(row=2, column=0, sticky='w')
        inactivity_entry = Entry(settings_frame); inactivity_entry.insert(0, str(self.settings.get("inactivity_minutes", ""))); inactivity_entry.grid(row=2, column=1, sticky='ew')
        settings_frame.columnconfigure(1, weight=1)
        log_frame = Frame(win, padx=10, pady=5); log_frame.pack(expand=True, fill='both')
        Label(log_frame, text="Lock Event Log:").pack(anchor='w')
        text_area_frame = Frame(log_frame); text_area_frame.pack(expand=True, fill='both')
        log_text = Text(text_area_frame, wrap='word', state='disabled', height=15); scrollbar = Scrollbar(text_area_frame, command=log_text.yview)
        log_text.config(yscrollcommand=scrollbar.set); scrollbar.pack(side='right', fill='y'); log_text.pack(side='left', expand=True, fill='both')
        def load_log():
            log_text.config(state='normal'); log_text.delete('1.0', END)
            try:
                with open(LOG_FILE, "r", encoding="utf-8") as f: lines = f.readlines(); log_text.insert(END, "".join(lines[-200:]))
            except FileNotFoundError: log_text.insert(END, "Log file not found.")
            log_text.see(END); log_text.config(state='disabled')
        def clear_log():
            if messagebox.askyesno("Confirm", "Are you sure you want to permanently delete the log file?", parent=win):
                try: os.remove(LOG_FILE); load_log()
                except OSError as e: messagebox.showerror("Error", f"Could not delete log file: {e}", parent=win)
        load_log()
        button_frame = Frame(win, pady=5); button_frame.pack(fill='x')
        Button(button_frame, text="Refresh Log", command=load_log).pack(side='left', padx=10); Button(button_frame, text="Clear Log", command=clear_log).pack(side='left')
        def apply_settings():
            self.stop_lock_hotkey()
            self.settings["lock_shortcut"] = lock_entry.get().strip().lower(); self.settings["unlock_shortcut"] = unlock_entry.get().strip().lower()
            try: self.settings["inactivity_minutes"] = int(inactivity_entry.get())
            except ValueError: messagebox.showerror("Error", "Inactivity time must be a number.", parent=win); return
            self.save_settings(); self.update_tray_icon(); self.start_lock_hotkey()
            messagebox.showinfo("Success", "Settings saved.", parent=win); win.destroy()
        Button(button_frame, text="Save and Close", command=apply_settings).pack(side='right', padx=10)
        win.protocol("WM_DELETE_WINDOW", lambda: (setattr(self, 'settings_window', None), win.destroy()))

    # --- 程序生命周期 ---
    def run(self):
        self.icon = pystray.Icon("ScreenLocker", self.create_icon_image(), "Screen Locker", self.create_menu())
        threading.Thread(target=self.icon.run, daemon=True).start()
        self.start_activity_listeners(); self.start_lock_hotkey(); self.start_inactivity_monitor()
        self.root.mainloop()

    def exit_app(self, *args):
        self.stop_lock_hotkey(); self.stop_unlock_listener(); self.stop_activity_listeners()
        if self.icon: self.icon.stop()
        self.root.quit(); os._exit(0)

if __name__ == "__main__":
    app = ScreenLockerApp()
    app.run()