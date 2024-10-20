import json
import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import tkinter as tk
from tkinter import filedialog, messagebox

CONFIG_FILE = "config.json"

class FileHandler(FileSystemEventHandler):
    def __init__(self, destination_dir):
        self.destination_dir = destination_dir
        self.processed_files = set()  # To keep track of processed files and prevent duplication
        super().__init__()

    def on_modified(self, event):
        if event.src_path.endswith("achievements.json"):
            # Ignore the event if the file was just processed
            if event.src_path in self.processed_files:
                return

            # Adding a short delay to ensure the file is fully written
            time.sleep(0.5)
            self.process_file(event.src_path)

            # After processing, mark the file as processed
            self.processed_files.add(event.src_path)
            # Clear the processed files set after a short delay
            # to allow for future processing of the same file if it changes again
            time.sleep(2)
            self.processed_files.clear()

    def process_file(self, file_path):
        # Check if the file is empty
        if os.path.getsize(file_path) == 0:
            print(f"File {file_path} is empty. Skipping processing.")
            return

        try:
            with open(file_path, 'r') as file:
                data = json.load(file)
        except json.JSONDecodeError as e:
            print(f"Failed to decode JSON from {file_path}: {e}")
            return

        modified_data = {}
        for key, value in data.items():
            modified_data[key] = {
                "earned": True,
                "earned_time": value["unlock_time"]
            }

        if not os.path.exists(self.destination_dir):
            os.makedirs(self.destination_dir)
        destination_path = os.path.join(self.destination_dir, "achievements.json")

        with open(destination_path, 'w') as file:
            json.dump(modified_data, file, indent=4)

        print(f"File {file_path} was modified and copied to {destination_path}")

def select_file(prompt, initial_dir):
    root = tk.Tk()
    root.withdraw()
    file_selected = filedialog.askopenfilename(title=prompt, initialdir=initial_dir, filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
    if not file_selected:
        messagebox.showwarning("Warning", "No file selected. Exiting.")
        exit()
    return file_selected

def select_directory(prompt, initial_dir):
    root = tk.Tk()
    root.withdraw()
    folder_selected = filedialog.askdirectory(title=prompt, initialdir=initial_dir)
    if not folder_selected:
        messagebox.showwarning("Warning", "No folder selected. Exiting.")
        exit()
    return folder_selected

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as file:
            return json.load(file)
    return {}

def save_config(config):
    with open(CONFIG_FILE, 'w') as file:
        json.dump(config, file, indent=4)

if __name__ == "__main__":
    config = load_config()

    default_watch_dir = os.path.expandvars(r"%appdata%\NemirtingasGalaxyEmu")
    default_dest_dir = os.path.expandvars(r"%appdata%\Goldberg SteamEmu Saves")

    if os.path.exists(default_watch_dir):
        path_to_watch = config.get("path_to_watch") or select_file("Select the achievements.json file to watch", default_watch_dir)
    else:
        path_to_watch = config.get("path_to_watch") or select_file("Select the achievements.json file to watch", "/")

    if os.path.exists(default_dest_dir):
        destination_dir = config.get("destination_dir") or select_directory("Select the destination directory", default_dest_dir)
    else:
        destination_dir = config.get("destination_dir") or select_directory("Select the destination directory", "/")

    config["path_to_watch"] = path_to_watch
    config["destination_dir"] = destination_dir
    save_config(config)

    event_handler = FileHandler(destination_dir)
    observer = Observer()
    observer.schedule(event_handler, path=os.path.dirname(config["path_to_watch"]), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()
