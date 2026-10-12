# KanaShift

**A customizable multilingual input switcher for Windows.**

KanaShift lets you switch between keyboard layouts and supported IME modes using a single shortcut, **`CapsLock + Q`**. It displays a centered, keyboard-friendly selection overlay instead of making you cycle through input languages one by one.

Configure **1 to 6 shortcuts slots** for the input methods you actually use. KanaShift discovers available Windows input layouts, so you are not limited to a fixed list of languages.

> **Status:** v0.5 — development release. Windows 10/11 is the intended platform. Some IME mode changes depend on the installed IME and the target application; cross-device Windows testing is still required.

## Features

- **One shortcut, one overlay:** Press `CapsLock + Q` to open the input selector in the center of the screen.
- **1–6 customizable slots:** Add only the languages and modes you need, rename the slots, and rearrange them.
- **First-run setup:** Choose your input methods before enabling the global shortcut.
- **Detect available input layouts:** Read currently loaded Windows keyboard layouts and IMEs; refresh the list from Settings.
- **Keyboard or mouse navigation:** Choose a slot with `1–6`, arrow keys and `Enter`, or a mouse click. Press `Esc` to cancel.
- **Japanese input modes:** Choose full-width Hiragana, full-width Katakana, half-width Katakana, or a prompt asking which Katakana width to use.
- **Korean input modes:** Select Hangul or Latin-letter input through the Korean IME.
- **More languages:** Use any compatible, available Windows keyboard layout, including English, Chinese, Russian, French, Spanish, German, and others.
- **System tray controls:** Open the overlay, edit slots, or quit using the KanaShift tray icon.
- **Saved preferences:** Slot settings are retained between launches.

## Supported languages and input methods

KanaShift **does not ship language packs or install new input methods**. It works with the keyboard layouts and IMEs exposed by Windows on your device.

| Language / input method | Available configuration |
| --- | --- |
| Korean | Hangul / Latin-letter mode (Korean IME) |
| Japanese | Full-width Hiragana, full-width Katakana, half-width Katakana, or ask for Katakana width |
| Chinese (Simplified) | Select an available Simplified Chinese keyboard / IME |
| Chinese (Traditional) | Select an available Traditional Chinese keyboard / IME |
| English | Select an available keyboard layout (e.g., US or UK) |
| Russian | Select an available Russian keyboard layout |
| Spanish | Select an available Spanish keyboard layout |
| French | Select an available French keyboard layout |
| Other languages | Select other compatible Windows input layouts detected on your device |

**Important limitations:**

- Selecting a Simplified or Traditional Chinese IME does **not** force the character set inside an individual IME (such as Microsoft Pinyin). That depends on the IME's own settings.
- Japanese conversion-mode control can behave differently across versions of Microsoft IME and applications.
- KanaShift uses the Windows `GetKeyboardLayoutList` API, which enumerates **currently loaded input layouts**, not every language pack installed on the machine. If a newly added layout is missing, activate it in Windows and refresh the list; signing out and back in may also help.

## Requirements

- Windows 10 or Windows 11
- Python 3.10 or newer (for running from source)
- [PySide6](https://pypi.org/project/PySide6/) (installed through `requirements.txt`)
- The keyboard layouts / IMEs you want to use must already be configured in Windows

## Installation

### Run from source

1. Download or clone the repository.
2. Make sure Python is installed and available through the Windows `py` launcher.
3. Run **`install.bat`** to install dependencies.
4. Run **`run.bat`** to launch KanaShift.

Alternatively, use Windows Terminal or Command Prompt:

```powershell
py -m pip install -r requirements.txt
py app.py
```

Run **`debug.bat`** to launch with a visible console if startup fails or you need to read error messages.

### Build a standalone executable

Run **`build_windows.bat`** on Windows. It uses PyInstaller and writes the executable to:

```text
dist\KanaShift.exe
```

You can also build manually:

```powershell
py -m pip install -r requirements.txt pyinstaller
py -m PyInstaller --noconfirm --clean --onefile --windowed --name KanaShift app.py
```

The executable bundles the Python dependencies, but **does not bundle Windows language packs or IMEs**. A compiled EXE is not included in the source repository unless a release explicitly provides one.

## Getting started

1. Launch KanaShift. A short **`Loading....`** indicator will appear.
2. On first launch, select an available keyboard layout and input mode for **Slot 1**.
3. Click **Add input method** if you want more slots (up to six). You can also use just one slot.
4. Save your settings. The global shortcut is enabled after the first-run setup finishes.
5. Press **`CapsLock + Q`** in another application to open the input selector.
6. Choose a slot and continue typing in your original application.

Already configured? KanaShift skips the first-run wizard. To make changes later, right-click the **K** icon in the Windows system tray and open **Settings**.

## Keyboard controls

| Action | Shortcut |
| --- | --- |
| Open / close the selector | `CapsLock + Q` |
| Select a configured slot | `1`–`6` |
| Move selection | Arrow keys |
| Confirm | `Enter` |
| Cancel / close | `Esc` |

Pressing `CapsLock` alone retains its usual behavior. When the `CapsLock + Q` shortcut is recognized, KanaShift is designed to suppress the shortcut keystrokes so they do not appear in the active text field.

## Settings and privacy

KanaShift stores user preferences using Qt's `QSettings` in the current Windows user profile:

```text
HKEY_CURRENT_USER\Software\LuteTools\KanaShift
```

The application does **not** require your Windows password or an online account. Its global keyboard hook is used to detect the activation shortcut; it is **not** intended as a keystroke recorder. Input method changes are performed locally using Windows APIs.

## Troubleshooting

**My language or keyboard is not listed.**  
Add it in **Windows Settings → Time & language → Language & region**, activate the keyboard layout, then use **Refresh input methods** in KanaShift Settings. Windows may not report a newly installed but not yet loaded layout.

**An input mode does not change as expected.**  
IME behavior varies by Windows version, keyboard layout, and application. Japanese and Chinese internal conversion modes in particular may not respond identically everywhere. If the target application is running as administrator, a non-elevated KanaShift instance may be unable to control it.

**KanaShift does not open or the shortcut is unavailable.**  
Run `debug.bat` to check errors. Also check whether another utility has reserved `CapsLock + Q`.

## Project structure

```text
KanaShift/
├── app.py                  # PySide6 UI, system tray, and application state
├── hotkeys_windows.py      # Global CapsLock + Q hotkey
├── ime_windows.py          # Windows input layout / IME operations
├── layout_profiles.py      # Input discovery and customizable slots
├── requirements.txt        # Python dependencies
├── install.bat             # Install dependencies
├── run.bat                 # Start the app
├── debug.bat               # Console-based troubleshooting
├── build_windows.bat       # Build a Windows EXE
└── tests/                  # Unit tests
```

Run the tests with:

```powershell
py -m unittest discover -s tests -v
```

## Credits

**Developed by Lutté Laurent**

## License

Licensed under the **MIT License**. See [LICENSE](LICENSE) for the complete license text.
