import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import requests
import os
import subprocess
import py7zr
import ctypes
import sys
import threading
import time
from tqdm import tqdm
import logging
import shutil
import tempfile
import json
import webbrowser
import winreg
from typing import Dict, Optional, List


class APILimitRateError(Exception):
    pass


# Initialize logging configuration
logging.basicConfig(
    filename="ollama_installer.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(module)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Constants for repository and base download URLs
ROCM_VERSION_TAG = "v0.6.4.2"
BASE_URL = f"https://github.com/likelovewant/ROCmLibs-for-gfx1103-AMD780M-APU/releases/download/{ROCM_VERSION_TAG}/"

# GPU architecture mapping strictly based on actual release filenames
GPU_ROCM_MAPPING = {
    "Official Support (Navi 31/32, Vega 20, 890M, RX9000)": "rocm.for.official.Support.7z",
    "gfx1010/1012 xnack- ('Navi 10', RX 5700/5600/5500 XT)": "rocm.gfx1010-xnack-gfx1012-xnack-.for.hip6.4.2.7z",
    "gfx1012 without xnack- / gfx1100 Mixed": "rocm.gfx1100.gfx1012.for.hip.6.4.2.7z",
    "gfx1031 ('Navi 22', RX 6700/6750 XT)": "rocm.gfx1031.for.hip.6.4.2.7z",
    "gfx1032 ('Navi 23', RX 6600/6650 XT, RX 7600)": "rocm.gfx1032.for.hip.6.4.2.7z",
    "gfx1034/1035/1036 ('Navi 24', RX 6500 XT, 6400, 680M APU)": "rocm.gfx1034.gfx1035.gfx1036.for.hip.6.4.2.7z",
    "gfx1103 ('Phoenix', 780M/880M APU)": "rocm.gfx1103.for.hip.6.4.2.7z",
    "gfx1152 (Strix / Ryzen AI 300 APU)": "rocm.gfx1152.for.hip.6.4.2.7z",
    "gfx1153 (Strix / Ryzen AI 300 APU)": "rocm.gfx1153.for.hip.6.4.2.7z"
}


def get_rocm_url(gpu_model: str) -> Optional[str]:
    """Retrieve the exact ROCm download URL for the selected GPU model."""
    if gpu_model in GPU_ROCM_MAPPING:
        return BASE_URL + GPU_ROCM_MAPPING[gpu_model]
    return None


def get_system_amd_gpus() -> List[str]:
    """Fetch installed AMD GPU names using Windows PowerShell."""
    try:
        cmd = 'powershell "Get-CimInstance -ClassName Win32_VideoController | Select-Object -ExpandProperty Name"'
        output = subprocess.check_output(
            cmd, shell=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW).strip()
        gpus = [line.strip() for line in output.split('\n') if line.strip()]
        return [gpu for gpu in gpus if "AMD" in gpu.upper() or "RADEON" in gpu.upper()]
    except Exception as e:
        logging.error(f"Failed to detect GPU: {e}")
        return []


def auto_match_gpu_to_key(gpu_name: str) -> str:
    """Map detected GPU model name to the corresponding dictionary key."""
    gpu_name_upper = gpu_name.upper()

    # Match Official Support packages (High-end and newer architectures)
    if any(x in gpu_name_upper for x in ["7900", "7800", "7700", "6900", "6950", "6800", "890M", "9070", "9060"]):
        return "Official Support (Navi 31/32, Vega 20, 890M, RX9000)"

    # Match specific modified architectures
    if "780M" in gpu_name_upper or "880M" in gpu_name_upper:
        return "gfx1103 ('Phoenix', 780M/880M APU)"
    elif any(x in gpu_name_upper for x in ["6700", "6750"]):
        return "gfx1031 ('Navi 22', RX 6700/6750 XT)"
    elif any(x in gpu_name_upper for x in ["6600", "6650", "7600"]):
        return "gfx1032 ('Navi 23', RX 6600/6650 XT, RX 7600)"
    elif any(x in gpu_name_upper for x in ["6500", "6400", "680M"]):
        return "gfx1034/1035/1036 ('Navi 24', RX 6500 XT, 6400, 680M APU)"
    elif any(x in gpu_name_upper for x in ["5700", "5600", "5500"]):
        return "gfx1010/1012 xnack- ('Navi 10', RX 5700/5600/5500 XT)"

    # Handle ambiguous integrated graphics naming
    if "GRAPHICS" in gpu_name_upper and not any(char.isdigit() for char in gpu_name):
        return "AMBIGUOUS_APU"

    return ""


def is_admin() -> bool:
    """Check if the script is running with administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def restart_as_admin():
    """Relaunch the script requesting UAC elevation."""
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    sys.exit()


class ProxySelector:
    """Handles proxy configuration and selection."""
    DEFAULT_PROXIES = {
        "Default (No Proxy)": "",
        "GHProxy": "https://ghfast.top/",
        "GitHub Mirror": "https://github.moeyy.xyz/",
        "CF Worker": "https://gh.api.99988866.xyz/"
    }

    def __init__(self, master):
        self.master = master
        self.proxies: Dict[str, str] = self.load_proxies()
        self.selected_proxy = tk.StringVar(value="Default (No Proxy)")
        self.custom_proxy = tk.StringVar()
        self.create_widgets()

    def create_widgets(self):
        self.proxy_frame = ttk.LabelFrame(
            self.master.master, text="🌐 Proxy & Network Settings", padding=(10, 5))
        self.proxy_frame.grid(row=2, column=0, columnspan=2,
                              pady=5, padx=10, sticky="ew")
        self.proxy_frame.columnconfigure(1, weight=1)

        ttk.Label(self.proxy_frame, text="Select Proxy:").grid(
            row=0, column=0, pady=5, padx=5, sticky="w")
        self.proxy_combo = ttk.Combobox(
            self.proxy_frame, textvariable=self.selected_proxy, state="readonly")
        self.update_proxy_list()
        self.proxy_combo.grid(row=0, column=1, pady=5, padx=5, sticky="ew")

        ttk.Label(self.proxy_frame, text="Custom Proxy:").grid(
            row=1, column=0, pady=5, padx=5, sticky="w")
        self.custom_entry = ttk.Entry(
            self.proxy_frame, textvariable=self.custom_proxy)
        self.custom_entry.grid(row=1, column=1, pady=5, padx=5, sticky="ew")

        ttk.Button(self.proxy_frame, text="Add", command=self.add_custom_proxy,
                   width=8).grid(row=1, column=2, pady=5, padx=5, sticky="e")

    def update_proxy_list(self):
        proxy_list = list(self.proxies.keys())
        self.proxy_combo["values"] = proxy_list
        if self.selected_proxy.get() not in proxy_list:
            self.selected_proxy.set(proxy_list[0])

    def get_selected_proxy_url(self) -> str:
        name = self.selected_proxy.get()
        return self.proxies.get(name, "")

    def add_custom_proxy(self):
        url = self.custom_proxy.get().strip()
        if not url:
            return
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        if not url.endswith("/"):
            url += "/"
        name = f"Custom ({url})"
        self.proxies[name] = url
        self.save_proxies()
        self.update_proxy_list()
        self.proxy_combo.set(name)
        self.custom_proxy.set("")

    def load_proxies(self) -> Dict[str, str]:
        try:
            if os.path.exists("proxy_config.json"):
                with open("proxy_config.json", "r") as f:
                    saved = json.load(f)
                    proxies = self.DEFAULT_PROXIES.copy()
                    proxies.update(saved)
                    return proxies
        except Exception:
            pass
        return self.DEFAULT_PROXIES.copy()

    def save_proxies(self):
        try:
            save_proxies = {k: v for k,
                            v in self.proxies.items() if "Default" not in k}
            with open("proxy_config.json", "w") as f:
                json.dump(save_proxies, f, indent=2)
        except Exception as e:
            logging.error(f"Error saving proxy config: {e}")


class OllamaInstallerGUI:
    """Main Application GUI."""

    def __init__(self, master):
        self.master = master
        master.title("Ollama For AMD Installer (v0.16.1+ Ready)")
        master.geometry("750x850")

        # Apply modern clam theme if available
        style = ttk.Style()
        if 'clam' in style.theme_names():
            style.theme_use('clam')

        master.columnconfigure(0, weight=1)
        master.rowconfigure(4, weight=1)

        self.repo = "likelovewant/ollama-for-amd"
        self.base_url = f"https://github.com/{self.repo}/releases/download"
        self.github_url = "https://github.com/ByronLeeeee/Ollama-For-AMD-Installer"
        self.gpu_var = tk.StringVar()
        self.github_access_token_var = tk.StringVar()

        self.create_widgets()
        self.proxy_selector = ProxySelector(self)
        self.load_settings()

    def create_widgets(self):
        # --- 1. GPU Selection Frame ---
        gpu_frame = ttk.LabelFrame(
            self.master, text="💻 GPU Configuration", padding=(10, 5))
        gpu_frame.grid(row=0, column=0, columnspan=2,
                       pady=10, padx=10, sticky="ew")
        gpu_frame.columnconfigure(1, weight=1)

        ttk.Label(gpu_frame, text="Select your GPU Model:").grid(
            row=0, column=0, pady=5, padx=5, sticky="w")
        self.gpu_combo = ttk.Combobox(gpu_frame, textvariable=self.gpu_var, values=list(
            GPU_ROCM_MAPPING.keys()), state="readonly", width=45)
        self.gpu_combo.grid(row=0, column=1, pady=5, padx=5, sticky="ew")

        self.detect_btn = ttk.Button(
            gpu_frame, text="🔍 Auto-Detect", command=self.detect_gpu)
        self.detect_btn.grid(row=0, column=2, pady=5, padx=5, sticky="e")

        # --- 2. Main Actions Frame ---
        actions_frame = ttk.LabelFrame(
            self.master, text="🚀 Installation Actions", padding=(10, 5))
        actions_frame.grid(row=1, column=0, columnspan=2,
                           pady=5, padx=10, sticky="ew")
        actions_frame.columnconfigure(0, weight=1)

        self.check_button = ttk.Button(
            actions_frame, text="1. Full Install (App + AMD Base + GPU Libs)", command=self.full_install_thread)
        self.check_button.grid(
            row=0, column=0, columnspan=2, pady=5, padx=5, sticky="ew")

        self.replace_button = ttk.Button(
            actions_frame, text="2. Replace GPU ROCm Libraries Only", command=self.replace_only_thread)
        self.replace_button.grid(
            row=1, column=0, columnspan=2, pady=5, padx=5, sticky="ew")

        # --- 3. Troubleshooting Frame ---
        troubleshoot_frame = ttk.LabelFrame(
            self.master, text="🛠️ Troubleshooting & Fixes", padding=(10, 5))
        troubleshoot_frame.grid(
            row=3, column=0, columnspan=2, pady=5, padx=10, sticky="ew")
        troubleshoot_frame.columnconfigure(1, weight=1)

        self.fix_button = ttk.Button(
            troubleshoot_frame, text="Fix 0xc0000005 Error (Copy Base Libs)", command=self.fix_05Error_thread)
        self.fix_button.grid(row=0, column=0, columnspan=2,
                             pady=5, padx=5, sticky="ew")

        ttk.Label(troubleshoot_frame, text="GitHub PAT (To avoid API Limits):").grid(
            row=1, column=0, pady=5, sticky="w")
        self.github_entry = ttk.Entry(
            troubleshoot_frame, textvariable=self.github_access_token_var)
        self.github_entry.grid(row=1, column=1, pady=5, padx=5, sticky="ew")

        # --- 4. Live Console & Progress Frame ---
        console_frame = ttk.LabelFrame(
            self.master, text="🖥️ Console Output", padding=(10, 5))
        console_frame.grid(row=4, column=0, columnspan=2,
                           pady=5, padx=10, sticky="nsew")
        console_frame.columnconfigure(0, weight=1)
        console_frame.rowconfigure(0, weight=1)

        self.log_area = scrolledtext.ScrolledText(
            console_frame, height=10, font=("Consolas", 9), state="disabled", bg="#f4f4f4")
        self.log_area.grid(row=0, column=0, sticky="nsew", pady=5)

        self.progress = ttk.Progressbar(
            console_frame, length=100, mode="determinate")
        self.progress.grid(row=1, column=0, pady=5, sticky="ew")
        self.speed_label = ttk.Label(console_frame, text="Ready.")
        self.speed_label.grid(row=2, column=0, sticky="w")

        # --- 5. Footer Frame ---
        footer_frame = ttk.Frame(self.master)
        footer_frame.grid(row=5, column=0, columnspan=2,
                          padx=10, pady=5, sticky="e")
        tk.Label(footer_frame, text="GitHub:",
                 font=("Arial", 8)).pack(side="left")
        link = tk.Label(footer_frame, text="ByronLeeeee/Ollama-For-AMD-Installer",
                        font=("Arial", 8, "underline"), fg="blue", cursor="hand2")
        link.pack(side="left")
        link.bind("<Button-1>", lambda e: webbrowser.open_new_tab(self.github_url))

        self.log_msg("System Ready. Waiting for user action...")

    def log_msg(self, message: str, level="INFO"):
        """Print timestamped messages to the GUI console and log file."""
        logging.info(message)
        self.log_area.config(state="normal")
        self.log_area.insert(
            tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.log_area.see(tk.END)
        self.log_area.config(state="disabled")
        self.master.update_idletasks()

    def detect_gpu(self):
        """Handle auto-detect GPU button action."""
        self.log_msg("Detecting system GPUs...")
        gpus = get_system_amd_gpus()

        if not gpus:
            self.log_msg(
                "No AMD GPUs detected or detection failed.", "WARNING")
            messagebox.showinfo(
                "GPU Detection", "Could not automatically detect an AMD GPU.\nPlease select it manually from the list.")
            return

        detected_str = ", ".join(gpus)
        self.log_msg(f"Detected GPU(s): {detected_str}")

        matched_key = auto_match_gpu_to_key(gpus[0])

        if matched_key == "AMBIGUOUS_APU":
            messagebox.showwarning(
                "Ambiguous APU Detected",
                f"Detected: {gpus[0]}\n\nYour CPU has integrated graphics (APU), but Windows only reports it generically.\n\nIf it is a Ryzen 7000/8000 series, select gfx1103.\nIf it is a Ryzen 6000 series, select gfx1034."
            )
        elif matched_key:
            self.gpu_var.set(matched_key)
            self.log_msg(f"Auto-selected architecture: {matched_key}")
            messagebox.showinfo(
                "GPU Detected", f"Detected: {gpus[0]}\nAuto-selected: {matched_key}")
        else:
            messagebox.showinfo(
                "GPU Detected",
                f"Detected: {gpus[0]}\n\nCould not confidently auto-match this to a specific ROCm architecture. Please select the closest match manually."
            )

    def kill_ollama(self):
        """Terminate Ollama processes to prevent file locking issues during extraction."""
        self.log_msg("Stopping Ollama services to prevent file lock errors...")
        subprocess.run(["taskkill", "/F", "/IM", "ollama.exe"],
                       capture_output=True)
        subprocess.run(
            ["taskkill", "/F", "/IM", "ollama app.exe"], capture_output=True)
        time.sleep(1)

    def find_ollama_path(self) -> Optional[str]:
        """Locate the Ollama installation directory via Registry or default path."""
        try:
            hkey = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Ollama")
            install_path = winreg.QueryValueEx(hkey, "InstallLocation")[0]
            winreg.CloseKey(hkey)
            if os.path.exists(install_path):
                return install_path
        except Exception:
            pass

        try:
            hkey = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Ollama")
            install_path = winreg.QueryValueEx(hkey, "InstallLocation")[0]
            winreg.CloseKey(hkey)
            if os.path.exists(install_path):
                return install_path
        except Exception:
            pass

        default_path = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama")
        if os.path.exists(default_path):
            return default_path

        if messagebox.askokcancel("Ollama Not Found", "Could not automatically locate Ollama. Select folder manually?"):
            user_path = filedialog.askdirectory(
                title="Select Ollama installation folder")
            if user_path and os.path.exists(os.path.join(user_path, "ollama.exe")):
                return user_path

        return None

    def _get_auth_headers(self):
        """Attach GitHub PAT for authentication if provided and not using a proxy."""
        token = self.github_access_token_var.get().strip()
        proxy = self.proxy_selector.get_selected_proxy_url()
        if token and not proxy:
            return {"Authorization": f"Bearer {token}"}
        return None

    def check_rate_limit(self, response):
        """Check HTTP headers for GitHub API rate limit errors."""
        if response.status_code in [403, 429]:
            remaining = response.headers.get("x-ratelimit-remaining")
            if remaining and int(remaining) == 0:
                raise APILimitRateError()
        response.raise_for_status()

    def get_latest_release(self) -> str:
        """Fetch the latest release tag from the GitHub API."""
        url = "https://api.github.com/repos/likelovewant/ollama-for-amd/releases/latest"
        response = requests.get(url, headers=self._get_auth_headers())
        self.check_rate_limit(response)
        return response.json()["tag_name"]

    def full_install_thread(self):
        threading.Thread(target=self._execute_full_install,
                         daemon=True).start()

    def replace_only_thread(self):
        threading.Thread(target=self._execute_replace_only,
                         daemon=True).start()

    def fix_05Error_thread(self):
        threading.Thread(target=self.fix_05Error, daemon=True).start()

    def _execute_full_install(self):
        """Download and silently install the base Ollama app, then initiate library replacement."""
        try:
            self.set_ui_state("disabled")
            self.log_msg("Checking for latest version...")
            latest_version = self.get_latest_release()
            self.log_msg(f"Latest version found: {latest_version}")

            if not messagebox.askyesno("Install", f"Install version {latest_version}?"):
                return

            os.makedirs(latest_version, exist_ok=True)
            proxy = self.proxy_selector.get_selected_proxy_url()

            exe_url = f"{proxy}{self.base_url}/{latest_version}/OllamaSetup.exe"
            exe_filename = os.path.join(latest_version, "OllamaSetup.exe")
            self.log_msg(f"Downloading {os.path.basename(exe_filename)}...")
            self.download_file(exe_url, exe_filename)

            self.log_msg("Running Installer...")
            self.kill_ollama()
            subprocess.run([exe_filename, "/SILENT"], check=True)
            self.log_msg("Base App installed successfully.")

            self._execute_replace_only(latest_version)

        except APILimitRateError:
            self.show_API_rate_limit_messagebox()
        except Exception as e:
            self.log_msg(f"Installation failed: {str(e)}", "ERROR")
            messagebox.showerror("Error", f"Installation failed: {e}")
        finally:
            self.set_ui_state("normal")

    def _execute_replace_only(self, version_tag=None):
        """Download and inject the foundational ROCm framework and specific GPU libraries."""
        try:
            self.set_ui_state("disabled")
            gpu_model = self.gpu_var.get()
            if not gpu_model:
                messagebox.showwarning(
                    "Warning", "Please select a GPU model first.")
                return

            if not version_tag:
                self.log_msg("Fetching version info...")
                version_tag = self.get_latest_release()

            os.makedirs(version_tag, exist_ok=True)
            proxy = self.proxy_selector.get_selected_proxy_url()

            ollama_path = self.find_ollama_path()
            if not ollama_path:
                self.log_msg("Ollama path not found. Aborting.", "ERROR")
                return

            rocm_target_dir = os.path.join(
                ollama_path, "lib", "ollama", "rocm")

            # Phase 1: Establish the foundational ROCm environment
            base_zip_url = f"{proxy}{self.base_url}/{version_tag}/ollama-windows-amd64.7z"
            base_zip_path = os.path.join(
                version_tag, "ollama-windows-amd64.7z")

            if not os.path.exists(base_zip_path):
                self.log_msg("Downloading Foundation ROCm Framework...")
                self.download_file(base_zip_url, base_zip_path)

            self.kill_ollama()

            self.log_msg("Clearing old ROCm environment...")
            if os.path.exists(rocm_target_dir):
                shutil.rmtree(rocm_target_dir, ignore_errors=True)
            os.makedirs(rocm_target_dir, exist_ok=True)

            self.log_msg("Extracting Foundation ROCm Framework...")
            with py7zr.SevenZipFile(base_zip_path, 'r') as archive:
                archive.extractall(path=rocm_target_dir)

            # Phase 2: Inject GPU-specific ROCm libraries
            rocm_url = get_rocm_url(gpu_model)
            if not rocm_url:
                raise ValueError(f"No ROCm URL matched for {gpu_model}")

            rocm_zip_path = os.path.join(
                version_tag, os.path.basename(rocm_url))
            if not os.path.exists(rocm_zip_path):
                self.log_msg(
                    f"Downloading Specific GPU Libs for {gpu_model}...")
                self.download_file(f"{proxy}{rocm_url}", rocm_zip_path)

            self.log_msg("Extracting GPU specific libs...")
            temp_dir = tempfile.mkdtemp()
            try:
                with py7zr.SevenZipFile(rocm_zip_path, "r") as zip_ref:
                    zip_ref.extractall(path=temp_dir)

                extracted_root = temp_dir
                items = os.listdir(temp_dir)
                if len(items) == 1 and os.path.isdir(os.path.join(temp_dir, items[0])):
                    extracted_root = os.path.join(temp_dir, items[0])

                rocblas_dll_src = os.path.join(extracted_root, "rocblas.dll")
                library_src = os.path.join(extracted_root, "library")

                if not os.path.exists(rocblas_dll_src):
                    raise FileNotFoundError(
                        "rocblas.dll missing from GPU zip archive!")

                self.log_msg("Injecting GPU Libraries...")
                shutil.copy2(rocblas_dll_src, rocm_target_dir)
                if os.path.exists(library_src):
                    dest_lib = os.path.join(
                        rocm_target_dir, "rocblas", "library")
                    os.makedirs(dest_lib, exist_ok=True)
                    shutil.copytree(library_src, dest_lib, dirs_exist_ok=True)

                self.log_msg("✅ Success! ROCm environment is fully updated.")
                messagebox.showinfo(
                    "Success", "Ollama AMD Libraries updated successfully.\nYou can now start Ollama.")
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

        except APILimitRateError:
            self.show_API_rate_limit_messagebox()
        except Exception as e:
            self.log_msg(f"Operation failed: {str(e)}", "ERROR")
            messagebox.showerror("Error", f"Operation failed: {e}")
        finally:
            self.set_ui_state("normal")

    def fix_05Error(self):
        """Apply the 0xc0000005 error fix by copying necessary DLLs into the active runners directory."""
        try:
            self.set_ui_state("disabled")
            self.log_msg("Attempting to fix 0xc0000005 Error...")
            ollama_base = self.find_ollama_path()
            if not ollama_base:
                self.log_msg("Ollama path not found.", "ERROR")
                return

            self.kill_ollama()
            source_dir = os.path.join(ollama_base, "lib", "ollama")
            runners_dir = os.path.join(source_dir, "runners")

            if not os.path.exists(runners_dir):
                os.makedirs(runners_dir, exist_ok=True)

            # Locate the most recent rocm_v* directory dynamically
            rocm_dirs = [d for d in os.listdir(
                runners_dir) if d.startswith("rocm_v")]
            if rocm_dirs:
                rocm_dirs.sort()
                dest_dir = os.path.join(runners_dir, rocm_dirs[-1])
            else:
                dest_dir = os.path.join(runners_dir, "rocm_v6.4")
                os.makedirs(dest_dir, exist_ok=True)

            self.log_msg(
                f"Targeting runners directory: {os.path.basename(dest_dir)}")
            files_to_copy = [f for f in os.listdir(
                source_dir) if f.endswith(".dll")]

            for f in files_to_copy:
                shutil.copy2(os.path.join(source_dir, f), dest_dir)

            self.log_msg("✅ Fix applied successfully.")
            messagebox.showinfo(
                "Success", "0xc0000005 Fix Applied. Try running Ollama.")
        except Exception as e:
            self.log_msg(f"Fix failed: {e}", "ERROR")
        finally:
            self.set_ui_state("normal")

    def download_file(self, url: str, filename: str):
        """Download file and handle Chunked Transfer Encoding (Missing Content-Length) gracefully."""
        try:
            response = requests.get(
                url, headers=self._get_auth_headers(), stream=True)
            self.check_rate_limit(response)

            total_size = int(response.headers.get("content-length", 0) or 0)
            written = 0
            start_time = time.time()

            tqdm_total = total_size if total_size > 0 else None

            # Switch to indeterminate loading animation if the download size is unknown
            if total_size == 0:
                self.progress.configure(mode="indeterminate")
                self.progress.start(10)
            else:
                self.progress.configure(mode="determinate", maximum=total_size)

            with open(filename, "wb") as file, tqdm(total=tqdm_total, unit="iB", unit_scale=True, desc=os.path.basename(filename)) as pbar:
                for data in response.iter_content(chunk_size=8192):
                    if not data:
                        continue
                    size = file.write(data)
                    written += size
                    pbar.update(size)

                    if total_size > 0:
                        self.progress["value"] = written
                    self._update_speed(written, start_time)
                    self.master.update_idletasks()

            if total_size == 0:
                self.progress.stop()
                self.progress.configure(mode="determinate")
            self.progress["value"] = self.progress["maximum"] if total_size > 0 else 100
            self.speed_label.config(text="Download complete.")

        except Exception as e:
            self.log_msg(f"Download Error: {e}", "ERROR")
            if os.path.exists(filename):
                os.remove(filename)
            raise

    def _update_speed(self, downloaded: int, start_time: float):
        """Update speed status label during file transfer."""
        elapsed = time.time() - start_time
        if elapsed > 0.5:
            speed_mb = (downloaded / (1024 * 1024)) / elapsed
            self.speed_label.config(
                text=f"Speed: {speed_mb:.2f} MB/s | Downloaded: {downloaded/(1024*1024):.2f} MB")

    def show_API_rate_limit_messagebox(self):
        """Notify the user that GitHub API rate limit has been hit."""
        self.log_msg("GitHub API Rate Limit Exceeded.", "ERROR")
        messagebox.showerror("API Rate Limit Exceeded",
                             "GitHub rate limit hit. Add a Personal Access Token (PAT) or use a Proxy.")

    def set_ui_state(self, state):
        """Toggle main button states to prevent spam clicking during tasks."""
        self.check_button.config(state=state)
        self.replace_button.config(state=state)
        self.fix_button.config(state=state)

    def load_settings(self):
        """Load previously saved GPU selection from configuration file."""
        try:
            if os.path.exists("settings.txt"):
                with open("settings.txt", "r") as f:
                    saved_gpu = f.readline().strip()
                    if saved_gpu in GPU_ROCM_MAPPING:
                        self.gpu_var.set(saved_gpu)
        except Exception:
            pass

    def save_settings(self):
        """Persist current GPU selection configuration to file."""
        try:
            with open("settings.txt", "w") as f:
                f.write(f"{self.gpu_var.get()}\n")
        except Exception:
            pass


def main():
    if not is_admin():
        if messagebox.askyesno("Admin Rights Needed", "Ollama system files are protected.\nRestart the application as Administrator?"):
            restart_as_admin()
        return

    root = tk.Tk()
    app = OllamaInstallerGUI(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (
        app.save_settings(), root.destroy()))
    root.mainloop()


if __name__ == "__main__":
    main()
