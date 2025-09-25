import pyperclip
import time
from googletrans import Translator
import tkinter as tk
from tkinter import ttk, messagebox
import psutil
import json
import win32gui
import win32process
import os
import threading

# ---------------- Настройки -----------------
SETTINGS_FILE = "settings.json"

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f)

settings = load_settings()
selected_process = settings.get("selected_process", "")
autostart_enabled = settings.get("autostart", False)
translator_enabled = settings.get("translator_enabled", True)

# ---------------- GUI -----------------
window = tk.Tk()
window.title("Перевод буфера")
window.geometry("400x300")
window.resizable(False, False)

tk.Label(window, text="Выберите процесс для перевода:").pack(pady=10)

# ---------------- Процессы -----------------
def get_windows_processes():
    windows = []

    def enum_callback(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd) and win32gui.IsWindowEnabled(hwnd):
            windows.append(hwnd)
        return True

    win32gui.EnumWindows(enum_callback, None)

    processes = set()
    for hwnd in windows:
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = psutil.Process(pid)
            folder = os.path.dirname(proc.exe()).lower()
            if folder.endswith("\\system32") or folder.endswith("\\syswow64"):
                continue
            processes.add(proc.name())
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return sorted(processes)

process_list = get_windows_processes()
combo = ttk.Combobox(window, values=process_list, state="readonly", width=35)
combo.pack(pady=10)

if selected_process in process_list:
    combo.set(selected_process)
elif process_list:
    combo.set(process_list[0])

# ---------------- Обновление списка -----------------
def refresh_process_list():
    processes = get_windows_processes()
    combo['values'] = processes
    if processes:
        combo.set(processes[0])

tk.Button(window, text="Обновить список", command=refresh_process_list).pack(pady=5)

# ---------------- Сохранение -----------------
def save_selected():
    global selected_process
    selected_process = combo.get()
    settings["selected_process"] = selected_process
    settings["autostart"] = autostart_var.get()
    save_settings(settings)
    messagebox.showinfo("Настройки", f"Процесс установлен: {selected_process}")

tk.Button(window, text="Сохранить", command=save_selected).pack(pady=10)

# ---------------- Переключатели -----------------
translator_var = tk.BooleanVar(value=translator_enabled)
def toggle_translator():
    global translator_enabled
    translator_enabled = translator_var.get()

translator_check = tk.Checkbutton(window, text="Включить перевод", variable=translator_var, command=toggle_translator)
translator_check.pack(pady=5)

autostart_var = tk.BooleanVar(value=autostart_enabled)
tk.Checkbutton(window, text="Автозапуск при старте", variable=autostart_var).pack(pady=5)

# ---------------- Закрытие окна -----------------
def on_close():
    save_selected()
    window.destroy()

window.protocol("WM_DELETE_WINDOW", on_close)

# ---------------- Перевод (в отдельном потоке) -----------------
translator = Translator()
last_buffer = ""
last_translated = ""
initial_clip = pyperclip.paste()
ignore = ["import", "def", "class", "include"]

def translation_loop():
    global last_buffer, last_translated
    while True:
        if not translator_enabled:
            time.sleep(0.5)
            continue

        clip_text = pyperclip.paste()

        # имя активного окна
        hwnd = win32gui.GetForegroundWindow()
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        try:
            active_process = psutil.Process(pid).name()
        except Exception:
            active_process = ""

        # проверка условий для перевода
        if (clip_text != last_buffer and clip_text != last_translated and clip_text != initial_clip
            and clip_text.strip() != "" and active_process.lower() == selected_process.lower()):

            # проверка на код
            if any(kw in clip_text for kw in ignore):
                last_buffer = clip_text
                continue

            try:
                lang_detected = translator.detect(clip_text).lang

                if lang_detected == "ru":
                    translated = translator.translate(clip_text, dest="en")
                elif lang_detected == "en":
                    translated = translator.translate(clip_text, dest="ru")
                else:
                    translated = translator.translate(clip_text, dest="en") # на всякий

                pyperclip.copy(translated.text)
                last_buffer = clip_text
                last_translated = translated.text
            except Exception as e:
                print("Ошибка перевода:", e)

        time.sleep(0.5)

threading.Thread(target=translation_loop, daemon=True).start()

window.mainloop()
