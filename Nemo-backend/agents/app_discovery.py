"""
App Discovery — Dynamic Windows application finder
Scans Start Menu, Desktop, Program Files, and Registry to build
a fuzzy-searchable index of ALL installed apps on the system.
Results are cached for fast repeated lookups.
"""
import os
import glob
import time
import logging
import subprocess
import winreg
from pathlib import Path
from typing import Optional
from difflib import SequenceMatcher

logger = logging.getLogger("app_discovery")

# ── Web app fallbacks — open in browser if no local install found ─────────────
WEB_APP_URLS = {
    "youtube music":  "https://music.youtube.com",
    "youtube":        "https://www.youtube.com",
    "gmail":          "https://mail.google.com",
    "google drive":   "https://drive.google.com",
    "google docs":    "https://docs.google.com",
    "google sheets":  "https://sheets.google.com",
    "notion":         "https://www.notion.so",
    "figma":          "https://www.figma.com",
    "github":         "https://github.com",
    "netflix":        "https://www.netflix.com",
    "twitch":         "https://www.twitch.tv",
    "discord web":    "https://discord.com/app",
    "twitter":        "https://twitter.com",
    "reddit":         "https://www.reddit.com",
    "chatgpt":        "https://chat.openai.com",
    "claude":         "https://claude.ai",
}

# ── Hardcoded quick-launch overrides (shell commands / direct exes) ────────────
SHELL_COMMANDS = {
    "chrome":           "chrome",
    "google chrome":    "chrome",
    "firefox":          "firefox",
    "edge":             "msedge",
    "microsoft edge":   "msedge",
    "notepad":          "notepad.exe",
    "notepad++":        "notepad++.exe",
    "calculator":       "calc.exe",
    "paint":            "mspaint.exe",
    "explorer":         "explorer.exe",
    "file explorer":    "explorer.exe",
    "task manager":     "taskmgr.exe",
    "cmd":              "cmd.exe",
    "command prompt":   "cmd.exe",
    "powershell":       "powershell.exe",
    "wordpad":          "wordpad.exe",
    "snipping tool":    "SnippingTool.exe",
    "settings":         "ms-settings:",
    "control panel":    "control",
    "device manager":   "devmgmt.msc",
    "disk management":  "diskmgmt.msc",
    "vscode":           "code",
    "visual studio code": "code",
}

# ── Directories to scan ───────────────────────────────────────────────────────
# Fast dirs: only .lnk shortcuts, very quick to index
SCAN_LNK_DIRS = [
    os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
    r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
    os.path.expandvars(r"%USERPROFILE%\Desktop"),
    r"C:\Users\Public\Desktop",
]

# Deep dirs: scan for executables (one level)
SCAN_EXE_DIRS = [
    r"C:\Program Files",
    r"C:\Program Files (x86)",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs"),
    os.path.expandvars(r"%APPDATA%\Programs"),
    os.path.expandvars(r"%LOCALAPPDATA%"),   # Discord, Riot, Valorant, etc.
]

CACHE_TTL = 300  # seconds (5 min)


def _normalize(name: str) -> str:
    """Lowercase, strip extension and punctuation for comparison."""
    name = name.lower().strip()
    for ext in (".lnk", ".exe", ".bat", ".cmd", ".url"):
        if name.endswith(ext):
            name = name[: -len(ext)]
    name = name.replace("-", " ").replace("_", " ")
    return " ".join(name.split())


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _best_match(query: str, candidates: dict[str, str], threshold: float = 0.55) -> Optional[tuple[str, str]]:
    """
    Return (matched_name, path) for the best fuzzy match above threshold.
    Uses both substring containment and SequenceMatcher similarity.
    """
    q = _normalize(query)
    best_score = 0.0
    best_key   = None

    for key in candidates:
        # Exact or substring match — score 1.0
        if q == key or q in key or key in q:
            score = 1.0
        else:
            score = _similarity(q, key)

        if score > best_score:
            best_score = score
            best_key   = key

    if best_key and best_score >= threshold:
        return best_key, candidates[best_key]
    return None


class AppDiscovery:
    """
    Discovers ALL apps installed on the Windows system and provides
    a fast fuzzy lookup interface.
    """

    def __init__(self):
        self._cache: dict[str, str] = {}   # normalized_name → launch_path
        self._cache_time: float = 0.0
        self._build_index()

    def _build_index(self):
        """Scan all sources and populate the app index."""
        start = time.time()
        index: dict[str, str] = {}

        # 1. Shell commands (highest priority overrides)
        for name, cmd in SHELL_COMMANDS.items():
            index[_normalize(name)] = cmd

        # 2. Web apps
        for name, url in WEB_APP_URLS.items():
            key = _normalize(name)
            if key not in index:
                index[key] = f"__web__{url}"

        # 3. Start Menu + Desktop .lnk shortcuts (case-insensitive, recursive)
        for base_dir in SCAN_LNK_DIRS:
            if not os.path.isdir(base_dir):
                continue
            try:
                for root, dirs, files in os.walk(base_dir):
                    for fname in files:
                        if fname.lower().endswith(('.lnk', '.url')):
                            stem = Path(fname).stem
                            key  = _normalize(stem)
                            if key and key not in index:
                                full_path = os.path.join(root, fname)
                                index[key] = full_path
                                # Also index by parent folder name (e.g. 'Discord Inc' -> 'discord inc')
                                folder_name = _normalize(os.path.basename(root))
                                if folder_name and folder_name not in index and folder_name != key:
                                    index[folder_name] = full_path
            except PermissionError:
                pass

        # 4. Exe scan in common install dirs
        for base_dir in SCAN_EXE_DIRS:
            if not os.path.isdir(base_dir):
                continue
            try:
                for entry in os.scandir(base_dir):
                    if not entry.is_dir(follow_symlinks=False):
                        continue
                    try:
                        best_exe = self._find_best_exe(entry.path, entry.name)
                        if best_exe:
                            folder_key = _normalize(entry.name)
                            exe_key    = _normalize(Path(best_exe).stem)
                            for key in (folder_key, exe_key):
                                if key and key not in index:
                                    index[key] = best_exe
                    except PermissionError:
                        pass
            except PermissionError:
                pass

        # 5. Windows Registry
        index.update({k: v for k, v in self._scan_registry().items() if k not in index})

        self._cache = index
        self._cache_time = time.time()
        elapsed = time.time() - start
        logger.info(f"App Discovery: Indexed {len(index)} apps in {elapsed:.2f}s")

    def _find_best_exe(self, folder_path: str, folder_name: str) -> Optional[str]:
        """
        Given a folder, find the best executable to launch.
        Handles Squirrel/Electron apps (Discord, Riot, etc.) that use
        versioned subdirectories like 'app-1.0.9228/Discord.exe'.
        Prefers exe named like the folder, avoids Update.exe / Uninstall.exe.
        """
        SKIP_EXES = {"update.exe", "uninstall.exe", "installer.exe",
                     "setup.exe", "crashpad_handler.exe", "squirrel.exe"}
        name_norm = folder_name.lower().replace(" ", "").replace("-", "")

        # Look in versioned subdirs first (app-X.X.X, vX.X.X, etc.)
        versioned_dirs: list[tuple[str, str]] = []
        try:
            for sub in os.scandir(folder_path):
                if sub.is_dir() and (sub.name.startswith("app-") or sub.name.startswith("v")):
                    versioned_dirs.append((sub.name, sub.path))
        except PermissionError:
            pass

        # Sort newest version first
        versioned_dirs.sort(key=lambda x: x[0], reverse=True)

        candidate_dirs = [path for _, path in versioned_dirs] + [folder_path]

        for search_dir in candidate_dirs:
            candidates: list[tuple[int, str]] = []  # (priority, path)
            try:
                for f in os.scandir(search_dir):
                    if not f.name.lower().endswith(".exe") or not f.is_file():
                        continue
                    if f.name.lower() in SKIP_EXES:
                        continue
                    fn = f.name.lower().replace(".exe", "").replace(" ", "").replace("-", "")
                    if fn == name_norm:
                        return f.path  # Perfect name match
                    candidates.append((0, f.path))
            except PermissionError:
                continue
            if candidates:
                return candidates[0][1]  # First non-skipped exe

        return None


    def _scan_registry(self) -> dict[str, str]:
        """Scan Windows registry for installed application DisplayName + InstallLocation."""
        reg_paths = [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        ]
        found: dict[str, str] = {}
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for reg_path in reg_paths:
                try:
                    with winreg.OpenKey(hive, reg_path) as key:
                        for i in range(winreg.QueryInfoKey(key)[0]):
                            try:
                                sub_name = winreg.EnumKey(key, i)
                                with winreg.OpenKey(key, sub_name) as sub:
                                    try:
                                        display_name = winreg.QueryValueEx(sub, "DisplayName")[0]
                                        norm = _normalize(display_name)
                                        if norm and norm not in found:
                                            # Try to find executable
                                            try:
                                                loc = winreg.QueryValueEx(sub, "InstallLocation")[0]
                                                if loc and os.path.isdir(loc):
                                                    # Find first .exe in that directory
                                                    for f in os.listdir(loc):
                                                        if f.lower().endswith(".exe"):
                                                            found[norm] = os.path.join(loc, f)
                                                            break
                                                    else:
                                                        found[norm] = loc  # dir as fallback
                                            except (FileNotFoundError, OSError):
                                                pass
                                    except OSError:
                                        pass
                            except OSError:
                                continue
                except OSError:
                    continue
        return found

    def _refresh_if_stale(self):
        if time.time() - self._cache_time > CACHE_TTL:
            logger.info("App Discovery: Cache stale, refreshing...")
            self._build_index()

    def find(self, query: str) -> Optional[dict]:
        """
        Look up an app by name. Returns a dict describing how to launch it:
          {"type": "shell"|"lnk"|"exe"|"web"|"where", "path": ...}
        Returns None if no match found.
        """
        self._refresh_if_stale()
        q_norm = _normalize(query)

        # Exact match in index
        if q_norm in self._cache:
            return self._resolve(q_norm, self._cache[q_norm])

        # Fuzzy match
        match = _best_match(query, self._cache)
        if match:
            name, path = match
            logger.info(f"App Discovery: Fuzzy matched '{query}' → '{name}' ({path[:60]})")
            return self._resolve(name, path)

        # Last resort: try Windows `where` command
        where_result = self._where_lookup(query)
        if where_result:
            return {"type": "exe", "path": where_result, "display": query}

        return None

    def _resolve(self, name: str, path: str) -> dict:
        if path.startswith("__web__"):
            return {"type": "web", "path": path[7:], "display": name}
        if path.startswith("ms-") or path in ("control", "calc.exe", "notepad.exe",
                                               "taskmgr.exe", "explorer.exe", "mspaint.exe",
                                               "wordpad.exe", "cmd.exe", "powershell.exe",
                                               "SnippingTool.exe", "devmgmt.msc",
                                               "diskmgmt.msc"):
            return {"type": "shell", "path": path, "display": name}
        if path.endswith(".lnk"):
            return {"type": "lnk", "path": path, "display": name}
        if os.path.isdir(path):
            return {"type": "dir", "path": path, "display": name}
        return {"type": "exe", "path": path, "display": name}

    def _where_lookup(self, name: str) -> Optional[str]:
        """Use `where` command to find an executable on PATH."""
        try:
            result = subprocess.run(
                ["where", name],
                capture_output=True, text=True, timeout=3, shell=True
            )
            if result.returncode == 0:
                path = result.stdout.strip().splitlines()[0]
                if os.path.isfile(path):
                    return path
        except Exception:
            pass
        return None

    def list_apps(self, limit: int = 100) -> list[str]:
        """Return a list of all discovered app names (for UI/autocomplete)."""
        self._refresh_if_stale()
        return sorted(
            [k for k in self._cache if not k.startswith("_")],
            key=len
        )[:limit]

    def refresh(self):
        """Force a full rescan."""
        self._build_index()


# Singleton
_discovery_instance: Optional[AppDiscovery] = None


def get_app_discovery() -> AppDiscovery:
    global _discovery_instance
    if _discovery_instance is None:
        _discovery_instance = AppDiscovery()
    return _discovery_instance
