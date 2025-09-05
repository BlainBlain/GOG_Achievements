
# GOG → Goldberg Achievement Watcher

This script works with **Nemirtingas GOG emulator** and the **Goldberg Steam Emulator** to let you see achievement notifications from GOG games inside your prefered achievement watcher.  

It has been tested with **Yakuza: Like a Dragon** and other GOG releases.

---

## Overall Setup Instructions

1. **Patch the GOG game**  
   - Copy `galaxy.dll` or `galaxy64.dll` by Nemirtingas into the game’s install folder.  
   - In-game, press **Shift+F4** to check if the overlay works. 
   - If the program detects an unpatched DLL, it can patch it for you automatically (with backup).  
   - **Note:** Only emulator API version **1.152.1.0** is supported. Newer games may not work. (more specifically the achievements are listed as "null", unlock detection is nonfunctional)

2. **Install Achievement Watcher**  
   Download and configure any achievement watcher of your choice, the achievment watcher must be compatible with Goldberg Emu.

3. **Use the Script**  
   - Run the script with Python:
     ```bash
     python Achievements_Fixer.py
     ```
   - Add a GOG game by selecting its **launch shortcut (.lnk)** from the game directory.  
     - The program will automatically detect the **game name** and **GOG ID**.  
     - You must manually enter the **Steam ID** (get it from [SteamDB](https://steamdb.info/)).  

   Example setup for **Yakuza: Like a Dragon**:
   ```json
   {
     "game_name": "Yakuza: Like a Dragon", # (automatically detected)
     "gog_id": "1229228729", # (automatically detected)
     "steam_id": "1235140" # (must be set manually)
   }
   ```

---

## Features

- **Easy Game Setup**  
  Add a GOG game by picking its shortcut. No need to hunt for IDs manually except the Steam ID.  

- **Automatic DLL Patching**  
  The script checks and patches `galaxy.dll` / `galaxy64.dll` if they aren’t already patched for achievements.  

- **Process Detection**  
  When you launch a configured game, the script notices and automatically begins monitoring that game’s achievement file.  

- **Achievement Syncing**  
  Copies unlocked achievements from the GOG emulator into the correct Goldberg folder so Achievement Watcher shows notifications.  

- **Saved Config**  
  Your games and Steam IDs are stored in `gog_goldberg_config.json`. You don’t need to re-add them every time.  

---

## Screenshot

![Yakuza 7 Achievements](https://i.imgur.com/vMHSP0r.png)

---

## Requirements

- Windows (for `.lnk` shortcuts and DLLs)  
- Python 3.x  
- Required packages:
  ```bash
  pip install psutil watchdog pywin32
  ```

---

## How to Use

1. **Run the Script**  
   ```bash
   python Achievements_Fixer.py
   ```

2. **Add Your Game**  
   - Click **“Add .lnk”** and select the game’s shortcut from its install folder.  
   - Enter the Steam ID when prompted.  

3. **Start Monitoring**  
   - Press **“Start Monitoring.”**  
   - When you launch a configured GOG game, the program will automatically begin syncing its achievements.  

4. **Play & Unlock Achievements**  
   - Achievements will be copied to the correct Goldberg folder.  
   - Achievement Watcher will display notifications just like on Steam.  

---

## Compatibility

- Works only with **Nemirtingas GOG emulator** and Goldberg SteamEmu.  
- Tested with **Yakuza: Like a Dragon**.  
- Should work with most older GOG titles that use the supported API version.

---

## Troubleshooting

- **Achievements not showing** → Make sure DLLs are patched, Steam ID is correct, and Achievement Watcher is running.  
- **Removing a game** → Select it in the list and click *Remove*.  
- **Editing Steam ID** → Select the game and click *Edit Steam ID*.  
- Invalid or empty `achievements.json` files are skipped until valid data appears.

---

## Explaination

- **Valid achievement watchers** → [Hydra Launcher](https://hydralauncher.gg/) (more up to date achievement detection), [Achievement Watcher](https://xan105.github.io/Achievement-Watcher/) (outdated and achievement detection can be spotty)
- **Goldberg Requirement** → This script does not require goldberg steam emu at all, it simply translates Galaxy Emu achievements to goldbergs format then updates the goldberg achievements folder that achievement watchers look for, the achievement watcher thinks you unlocked a goldberg achievement for that game, unlocking the achievement for that game, despite being a GOG game.
 
