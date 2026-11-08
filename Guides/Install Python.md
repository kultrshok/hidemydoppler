# How to install Python (for hidemydoppler)

> **Shortcut:** on Windows, just double-click **Prepare System.cmd** in the hidemydoppler
> folder and click **Prepare system**. It installs Python and everything else for you.
> On Linux, run `./prepare_linux.sh`. The manual steps below are for when that doesn't work.

hidemydoppler needs **Python 3.9 or newer**. Get the newest 3.x release you can. Pick your
system below, then jump to **Verify** and **Run hidemydoppler**.

---

## Windows 10 / 11

**Option A: installer (easiest)**
1. Go to <https://www.python.org/downloads/> and click the big **Download Python 3.x** button.
2. Run the installer. On the first screen, **tick "Add python.exe to PATH"** at the bottom.
   This is the step most people miss.
3. Click **Install Now**. When it finishes, click **Disable path length limit** if it's offered.

**Option B: winget (one command)**
Open **Terminal** or **PowerShell** and run:
```
winget search Python.Python
winget install -e --id Python.Python.3.13
```
Swap `3.13` for the newest version the search shows.

> Already have Python but `python` opens the Microsoft Store? Go to
> **Settings > Apps > Advanced app settings > App execution aliases** and turn off the
> two "App Installer python" entries, then open a new terminal.

---

## macOS

**Option A: installer:** download the macOS installer from
<https://www.python.org/downloads/>, run it, then double-click **Install Certificates.command**
in the Python folder under Applications.

**Option B: Homebrew:**
```
brew install python
```
On macOS, the command is usually `python3` (not `python`).

---

## Linux

**Ubuntu / Debian**
```
sudo apt update
sudo apt install -y python3 python3-pip python3-venv
```

**RHEL / Rocky / Alma / CentOS Stream / Fedora**
```
sudo dnf install -y python3 python3-pip
```

**Arch**
```
sudo pacman -S python python-pip
```

On Linux, the command is `python3`.

---

## Verify

Open a **new** terminal window (so it picks up the new PATH) and run:
```
python --version        # Windows
python3 --version       # macOS / Linux
```
You should see `Python 3.9` or higher. On Windows, `py --version` also works.

---

## Run hidemydoppler

1. Unzip or copy the `hidemydoppler` folder somewhere handy.
2. Open a terminal **in that folder**.
   - Windows: open the folder in File Explorer, click the address bar, type `cmd`, press Enter.
   - macOS / Linux: `cd` to the folder.
3. Start the UI:
   ```
   python ui.py        # Windows
   python3 ui.py       # macOS / Linux
   ```
4. Your browser opens the hidemydoppler page. Click **Run prep check**. If anything is missing
   (numpy, scipy, ffmpeg), click **Install missing** and approve any admin or password
   prompt that pops up.

Prefer the command line? Run `python setup_check.py` instead. It does the same check
and asks before installing anything.

---

## Common snags

| Problem | Fix |
|---|---|
| `python` is not recognized | Python isn't on PATH. Re-run the installer, choose **Modify**, and tick **Add Python to environment variables**. Or use `py` instead. |
| `pip` says "externally managed environment" (Linux) | Make a virtual environment: `python3 -m venv .venv`, then `source .venv/bin/activate`, then rerun. |
| ffmpeg installed but still "missing" | Close and reopen the terminal (or restart `ui.py`) so the new PATH loads. |
| Browser doesn't open | Go to <http://127.0.0.1:8765> yourself. |
| Port already in use | `python ui.py --port 8800` |
