#!/usr/bin/env python3
"""
GOG -> Goldberg achievements watcher
- GUI to add .lnk launchers (auto-find .info, extract rootGameId (GOG_ID) & name)
- User supplies Steam ID
- Monitors running processes to detect which configured game is running
- Automatically watches GalaxyEmu achievements.json for that GOG_ID and writes Goldberg formatted achievements.json to Goldberg SteamEmu Saves/<STEAM_ID>
- Added: Detect Galaxy.dll / Galaxy64.dll, check if patched, optionally patch from remote
"""

import os
import sys
import json
import time
import glob
import logging
import threading
import fnmatch
import traceback
import getpass
import zipfile
from pathlib import Path
from queue import Queue, Empty
from urllib.request import urlopen, urlretrieve

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

# External dependencies
try:
    import psutil
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    # pywin32 for reading .lnk shortcuts and DLL metadata on Windows
    import pythoncom
    from win32com.client import Dispatch
    import win32api
except Exception as e:
    print("Missing dependency or running on unsupported platform. Please install required packages:")
    print("pip install psutil watchdog pywin32")
    raise

CONFIG_FILE = "gog_goldberg_config.json"
LOG_FILE = "gog_goldberg_watcher.log"
WATCH_POLL_INTERVAL = 1.0  # seconds - how often to check running processes
FIND_ACHIEVEMENTS_GLOB = os.path.join("C:/Users", getpass.getuser(), "AppData", "Roaming", "NemirtingasGalaxyEmu", "*", "{gog_id}", "achievements.json")
GOLDBERG_BASE = os.path.join("C:/Users", getpass.getuser(), "AppData", "Roaming", "Goldberg SteamEmu Saves")

# URLs for Galaxy DLL patch
GALAXY_ZIP_URL = "https://github.com/Smealm/GOG_Achievements/raw/refs/heads/main/Galaxy.zip"
GALAXY64_ZIP_URL = "https://github.com/BlainBlain/GOG_Achievements/raw/refs/heads/main/Galaxy64.zip"

# Setup logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))

# Helper functions
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"games": {}, "active": None}

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4)

def read_shortcut_lnk(lnk_path):
    """
    Return a dict with fields 'target', 'working_dir', 'arguments'
    Uses Windows COM (WScript.Shell) to read .lnk shortcuts.
    """
    pythoncom.CoInitialize()
    shell = Dispatch("WScript.Shell")
    shortcut = shell.CreateShortcut(lnk_path)
    return {
        "target": shortcut.TargetPath,
        "working_dir": shortcut.WorkingDirectory,
        "arguments": shortcut.Arguments,
        "description": getattr(shortcut, "Description", "")
    }

def find_info_file_for_lnk(lnk_path):
    """
    Look in the same directory as the lnk for *.info files, parse JSON, and return the matching info
    that contains a playTask with category == 'game' and isPrimary == True.
    Returns (rootGameId, name, playtask_path_relative, info_filepath) or (None, None, None, None)
    """
    folder = os.path.dirname(lnk_path)
    for fname in os.listdir(folder):
        if fname.lower().endswith(".info"):
            info_path = os.path.join(folder, fname)
            try:
                with open(info_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                logging.warning("Failed to parse .info %s: %s", info_path, e)
                continue

            # prefer playTasks where category == "game" and isPrimary true
            play_tasks = data.get("playTasks", [])
            for task in play_tasks:
                if task.get("category") == "game" and task.get("isPrimary"):
                    root_id = data.get("rootGameId") or data.get("gameId")
                    name = data.get("name") or data.get("title") or None
                    relative_exe = task.get("path")
                    return root_id, name, relative_exe, info_path
    return None, None, None, None

def find_achievements_json_for_gog_id(gog_id):
    """
    Use glob to find the achievements.json path for the given GOG ID under NemirtingasGalaxyEmu.
    There may be multiple EMU_IDs; pick the most recently modified achievements.json if several.
    Returns full path or None.
    """
    pattern = FIND_ACHIEVEMENTS_GLOB.format(gog_id=gog_id)
    matches = glob.glob(pattern, recursive=False)
    if not matches:
        return None
    # Choose the most recently modified
    matches.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return matches[0]

def ensure_dest_folder(steam_id):
    dest_dir = os.path.join(GOLDBERG_BASE, str(steam_id))
    os.makedirs(dest_dir, exist_ok=True)
    return dest_dir

# --- Galaxy DLL patching helpers ---
def find_galaxy_dlls(folder):
    """
    Return list of full paths to Galaxy.dll / Galaxy64.dll recursively in folder
    """
    dll_names = ["galaxy.dll", "galaxy64.dll"]
    matches = []
    for root, dirs, files in os.walk(folder):
        for file in files:
            if file.lower() in dll_names:
                matches.append(os.path.join(root, file))
    return matches

def check_galaxy_metadata(dll_path):
    """
    Return True if DLL exists and is unpatched (contains 'GOG Galaxy Library')
    If string not found, it's patched.
    """
    try:
        langs = []
        trans = win32api.GetFileVersionInfo(dll_path, r"\VarFileInfo\Translation")
        if isinstance(trans, (list, tuple)):
            for t in trans:
                if isinstance(t, (list, tuple)) and len(t) >= 2:
                    langs.append((int(t[0]), int(t[1])))
        if not langs:
            langs = [(0x0409, 0x04B0), (0x0409, 0x0000), (0x0000, 0x04B0), (0x0000, 0x0000)]
        FIELDS = ["CompanyName", "FileDescription", "ProductName"]
        for lang, cp in langs:
            base = rf"\StringFileInfo\{lang:04x}{cp:04x}\\"
            for field in FIELDS:
                try:
                    val = win32api.GetFileVersionInfo(dll_path, base + field)
                    if val and "GOG Galaxy Library" in val:
                        return True
                except Exception:
                    continue
    except Exception:
        pass
    return False

def download_and_patch_galaxy(dll_path):
    """
    Backup original DLL and replace it with one from remote
    """
    name = os.path.basename(dll_path)
    url = GALAXY_ZIP_URL if name.lower() == "galaxy.dll" else GALAXY64_ZIP_URL
    # backup
    bak_path = dll_path + ".bak"
    if not os.path.exists(bak_path):
        os.rename(dll_path, bak_path)
    else:
        # already backed up
        os.remove(dll_path)
    # download zip to temp
    tmp_zip = os.path.join(os.environ.get("TEMP", "."), name + ".zip")
    urlretrieve(url, tmp_zip)
    with zipfile.ZipFile(tmp_zip, "r") as zf:
        # DLL inside root
        extracted = zf.extract(name, os.path.dirname(dll_path))
    os.remove(tmp_zip)
    return extracted

# Watcher logic
class AchievementsHandler(FileSystemEventHandler):
    def __init__(self, gog_id, steam_id, queue):
        """
        queue: a Queue where actions or logs can be posted to the GUI thread
        """
        super().__init__()
        self.gog_id = str(gog_id)
        self.steam_id = str(steam_id)
        self.queue = queue
        self._processed_files = set()

    def _process_file(self, src_path):
        try:
            if not os.path.exists(src_path) or os.path.getsize(src_path) == 0:
                logging.info("Source achievements.json is empty or missing: %s", src_path)
                return

            with open(src_path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError as e:
                    logging.warning("Failed to decode JSON from %s: %s", src_path, e)
                    return

            modified = {}
            now_ts = int(time.time())
            for key, value in data.items():
                unlock_time = None
                if isinstance(value, dict):
                    unlock_time = value.get("unlock_time") or value.get("unlockTime") or value.get("unlock_date")
                if not isinstance(unlock_time, int):
                    try:
                        unlock_time = int(unlock_time)
                    except Exception:
                        unlock_time = now_ts
                modified[key] = {
                    "earned": True,
                    "earned_time": unlock_time
                }

            dest_dir = ensure_dest_folder(self.steam_id)
            dest_path = os.path.join(dest_dir, "achievements.json")
            with open(dest_path, "w", encoding="utf-8") as out:
                json.dump(modified, out, indent=4)

            logging.info("Processed %s -> %s", src_path, dest_path)
            self.queue.put(("log", f"Processed {os.path.basename(src_path)} -> {dest_path}"))
        except Exception as e:
            logging.error("Error processing achievements file: %s\n%s", e, traceback.format_exc())
            self.queue.put(("error", str(e)))

    def on_modified(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith("achievements.json"):
            if event.src_path in self._processed_files:
                return
            time.sleep(0.5)
            self._process_file(event.src_path)
            self._processed_files.add(event.src_path)
            def _clear(path):
                time.sleep(2)
                try:
                    self._processed_files.discard(path)
                except Exception:
                    pass
            threading.Thread(target=_clear, args=(event.src_path,), daemon=True).start()

    def on_created(self, event):
        self.on_modified(event)

class WatcherManager:
    def __init__(self, queue):
        self.observer = None
        self.handler = None
        self.queue = queue
        self.watched_path = None
        self.lock = threading.RLock()

    def stop(self):
        with self.lock:
            if self.observer:
                try:
                    self.observer.stop()
                    self.observer.join(timeout=3)
                except Exception:
                    pass
                self.observer = None
                self.handler = None
                self.watched_path = None
                logging.info("Stopped file watcher.")
                self.queue.put(("status", "Watcher stopped"))

    def start_watch(self, achievements_json_path, gog_id, steam_id):
        with self.lock:
            if not os.path.exists(achievements_json_path):
                logging.warning("Achievements file not found: %s", achievements_json_path)
                self.queue.put(("status", f"Achievements not found for GOG ID {gog_id}"))
                return False
            if os.path.abspath(self.watched_path or "") == os.path.abspath(achievements_json_path):
                return True
            self.stop()
            try:
                dir_to_watch = os.path.dirname(achievements_json_path)
                event_handler = AchievementsHandler(gog_id, steam_id, self.queue)
                observer = Observer()
                observer.schedule(event_handler, path=dir_to_watch, recursive=False)
                observer.start()
                self.observer = observer
                self.handler = event_handler
                self.watched_path = achievements_json_path
                logging.info("Started watching %s for GOG %s -> Steam %s", achievements_json_path, gog_id, steam_id)
                self.queue.put(("status", f"Watching {achievements_json_path}"))
                return True
            except Exception as e:
                logging.error("Failed to start watcher: %s", e)
                self.queue.put(("error", str(e)))
                return False

class ProcessMonitor(threading.Thread):
    def __init__(self, config, watcher_manager, queue, poll_interval=WATCH_POLL_INTERVAL):
        super().__init__(daemon=True)
        self.config = config
        self.watcher_manager = watcher_manager
        self.queue = queue
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def _proc_exe_path(self, proc):
        try:
            return proc.exe()
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            return None
        except Exception:
            return None

    def _is_proc_in_folder(self, proc_path, folder):
        if not proc_path or not folder:
            return False
        try:
            return os.path.commonpath([os.path.abspath(proc_path), os.path.abspath(folder)]) == os.path.abspath(folder)
        except Exception:
            return os.path.abspath(proc_path).lower().startswith(os.path.abspath(folder).lower())

    def _find_running_game(self):
        procs = []
        for proc in psutil.process_iter(["pid", "name", "exe"]):
            try:
                exe = proc.info.get("exe") or None
                procs.append((proc.pid, proc.info.get("name"), exe))
            except Exception:
                continue

        games = self.config.get("games", {})
        for gkey, gcfg in games.items():
            lnk_path = gcfg.get("lnk_path")
            if not lnk_path or not os.path.exists(lnk_path):
                continue
            try:
                shortcut = read_shortcut_lnk(lnk_path)
            except Exception:
                continue
            working_dir = shortcut.get("working_dir") or os.path.dirname(lnk_path) or os.path.dirname(shortcut.get("target") or "")
            compare_folder = os.path.abspath(working_dir)

            for pid, pname, pexe in procs:
                if pexe and self._is_proc_in_folder(pexe, compare_folder):
                    gog_id = gcfg.get("gog_id")
                    if not gog_id:
                        continue
                    ach = find_achievements_json_for_gog_id(gog_id)
                    if ach:
                        return gkey, gcfg, ach
                    else:
                        return gkey, gcfg, None
        return None, None, None

    def run(self):
        last_active = None
        while not self._stop_event.is_set():
            try:
                gkey, gcfg, ach_path = self._find_running_game()
                if gkey:
                    if last_active != gkey:
                        logging.info("Detected active game: %s", gkey)
                        self.queue.put(("status", f"Active: {gkey}"))
                        last_active = gkey
                    gog_id = gcfg.get("gog_id")
                    steam_id = gcfg.get("steam_id")
                    if ach_path:
                        self.watcher_manager.start_watch(ach_path, gog_id, steam_id)
                    else:
                        self.watcher_manager.stop()
                        self.queue.put(("status", f"Active: {gkey} (waiting for achievements.json)"))
                else:
                    if last_active is not None:
                        logging.info("No configured game running (previously %s).", last_active)
                        last_active = None
                        self.queue.put(("status", "No configured game running"))
                    self.watcher_manager.stop()
                time.sleep(self.poll_interval)
            except Exception as e:
                logging.error("Error in ProcessMonitor loop: %s\n%s", e, traceback.format_exc())
                time.sleep(self.poll_interval)

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("GOG -> Goldberg Achievements Watcher")
        self.config = load_config()
        self.queue = Queue()
        self.watcher_manager = WatcherManager(self.queue)
        self.monitor = None

        self._build_ui()
        self._refresh_game_list()
        self._poll_queue()

    def _build_ui(self):
        frame = ttk.Frame(self.root, padding=8)
        frame.pack(fill="both", expand=True)

        lbl = ttk.Label(frame, text="Configured games:")
        lbl.pack(anchor="w")
        self.tree = ttk.Treeview(frame, columns=("gog_id", "steam_id", "lnk"), show="headings", selectmode="browse", height=10)
        self.tree.heading("gog_id", text="GOG ID")
        self.tree.heading("steam_id", text="Steam ID")
        self.tree.heading("lnk", text="Launcher .lnk path")
        self.tree.pack(fill="both", expand=True, pady=(0,8))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x")
        add_btn = ttk.Button(btn_frame, text="Add .lnk", command=self.on_add)
        add_btn.pack(side="left", padx=2)
        edit_btn = ttk.Button(btn_frame, text="Edit Steam ID", command=self.on_edit)
        edit_btn.pack(side="left", padx=2)
        remove_btn = ttk.Button(btn_frame, text="Remove", command=self.on_remove)
        remove_btn.pack(side="left", padx=2)

        ctrl_frame = ttk.Frame(frame, padding=(0,8,0,0))
        ctrl_frame.pack(fill="x")
        self.start_btn = ttk.Button(ctrl_frame, text="Start Monitoring", command=self.start_monitoring)
        self.start_btn.pack(side="left")
        self.stop_btn = ttk.Button(ctrl_frame, text="Stop Monitoring", command=self.stop_monitoring)
        self.stop_btn.pack(side="left", padx=4)
        self.status_label = ttk.Label(frame, text="Idle")
        self.status_label.pack(anchor="w", pady=(4,0))

    def _refresh_game_list(self):
        self.tree.delete(*self.tree.get_children())
        for key, g in self.config.get("games", {}).items():
            self.tree.insert("", "end", iid=key, values=(g.get("gog_id"), g.get("steam_id"), g.get("lnk_path")))

    def _poll_queue(self):
        try:
            while True:
                item = self.queue.get_nowait()
                if item[0] == "status":
                    self.status_label.config(text=item[1])
                elif item[0] == "log":
                    logging.info(item[1])
                elif item[0] == "error":
                    logging.error(item[1])
        except Empty:
            pass
        self.root.after(200, self._poll_queue)

    def start_monitoring(self):
        if self.monitor and self.monitor.is_alive():
            return
        self.monitor = ProcessMonitor(self.config, self.watcher_manager, self.queue)
        self.monitor.start()
        self.status_label.config(text="Monitoring started")

    def stop_monitoring(self):
        if self.monitor:
            self.monitor.stop()
            self.monitor.join(timeout=3)
        self.watcher_manager.stop()
        self.status_label.config(text="Monitoring stopped")

    # --- Add / Edit / Remove ---
    def on_add(self):
        lnk_path = filedialog.askopenfilename(
            title="Select launcher .lnk",
            filetypes=[("LNK files", "*.lnk")],
            initialdir=os.path.expanduser("~")
        )
        if not lnk_path:
            return

        gog_id, name, rel_exe, info_file = find_info_file_for_lnk(lnk_path)
        if not gog_id:
            messagebox.showerror(
                "Error",
                "No suitable .info file with a primary game task found in the same folder as the .lnk."
            )
            return

        folder = os.path.dirname(lnk_path)
        dlls = find_galaxy_dlls(folder)
        unpatched = [dll for dll in dlls if check_galaxy_metadata(dll)]
        if unpatched:
            msg = "Game DLLs are not patched. Achievements won't work.\nApply patch now?"
            if messagebox.askyesno("Patch Required", msg):
                for dll in unpatched:
                    try:
                        download_and_patch_galaxy(dll)
                        logging.info(f"Patched {os.path.basename(dll)}")
                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to patch {dll}: {e}")
                        logging.error(f"Failed to patch {dll}: {e}")
                messagebox.showinfo("Patched", "DLLs patched successfully!")
            else:
                logging.info("User chose not to patch DLLs. Achievements will not work for this game.")

        steam_id = simpledialog.askstring(
            "Steam ID",
            f"Detected game: {name}\nGOG rootGameId: {gog_id}\nEnter Steam ID to map to:"
        )
        if not steam_id:
            messagebox.showwarning("Cancelled", "No Steam ID provided. Add aborted.")
            return

        key = name or gog_id
        games = self.config.setdefault("games", {})
        games[key] = {
            "name": name,
            "gog_id": str(gog_id),
            "steam_id": str(steam_id),
            "lnk_path": os.path.abspath(lnk_path),
            "info_file": os.path.abspath(info_file),
            "rel_exe": rel_exe,
            "galaxy_dlls": dlls
        }
        save_config(self.config)
        self._refresh_game_list()
        logging.info(f"Added game {key}: GOG {gog_id} -> Steam {steam_id}")

    def on_edit(self):
        sel = self.tree.selection()
        if not sel:
            return
        key = sel[0]
        g = self.config["games"].get(key)
        if not g:
            return
        steam_id = simpledialog.askstring("Edit Steam ID", f"Current: {g.get('steam_id')}", initialvalue=g.get('steam_id'))
        if steam_id:
            g["steam_id"] = steam_id
            save_config(self.config)
            self._refresh_game_list()

    def on_remove(self):
        sel = self.tree.selection()
        if not sel:
            return
        key = sel[0]
        if messagebox.askyesno("Confirm Remove", f"Remove game {key}?"):
            self.config["games"].pop(key, None)
            save_config(self.config)
            self._refresh_game_list()

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.stop_monitoring(), root.destroy()))
    root.mainloop()

