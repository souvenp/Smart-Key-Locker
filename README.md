[English](./README.md) | [中文](./README_zh.md)

# Smart Key Locker

A lightweight, system-tray based application for Windows to lock your keyboard and mouse input, preventing unintended actions. It can be triggered manually via a hotkey or automatically after a period of inactivity

### ✨ Features

*   **System Tray Control**: Runs silently in the system tray, showing the current status with its icon (🟢 Unlocked / 🔴 Locked).
*   **Hotkey Lock & Unlock**: Use customizable global hotkeys to instantly lock (Default: `Ctrl+Alt+L`) and securely unlock (Default: `Ctrl+Alt+P`) your inputs.
*   **Auto-Lock Timer**: Automatically locks the screen if there's no mouse or keyboard activity for a set duration.
*   **Total Input Blocking**: When locked, all keyboard presses and mouse actions are completely blocked.
*   **Easy Configuration**: A simple right-click menu provides access to a settings panel where you can change hotkeys and the inactivity timeout.

### 🚀 How to Get Started

1.  Navigate to the [**Releases**](https://github.com/souvenp/Smart-Key-Locker/releases) page of this repository.
2.  Download the latest `KeyLocker.exe` file.
3.  Run `KeyLocker.exe`. The application icon will appear in your system tray. No installation is needed.

### 📋 How to Use

1.  **Check Status**: Look at the icon in your system tray.
    *   **Green Icon**: Your keyboard and mouse are active.
    *   **Red Icon**: Your inputs are locked.
2.  **To Lock**: Press the lock hotkey (`Ctrl+Alt+L` by default) or right-click the tray icon and select "Lock Now".
3.  **To Unlock**: Press and hold all keys in the unlock hotkey combination (`Ctrl+Alt+P` by default) simultaneously.
4.  **To Change Settings**: Right-click the tray icon and select "Settings". Here you can:
    *   Customize the lock and unlock shortcuts.
    *   Set the inactivity time in minutes for auto-lock (set to 0 to disable).
    *   View recent lock/unlock events.
