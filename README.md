# Achievement File Watcher

This script collaborates with Nemirtingas GOG emulator to monitor and modify the `achievements.json` file, enabling achievement notifications in GOG games. It has been tested with **Yakuza: Like a Dragon**.

## Overall Setup Instructions

1. **Place the GOG Emulator**: Copy the `galaxy64.dll` by Nemirtingas to the respective GOG game folder (File is inside the repository). In-game, press **Shift+F4** to activate the overlay and verify it's working.
   - **Note**: API versions above **1.152.1.0** are not supported by the emulator. Newer games will not be handled, and the script won't function without this emulator version.

2. **Download and Set Up Achievement Watcher**: Ensure Achievements Watcher is installed and configured correctly (https://github.com/xan105/Achievement-Watcher).

3. **Use the Script**:
   - Locate the `achievements.json` file of your GOG game. The script will default to the expected directory, so you’ll start in the right location.
   - For the destination, create a folder named with the game’s Steam ID inside the Goldberg folder. The script defaults to this location, making it easier to set up.
   - Example configuration for **Yakuza: Like a Dragon**:
     ```json
     {
       "path_to_watch": "C:/Users/<USERNAME>/AppData/Roaming/NemirtingasGalaxyEmu/<EMU_ID>/1229228729/achievements.json",
       "destination_dir": "C:/Users/<USERNAME>/AppData/Roaming/Goldberg SteamEmu Saves/1235140"
     }
     ```

## Features

- **File Monitoring**: Uses `watchdog` to monitor the specified `achievements.json` file for modifications.
- **JSON Processing**: Reads and modifies the JSON file by setting all achievements as earned with the original unlock time.
- **User Interface**: A simple GUI using `tkinter` allows the user to select the file and destination directory if not already configured.
- **Configuration**: Configuration is saved in a `config.json` file, allowing the script to remember previous selections.

## Screenshot
![Yakuza 7 Achievements](https://i.imgur.com/vMHSP0r.png)



## Requirements

- Python 3.x
- Required packages: `watchdog`, `tkinter`

To install `watchdog`, use:

```bash
pip install watchdog
```

## How to Use

1. **Run the Script**: Execute the script using Python:
   ```bash
   python Achievements_Fixer.py
   ```
   
2. **Select Files and Directories**: If no paths are saved in the configuration, the script will prompt you to select:
   - The `achievements.json` file to monitor.
   - The destination directory where the modified file will be saved.

3. **File Monitoring**: The script will then monitor the selected file for any modifications. If changes are detected:
   - The script reads the file, modifies the data to mark achievements as earned, and saves it to the destination directory.

## Compatibility

- This script works in collaboration with **Nemirtingas GOG emulator** to enable achievement notifications for GOG games.
- **Tested in Yakuza: Like a Dragon** for functionality and proper achievement notifications.

## Notes

- Make sure the `achievements.json` file is not empty, as the script will skip processing if it is.
- If the file contains invalid JSON, the script will log an error and continue monitoring for further changes.

## Troubleshooting

- **No File Selected Warning**: If you do not select a file or directory, the script will display a warning and exit.
- **JSON Decode Error**: If the `achievements.json` file is not properly formatted, the script will log a message and skip processing until the next modification.

## Dependencies

- `watchdog`: For monitoring file changes.
- `tkinter`: For the graphical file and directory selection dialog.
- `json`: For reading and writing JSON data.

---

This version includes the detailed setup process and configuration example to guide users through the initial setup.
