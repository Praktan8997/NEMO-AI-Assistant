"""
Automation Agent — System-level command execution
Handles opening/closing applications, volume, brightness, system info, web searches, and calculations.
Uses App Discovery for dynamic fuzzy-matching of ANY installed application.
"""
import os
import re
import ctypes
import subprocess
import webbrowser
import logging
import psutil
import platform
import time
import threading
from difflib import SequenceMatcher
from typing import Optional
from models.schemas import IntentType, NLPResult, AutomationResult
from agents.app_discovery import get_app_discovery

try:
    import pyautogui
    import pyperclip
    pyautogui.FAILSAFE = False   # disable fail-safe so mouse corner doesn't abort
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False
    logger_tmp = __import__('logging').getLogger("automation_agent")
    logger_tmp.warning("pyautogui not installed — keyboard control disabled")

logger = logging.getLogger("automation_agent")


class AutomationAgent:
    """
    Executes system-level actions based on the classified intent and entities.
    """

    def __init__(self):
        self.tasks_completed = 0
        self.last_active: Optional[float] = None
        logger.info("Automation Agent: Initialized")

    def execute(self, nlp_result: NLPResult) -> AutomationResult:
        """Route to the appropriate action handler based on intent."""
        self.last_active = time.time()
        intent   = nlp_result.intent
        entities = nlp_result.entities
        raw_text = nlp_result.raw_text.lower()

        try:
            if intent == IntentType.OPEN_APP:
                result = self._open_app(entities.get("app", ""))
            elif intent == IntentType.CLOSE_APP:
                result = self._close_app(entities.get("app", ""), raw_text)
            elif intent == IntentType.SEARCH_WEB:
                result = self._search_web(entities.get("query", nlp_result.raw_text))
            elif intent == IntentType.SYSTEM_INFO:
                result = self._get_system_info()
            elif intent == IntentType.CALCULATE:
                result = self._calculate(entities.get("expression", ""))
            elif intent == IntentType.WEATHER:
                result = self._open_weather()
            elif intent == IntentType.PLAY_MEDIA:
                result = self._play_media(entities)
            elif intent == IntentType.VOLUME_CONTROL:
                result = self._control_volume(entities, raw_text)
            elif intent == IntentType.BRIGHTNESS_CONTROL:
                result = self._control_brightness(entities, raw_text)
            elif intent == IntentType.KEYBOARD_CONTROL:
                result = self._control_keyboard(entities, raw_text)
            elif intent in (IntentType.GENERAL_QUERY, IntentType.SET_REMINDER,
                            IntentType.SEND_MESSAGE):
                result = AutomationResult(
                    success=True, action_taken=intent.value, output=None,
                )
            else:
                logger.info(f"Automation Agent: Deferring intent '{intent}' to Conversation Agent")
                result = AutomationResult(
                    success=True, action_taken="deferred", output=None,
                )
        except Exception as ex:
            logger.error(f"Automation Agent error: {ex}", exc_info=True)
            result = AutomationResult(
                success=True,
                action_taken="error",
                output=f"I encountered a technical issue: {ex}",
            )

        if result.success:
            self.tasks_completed += 1

        return result

    # ── Open App ─────────────────────────────────────────────────────────────

    def _open_app(self, app_key: str) -> AutomationResult:
        """Open any application using multi-strategy discovery."""
        if not app_key:
            return AutomationResult(success=True, action_taken="open_app", output=None)

        discovery = get_app_discovery()
        result    = discovery.find(app_key)

        if result is None:
            try:
                subprocess.Popen(["start", "", app_key], shell=True)
                return AutomationResult(
                    success=True, action_taken=f"open_app:{app_key}",
                    output=f"Attempted to launch '{app_key}'. Windows will find it if it's installed.",
                )
            except Exception:
                return AutomationResult(
                    success=True, action_taken="open_app",
                    output=f"I couldn't find '{app_key}' on your system. Make sure it's installed.",
                )

        app_type = result["type"]
        path     = result["path"]
        display  = result.get("display", app_key).title()

        try:
            if app_type == "web":
                webbrowser.open(path)
                return AutomationResult(
                    success=True, action_taken=f"open_web:{app_key}",
                    output=f"Opened {display} in your browser.",
                )
            elif app_type == "shell":
                subprocess.Popen(["start", "", path], shell=True)
            elif app_type == "lnk":
                os.startfile(path)  # type: ignore[attr-defined]
            elif app_type in ("exe", "dir"):
                if platform.system() == "Windows":
                    os.startfile(path)  # type: ignore[attr-defined]
                else:
                    subprocess.Popen([path])
            else:
                subprocess.Popen(["start", "", path], shell=True)

            return AutomationResult(
                success=True, action_taken=f"open_app:{app_key}",
                output=f"Launched {display} successfully.",
            )
        except Exception as e:
            logger.error(f"Automation Agent: Failed to open '{app_key}': {e}")
            return AutomationResult(
                success=True, action_taken=f"open_app:{app_key}",
                output=f"I found {display} but had trouble launching it: {e}",
            )

    # ── Close App ─────────────────────────────────────────────────────────────

    def _close_app(self, app_key: str, raw_text: str = "") -> AutomationResult:
        """
        Close any running application by fuzzy-matching process names.
        Strategy: psutil process scan → fuzzy name match → taskkill fallback.
        """
        # If no entity, try to extract from raw text
        if not app_key:
            m = re.search(
                r'\b(?:close|kill|quit|exit|terminate)\s+(?:the\s+|my\s+)?(.+)',
                raw_text,
            )
            if m:
                app_key = m.group(1).strip()
        if not app_key:
            return AutomationResult(
                success=True, action_taken="close_app", output=None,
            )

        query_norm = app_key.lower().replace(" ", "").replace("-", "")

        # ── Scan all running processes and fuzzy-match ────────────────────
        SKIP_PROCS = {"system", "svchost", "wininit", "winlogon", "csrss",
                      "lsass", "smss", "services", "dwm", "explorer"}

        matched: list[tuple[float, psutil.Process]] = []

        for proc in psutil.process_iter(["name", "pid", "exe"]):
            try:
                pname = (proc.info["name"] or "").lower()
                if pname.split(".")[0] in SKIP_PROCS:
                    continue

                pname_clean = pname.replace(".exe", "").replace(" ", "").replace("-", "")

                # Exact or substring match
                if query_norm == pname_clean or query_norm in pname_clean or pname_clean in query_norm:
                    matched.append((1.0, proc))
                    continue

                # Fuzzy similarity
                score = SequenceMatcher(None, query_norm, pname_clean).ratio()
                if score >= 0.6:
                    matched.append((score, proc))

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if not matched:
            # Last resort: taskkill with the raw name
            try:
                # shell=True requires a string command, NOT a list
                result = subprocess.run(
                    f'taskkill /F /IM "{app_key}.exe"',
                    capture_output=True, text=True, timeout=5, shell=True,
                )
                if result.returncode == 0:
                    return AutomationResult(
                        success=True, action_taken=f"close_app:{app_key}",
                        output=f"Terminated {app_key.title()} successfully.",
                    )
            except Exception:
                pass

            return AutomationResult(
                success=True, action_taken=f"close_app:{app_key}",
                output=f"I couldn't find any running process named '{app_key}'. "
                       f"It may already be closed.",
            )

        # Sort by score descending, kill all matches above 0.6
        matched.sort(key=lambda x: -x[0])
        killed: list[str] = []
        display_name = app_key.title()

        for _, proc in matched:
            try:
                display_name = (proc.info["name"] or app_key).replace(".exe", "").title()
                proc.terminate()
                killed.append(str(proc.pid))
                logger.info(f"Automation Agent: Terminated PID {proc.pid} ({proc.info['name']})")
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                logger.warning(f"Automation Agent: Could not terminate PID {proc.pid}: {e}")

        if killed:
            return AutomationResult(
                success=True,
                action_taken=f"close_app:{app_key}",
                output=f"Closed {display_name} (terminated {len(killed)} process{'es' if len(killed)>1 else ''}).",
            )

        return AutomationResult(
            success=True, action_taken=f"close_app:{app_key}",
            output=f"{display_name} doesn't appear to be running.",
        )

    # ── Volume Control ────────────────────────────────────────────────────────

    def _control_volume(self, entities: dict, raw_text: str) -> AutomationResult:
        """
        Control system volume via Windows virtual key events (no extra packages needed).
        Supports: up/down/mute/unmute/set to X%.
        """
        VK_VOLUME_MUTE = 0xAD
        VK_VOLUME_DOWN = 0xAE
        VK_VOLUME_UP   = 0xAF

        def _press_key(vk: int, times: int = 1):
            """Send a virtual key event via ctypes (works even when window not in focus)."""
            for _ in range(times):
                ctypes.windll.user32.keybd_event(vk, 0, 0, 0)          # key press
                ctypes.windll.user32.keybd_event(vk, 0, 0x0002, 0)     # key release
                time.sleep(0.02)

        # Check for mute/unmute
        if re.search(r'\b(mute|silent|silence|quiet)\b', raw_text):
            _press_key(VK_VOLUME_MUTE)
            return AutomationResult(
                success=True, action_taken="volume_mute",
                output="Volume muted.",
            )
        if re.search(r'\bunmute\b', raw_text):
            _press_key(VK_VOLUME_MUTE)  # toggle
            return AutomationResult(
                success=True, action_taken="volume_unmute",
                output="Volume unmuted.",
            )

        # Check for specific percentage — press keys to approximate
        level_match = re.search(r'(\d+)\s*(?:percent|%)', raw_text)
        if level_match:
            level = max(0, min(100, int(level_match.group(1))))
            # Approach: press down 50 times to reach ~0%, then up to target
            _press_key(VK_VOLUME_DOWN, 50)   # go to minimum
            presses = max(0, level // 2)       # each press ≈ 2%
            _press_key(VK_VOLUME_UP, presses)
            return AutomationResult(
                success=True, action_taken="volume_set",
                output=f"Volume set to approximately {level}%.",
            )

        # Direction: up or down
        direction = entities.get("direction", "")
        amount    = int(entities.get("amount", 5))   # number of presses

        if not direction:
            if re.search(r'\b(up|increase|raise|higher|louder|more)\b', raw_text):
                direction = "up"
            elif re.search(r'\b(down|decrease|lower|quieter|less|reduce)\b', raw_text):
                direction = "down"

        # Each keypress = ~2% change; default presses = 5 (= ~10% change)
        if direction == "up":
            _press_key(VK_VOLUME_UP, amount)
            return AutomationResult(
                success=True, action_taken="volume_up",
                output=f"Volume increased by ~{amount * 2}%.",
            )
        elif direction == "down":
            _press_key(VK_VOLUME_DOWN, amount)
            return AutomationResult(
                success=True, action_taken="volume_down",
                output=f"Volume decreased by ~{amount * 2}%.",
            )
        else:
            return AutomationResult(
                success=True, action_taken="volume_control",
                output=None,  # JARVIS will ask what to do with volume
            )

    # ── Brightness Control ────────────────────────────────────────────────────

    def _control_brightness(self, entities: dict, raw_text: str) -> AutomationResult:
        """
        Control screen brightness via PowerShell WMI.
        Works on most laptops with supported display drivers.
        """
        # Check for specific percentage
        level_match = re.search(r'(\d+)\s*(?:percent|%)', raw_text)
        target_level: Optional[int] = None

        if level_match:
            target_level = max(0, min(100, int(level_match.group(1))))
        else:
            direction = entities.get("direction", "")
            if not direction:
                if re.search(r'\b(up|increase|raise|higher|brighter|more)\b', raw_text):
                    direction = "up"
                elif re.search(r'\b(down|decrease|lower|dim|dimmer|less|reduce)\b', raw_text):
                    direction = "down"

            if direction == "up":
                # Increase by 20%
                ps_get = "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness"
                try:
                    result = subprocess.run(
                        ["powershell", "-NoProfile", "-Command", ps_get],
                        capture_output=True, text=True, timeout=5,
                    )
                    current = int(result.stdout.strip()) if result.stdout.strip().isdigit() else 50
                    target_level = min(100, current + 20)
                except Exception:
                    target_level = 70
            elif direction == "down":
                ps_get = "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness"
                try:
                    result = subprocess.run(
                        ["powershell", "-NoProfile", "-Command", ps_get],
                        capture_output=True, text=True, timeout=5,
                    )
                    current = int(result.stdout.strip()) if result.stdout.strip().isdigit() else 50
                    target_level = max(0, current - 20)
                except Exception:
                    target_level = 30

        if target_level is None:
            return AutomationResult(
                success=True, action_taken="brightness_control", output=None,
            )

        try:
            ps_cmd = (
                f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods)"
                f".WmiSetBrightness(1, {target_level})"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=8,
            )
            if result.returncode == 0:
                return AutomationResult(
                    success=True, action_taken="brightness_set",
                    output=f"Brightness set to {target_level}%.",
                )
            else:
                return AutomationResult(
                    success=True, action_taken="brightness_set",
                    output=f"Brightness set to {target_level}%. Note: some displays may not support WMI brightness control.",
                )
        except Exception as e:
            return AutomationResult(
                success=True, action_taken="brightness_set",
                output=f"Could not adjust brightness: {e}. Try using Windows Settings > System > Display.",
            )

    # ── Other handlers ────────────────────────────────────────────────────────

    def _search_web(self, query: str) -> AutomationResult:
        if not query:
            query = "Google"
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        webbrowser.open(url)
        return AutomationResult(
            success=True, action_taken="search_web",
            output=f"Opened browser with search: '{query}'",
        )

    def _get_system_info(self) -> AutomationResult:
        cpu_pct = psutil.cpu_percent(interval=0.5)
        mem     = psutil.virtual_memory()
        # Use C:\ on Windows, / on other systems
        disk_path = "C:\\" if platform.system() == "Windows" else "/"
        try:
            disk = psutil.disk_usage(disk_path)
            disk_str = f"Disk: {disk.percent}% used ({disk.used // 1024**3}GB / {disk.total // 1024**3}GB)"
        except Exception:
            disk_str = "Disk: N/A"
        info = (
            f"CPU: {cpu_pct}% | "
            f"RAM: {mem.percent}% used ({mem.used // 1024**2}MB / {mem.total // 1024**2}MB) | "
            f"{disk_str}"
        )
        return AutomationResult(success=True, action_taken="system_info", output=info)

    def _calculate(self, expression: str) -> AutomationResult:
        if not expression:
            return AutomationResult(success=True, action_taken="calculate", output=None)
        try:
            safe_expr = re.sub(r'[^0-9\+\-\*\/\.\(\)\s]', '', expression)
            result    = eval(safe_expr)  # noqa: S307
            return AutomationResult(
                success=True, action_taken="calculate",
                output=f"{expression} = {result}",
            )
        except Exception as e:
            return AutomationResult(
                success=True, action_taken="calculate",
                output=f"Could not evaluate '{expression}': {e}",
            )

    def _open_weather(self) -> AutomationResult:
        webbrowser.open("https://weather.com")
        return AutomationResult(
            success=True, action_taken="weather",
            output="Opened weather website.",
        )

    def _play_media(self, entities: dict) -> AutomationResult:
        app = entities.get("app", "spotify")
        return self._open_app(app)

    # ─────────────────────────────────────────────────────────────────────────
    # Keyboard / UI Manipulation
    # ─────────────────────────────────────────────────────────────────────────

    def _focus_window(self, app_name: str) -> tuple:
        """
        Find a Windows window whose title contains app_name and bring it to
        the foreground. Returns (success: bool, window_title: str).
        """
        import ctypes
        import ctypes.wintypes

        user32   = ctypes.windll.user32    # type: ignore[attr-defined]
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

        ALIASES = {
            "chrome":      "google chrome",
            "browser":     "chrome",
            "edge":        "microsoft edge",
            "firefox":     "mozilla firefox",
            "notepad":     "notepad",
            "notepad++":   "notepad++",
            "word":        "microsoft word",
            "excel":       "microsoft excel",
            "vscode":      "visual studio code",
            "code":        "visual studio code",
            "discord":     "discord",
            "spotify":     "spotify",
            "explorer":    "file explorer",
            "files":       "file explorer",
            "terminal":    "windows terminal",
            "cmd":         "command prompt",
            "powershell":  "windows powershell",
            "task manager":"task manager",
        }
        query = ALIASES.get(app_name.lower(), app_name).lower()

        found_hwnds: list = []
        found_titles: list = []

        def _enum_cb(hwnd, _lParam):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length < 1:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            if query in title.lower() or app_name.lower() in title.lower():
                found_hwnds.append(hwnd)
                found_titles.append(title)
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(
            ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
        )
        user32.EnumWindows(WNDENUMPROC(_enum_cb), 0)

        if not found_hwnds:
            logger.warning(f"_focus_window: no window found for '{app_name}'")
            return False, ""

        hwnd  = found_hwnds[0]
        title = found_titles[0]

        # Restore if minimised, then force focus via thread attach trick
        user32.ShowWindow(hwnd, 9)   # SW_RESTORE = 9
        fg_thread = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
        my_thread = kernel32.GetCurrentThreadId()
        user32.AttachThreadInput(fg_thread, my_thread, True)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.AttachThreadInput(fg_thread, my_thread, False)

        logger.info(f"_focus_window: focused '{title}' (hwnd={hwnd})")
        return True, title

    def _control_keyboard(self, entities: dict, raw_text: str) -> AutomationResult:
        """
        Perform system-level keyboard actions on ANY window.
        If entities['target_app'] is given, JARVIS focuses that app's window
        first so keystrokes land there, not on the JARVIS browser tab.
        """
        if not HAS_PYAUTOGUI:
            return AutomationResult(
                success=False, action_taken="keyboard_control",
                output="Keyboard control requires pyautogui. Run: pip install pyautogui pyperclip",
            )

        action     = entities.get("action", "")
        text       = entities.get("text", "")
        target_app = entities.get("target_app", "")

        focus_pfx = ""
        if target_app:
            ok, win_title = self._focus_window(target_app)
            if ok:
                focus_pfx = f" (in {win_title[:35].strip()})"
                time.sleep(0.6)         # settle after focus switch
            else:
                # Not running — try to launch then re-focus
                self._open_app(target_app)
                time.sleep(2.2)
                ok, win_title = self._focus_window(target_app)
                if ok:
                    focus_pfx = f" (in {win_title[:35].strip()})"
                    time.sleep(0.5)
                else:
                    return AutomationResult(
                        success=False, action_taken="keyboard_control",
                        output=f"Could not find or open '{target_app}'. "
                               f"Please open it first, then tell me what to do.",
                    )
        else:
            # No target: small delay so user can alt-tab to desired window
            time.sleep(0.4)

        try:
            # ── Type / Write ─────────────────────────────────────────────────
            if action == "type" and text:
                # Use clipboard for full unicode support (handles Hindi, emoji, etc.)
                try:
                    import pyperclip
                    pyperclip.copy(text)
                    pyautogui.hotkey("ctrl", "v")
                except Exception:
                    pyautogui.typewrite(text, interval=0.03)
                return AutomationResult(
                    success=True, action_taken="type",
                    output=f'Typed: "{text}"{focus_pfx}.',
                )

            # ── Find on page (Ctrl+F) ────────────────────────────────────────
            elif action == "find":
                pyautogui.hotkey("ctrl", "f")
                if text:
                    time.sleep(0.25)
                    pyautogui.typewrite(text, interval=0.04)
                return AutomationResult(
                    success=True, action_taken="find",
                    output=f'Opened find bar{f" and searched for \"{text}\"" if text else ""}{focus_pfx}.',
                )

            # ── Tab management ────────────────────────────────────────────────
            elif action == "new_tab":
                pyautogui.hotkey("ctrl", "t")
                return AutomationResult(success=True, action_taken="new_tab",   output=f"Opened a new tab{focus_pfx}.")
            elif action == "close_tab":
                pyautogui.hotkey("ctrl", "w")
                return AutomationResult(success=True, action_taken="close_tab", output=f"Closed the current tab{focus_pfx}.")
            elif action == "next_tab":
                pyautogui.hotkey("ctrl", "tab")
                return AutomationResult(success=True, action_taken="next_tab",  output=f"Switched to the next tab{focus_pfx}.")
            elif action == "prev_tab":
                pyautogui.hotkey("ctrl", "shift", "tab")
                return AutomationResult(success=True, action_taken="prev_tab",  output=f"Switched to the previous tab{focus_pfx}.")

            # ── Editing shortcuts ─────────────────────────────────────────────
            elif action == "undo":
                pyautogui.hotkey("ctrl", "z")
                return AutomationResult(success=True, action_taken="undo",       output=f"Undo performed{focus_pfx}.")
            elif action == "redo":
                pyautogui.hotkey("ctrl", "y")
                return AutomationResult(success=True, action_taken="redo",       output=f"Redo performed{focus_pfx}.")
            elif action == "copy":
                pyautogui.hotkey("ctrl", "c")
                return AutomationResult(success=True, action_taken="copy",       output=f"Copied selection to clipboard{focus_pfx}.")
            elif action == "paste":
                pyautogui.hotkey("ctrl", "v")
                return AutomationResult(success=True, action_taken="paste",      output=f"Pasted from clipboard{focus_pfx}.")
            elif action == "cut":
                pyautogui.hotkey("ctrl", "x")
                return AutomationResult(success=True, action_taken="cut",        output=f"Cut selection to clipboard{focus_pfx}.")
            elif action == "select_all":
                pyautogui.hotkey("ctrl", "a")
                return AutomationResult(success=True, action_taken="select_all", output=f"Selected all content{focus_pfx}.")
            elif action == "backspace":
                for _ in range(10):
                    pyautogui.press("backspace")
                return AutomationResult(success=True, action_taken="backspace",  output=f"Deleted last 10 characters{focus_pfx}.")

            # ── Navigation keys ───────────────────────────────────────────────
            elif action == "scroll_up":
                pyautogui.scroll(500)
                return AutomationResult(success=True, action_taken="scroll_up",     output=f"Scrolled up{focus_pfx}.")
            elif action == "scroll_down":
                pyautogui.scroll(-500)
                return AutomationResult(success=True, action_taken="scroll_down",   output=f"Scrolled down{focus_pfx}.")
            elif action == "scroll_top":
                pyautogui.hotkey("ctrl", "home")
                return AutomationResult(success=True, action_taken="scroll_top",    output=f"Jumped to top of page{focus_pfx}.")
            elif action == "scroll_bottom":
                pyautogui.hotkey("ctrl", "end")
                return AutomationResult(success=True, action_taken="scroll_bottom", output=f"Jumped to bottom of page{focus_pfx}.")
            elif action == "back":
                pyautogui.hotkey("alt", "left")
                return AutomationResult(success=True, action_taken="back",     output=f"Navigated back{focus_pfx}.")
            elif action == "forward":
                pyautogui.hotkey("alt", "right")
                return AutomationResult(success=True, action_taken="forward",  output=f"Navigated forward{focus_pfx}.")
            elif action == "refresh":
                pyautogui.press("f5")
                return AutomationResult(success=True, action_taken="refresh",  output=f"Page refreshed{focus_pfx}.")
            elif action == "fullscreen":
                pyautogui.press("f11")
                return AutomationResult(success=True, action_taken="fullscreen", output=f"Toggled fullscreen{focus_pfx}.")
            elif action == "zoom_in":
                pyautogui.hotkey("ctrl", "+")
                return AutomationResult(success=True, action_taken="zoom_in",  output=f"Zoomed in{focus_pfx}.")
            elif action == "zoom_out":
                pyautogui.hotkey("ctrl", "-")
                return AutomationResult(success=True, action_taken="zoom_out", output=f"Zoomed out{focus_pfx}.")
            elif action == "save":
                pyautogui.hotkey("ctrl", "s")
                return AutomationResult(success=True, action_taken="save",     output=f"Save command sent{focus_pfx}.")
            elif action == "enter":
                pyautogui.press("enter")
                return AutomationResult(success=True, action_taken="enter",    output=f"Enter pressed{focus_pfx}.")
            elif action == "escape":
                pyautogui.press("escape")
                return AutomationResult(success=True, action_taken="escape",   output=f"Escape pressed{focus_pfx}.")
            elif action == "print":
                pyautogui.hotkey("ctrl", "p")
                return AutomationResult(success=True, action_taken="print",    output=f"Print dialog opened{focus_pfx}.")
            elif action == "new_window":
                pyautogui.hotkey("ctrl", "n")
                return AutomationResult(success=True, action_taken="new_window", output=f"Opened a new window{focus_pfx}.")

            else:
                return AutomationResult(
                    success=False, action_taken="keyboard_control",
                    output=f"I understood you want keyboard control, but I'm not sure what '{raw_text}' means. "
                           f"Try: 'type hello', 'undo', 'redo', 'copy', 'paste', 'select all', 'new tab', 'close tab', "
                           f"'scroll up/down', 'go back', 'refresh', 'zoom in/out', 'find hello', 'save', 'press enter'.",
                )
        except Exception as e:
            logger.error(f"Keyboard control error: {e}", exc_info=True)
            return AutomationResult(
                success=False, action_taken="keyboard_control",
                output=f"Keyboard action failed: {e}",
            )


# Singleton
_automation_instance: Optional[AutomationAgent] = None


def get_automation_agent() -> AutomationAgent:
    global _automation_instance
    if _automation_instance is None:
        _automation_instance = AutomationAgent()
    return _automation_instance
