import tkinter as tk
from tkinter import ttk, messagebox, filedialog
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
from typing import Dict, List, Optional, Tuple

class APILimitRateError(Exception):
    pass

# Set up logging with more detailed configuration
logging.basicConfig(
    filename="ollama_installer.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(module)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# GPU to ROCm library mapping - UPDATED with descriptive names
GPU_ROCM_MAPPING = {
    "gfx90c-xnack- (Radeon Pro Vega)": "rocm.gfx90c-xnack-.for.hip.skd.6.2.4.7z",
    "gfx1010/11/12 xnack (RX 5000 Series, e.g., 5700 XT)": "rocm.gfx1010-xnack-gfx1011-xnack-gfx1012-xnack-.for.hip.sdk.6.2.4.7z",
    "gfx1010/12 no-xnack (RX 5000 Series, e.g., 5700 XT)": "rocm.gfx1010-gfx1012-for.hip.sdk.6.2.4.7z",
    "gfx1031 (Radeon RX 6700 XT)": "rocm.gfx1031.for.hip.sdk.6.2.4.littlewu.s.logic.7z",
    "gfx1032 (Radeon RX 6600 XT)": "rocm.gfx1032.for.hip.sdk.6.2.4.navi21.logic.7z",
    "gfx1034/35/36 (APUs: Steam Deck, Ryzen 6000 'Rembrandt')": "rocm.gfx1034-gfx1035-gfx1036.for.hip.sdk.6.2.4.7z",
    "gfx1103 (APUs: Ryzen 7040/8040 'Phoenix', e.g., 780M)": "rocm.gfx1103.AMD.780M.phoenix.V5.0.for.hip.sdk.6.2.4.7z",
    "gfx1150 (APUs: Ryzen AI 300 'Strix Point')": "rocm.gfx1150.for.hip.skd.6.2.4.7z",
    "gfx1151 (APUs: Ryzen AI 300 'Strix Point')": "rocm.gfx1151.for.hip.skd.6.2.4.7z",
    "gfx1200 (Radeon 9000 Series 'Navi 48')": "rocm.gfx1200.for.rocm.6.2.4-no-optimized.7z",
    "gfx1201 (Radeon 9000 Series 'Navi 44')": "rocm.gfx1201.for.hip.skd.6.2.4-no-optimized.7z"
}


BASE_URL = "https://github.com/likelovewant/ROCmLibs-for-gfx1103-AMD780M-APU/releases/download/v0.6.2.4/"


def get_rocm_url(gpu_model: str) -> Optional[str]:
    """Get the ROCm download URL for a given GPU model."""
    if gpu_model in GPU_ROCM_MAPPING:
        return BASE_URL + GPU_ROCM_MAPPING[gpu_model]
    return None


def is_admin() -> bool:
    """Check if the program is running with administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def restart_as_admin():
    """Restart the program with administrator privileges."""
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1
    )
    sys.exit()


class ProxySelector:
    """Handles proxy selection and management for the application."""

    DEFAULT_PROXIES = {
        "Default (No Proxy)": "",
        "GHProxy": "https://ghfast.top/",
        "GitHub Mirror": "https://github.moeyy.xyz/",
        "CF Worker": "https://gh.api.99988866.xyz/"
    }

    def __init__(self, master):
        """Initialize proxy selector component."""
        self.master = master
        self.proxies: Dict[str, str] = self.load_proxies()
        self.selected_proxy = tk.StringVar(value="Default (No Proxy)")
        self.custom_proxy = tk.StringVar()
        self.ping_results: Dict[str, float] = {}
        self.placeholder = "e.g., https://proxy.example.com/"
        self.create_widgets()

    def create_widgets(self):
        """Create and layout proxy selector GUI components."""
        self.proxy_frame = ttk.LabelFrame(self.master, text="Proxy Settings", padding=(10, 5))
        self.proxy_frame.grid(row=2, column=0, columnspan=2, pady=(10, 5), padx=10, sticky="ew")
        self.proxy_frame.columnconfigure(1, weight=1)

        ttk.Label(self.proxy_frame, text="Select Proxy:").grid(row=0, column=0, pady=5, padx=5, sticky="w")
        self.proxy_combo = ttk.Combobox(self.proxy_frame, textvariable=self.selected_proxy)
        self.update_proxy_list()
        self.proxy_combo.grid(row=0, column=1, columnspan=2, pady=5, padx=5, sticky="ew")

        ttk.Label(self.proxy_frame, text="Custom Proxy:").grid(row=1, column=0, pady=5, padx=5, sticky="w")
        self.custom_entry = ttk.Entry(self.proxy_frame, textvariable=self.custom_proxy)
        self.custom_entry.grid(row=1, column=1, pady=5, padx=5, sticky="ew")
        
        # Placeholder logic
        self.custom_entry.insert(0, self.placeholder)
        self.custom_entry.config(foreground="grey")
        self.custom_entry.bind("<FocusIn>", self.on_entry_focus_in)
        self.custom_entry.bind("<FocusOut>", self.on_entry_focus_out)

        add_btn = ttk.Button(self.proxy_frame, text="Add", command=self.add_custom_proxy)
        add_btn.grid(row=1, column=2, pady=5, padx=5, sticky="e")

        test_btn = ttk.Button(self.proxy_frame, text="Test Proxies", command=self.start_proxy_test)
        test_btn.grid(row=2, column=0, columnspan=3, pady=5, padx=5, sticky="ew")

        self.result_text = tk.Text(self.proxy_frame, height=4)
        self.result_text.grid(row=3, column=0, columnspan=3, pady=(5,0), padx=5, sticky="ew")

    def on_entry_focus_in(self, event):
        """Handle focus in on custom proxy entry to remove placeholder."""
        if self.custom_entry.get() == self.placeholder:
            self.custom_entry.delete(0, tk.END)
            self.custom_entry.config(foreground="black")

    def on_entry_focus_out(self, event):
        """Handle focus out on custom proxy entry to restore placeholder if empty."""
        if not self.custom_entry.get():
            self.custom_entry.insert(0, self.placeholder)
            self.custom_entry.config(foreground="grey")

    def update_proxy_list(self):
        """Update the proxy dropdown list."""
        proxy_list = list(self.proxies.keys())
        self.proxy_combo["values"] = proxy_list
        if self.selected_proxy.get() not in proxy_list:
            self.selected_proxy.set(proxy_list[0])

    def get_selected_proxy_url(self) -> Optional[str]:
        """Get currently selected proxy URL."""
        proxy_name = self.selected_proxy.get()
        if proxy_name == "Default (No Proxy)":
            return ""
        return self.proxies.get(proxy_name, "")

    def add_custom_proxy(self):
        """Add custom proxy URL to available proxies."""
        custom_url = self.custom_proxy.get().strip()
        if not custom_url or custom_url == self.placeholder:
            return

        if not custom_url.startswith(("http://", "https://")):
            custom_url = "https://" + custom_url
        if not custom_url.endswith("/"):
            custom_url += "/"

        proxy_name = f"Custom ({custom_url})"
        self.proxies[proxy_name] = custom_url
        self.save_proxies()
        self.update_proxy_list()
        self.proxy_combo.set(proxy_name)
        self.custom_proxy.set("")
        self.on_entry_focus_out(None) # Restore placeholder

    def load_proxies(self) -> Dict[str, str]:
        """Load saved proxies from config file."""
        try:
            if os.path.exists("proxy_config.json"):
                with open("proxy_config.json", "r") as f:
                    saved_proxies = json.load(f)
                    proxies = self.DEFAULT_PROXIES.copy()
                    proxies.update(saved_proxies)
                    return proxies
        except Exception as e:
            logging.error(f"Error loading proxy config: {e}")
        return self.DEFAULT_PROXIES.copy()

    def save_proxies(self):
        """Save current proxy list to config file."""
        try:
            save_proxies = {k: v for k, v in self.proxies.items() if "Default" not in k}
            with open("proxy_config.json", "w") as f:
                json.dump(save_proxies, f, indent=2)
        except Exception as e:
            logging.error(f"Error saving proxy config: {e}")

    def test_proxy(self, name: str, url: str) -> float:
        """Test a single proxy's response time"""
        test_url = f"{url}https://github.com/ByronLeeeee/Ollama-For-AMD-Installer/blob/main/requirements.txt"
        if name == "Default (No Proxy)":
            test_url = "https://github.com/ByronLeeeee/Ollama-For-AMD-Installer/blob/main/requirements.txt"
        try:
            start_time = time.time()
            response = requests.get(test_url, timeout=5)
            response.raise_for_status()
            return time.time() - start_time
        except Exception:
            return float('inf')

    def start_proxy_test(self):
        """Start proxy testing in a separate thread"""
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, "Testing proxies...\n")
        threading.Thread(target=self.test_all_proxies, daemon=True).start()

    def test_all_proxies(self):
        """Test all proxies and update results"""
        self.ping_results.clear()
        for name, url in self.proxies.items():
            response_time = self.test_proxy(name, url)
            self.ping_results[name] = response_time
            self.master.after(0, self.update_result_display, name, response_time)
        
        sorted_proxies = dict(sorted(self.ping_results.items(), key=lambda x: x[1]))
        if sorted_proxies:
            best_proxy = next(iter(sorted_proxies))
            self.master.after(0, self.proxy_combo.set, best_proxy)
            self.result_text.insert(tk.END, f"\nBest proxy: {best_proxy}\n")
            
        self.result_text.insert(tk.END, "Done!\n")
        self.result_text.see(tk.END)

    def update_result_display(self, name: str, response_time: float):
        """Update the result display with proxy test results"""
        result = f"{name}: Failed\n" if response_time == float('inf') else f"{name}: {response_time:.2f}s\n"
        self.result_text.insert(tk.END, result)
        self.result_text.see(tk.END)

class OllamaInstallerGUI:
    """Main GUI application for Ollama installation and management."""
    def __init__(self, master):
        """Initialize main application GUI."""
        self.master = master
        master.title("Ollama For AMD Installer")
        master.geometry("700x700")
        master.columnconfigure(0, weight=1)

        self.repo = "likelovewant/ollama-for-amd"
        self.base_url = f"https://github.com/{self.repo}/releases/download"
        self.github_url = "https://github.com/ByronLeeeee/Ollama-For-AMD-Installer"
        self.gpu_var = tk.StringVar()
        self.github_access_token_placeholder = "e.g., ghp_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
        self.github_access_token_var = tk.StringVar()

        self.create_widgets()
        self.proxy_selector = ProxySelector(master)
        self.load_settings()

    def create_widgets(self):
        """Create and layout main application GUI components."""
        # --- GPU Selection Frame ---
        gpu_frame = ttk.LabelFrame(self.master, text="GPU Selection", padding=(10, 5))
        gpu_frame.grid(row=0, column=0, columnspan=2, pady=10, padx=10, sticky="ew")
        gpu_frame.columnconfigure(1, weight=1)
        ttk.Label(gpu_frame, text="GPU Model:").grid(row=0, column=0, pady=5, padx=5, sticky="w")
        self.gpu_combo = ttk.Combobox(gpu_frame, textvariable=self.gpu_var, values=list(GPU_ROCM_MAPPING.keys()))
        self.gpu_combo.grid(row=0, column=1, pady=5, padx=5, sticky="ew")

        # --- Main Actions Frame ---
        actions_frame = ttk.LabelFrame(self.master, text="Main Actions", padding=(10, 5))
        actions_frame.grid(row=1, column=0, columnspan=2, pady=5, padx=10, sticky="ew")
        actions_frame.columnconfigure(0, weight=1)
        self.check_button = ttk.Button(actions_frame, text="Download and Install Latest Ollama", command=self.check_version_thread)
        self.check_button.grid(row=0, column=0, pady=5, padx=5, sticky="ew")
        self.replace_button = ttk.Button(actions_frame, text="Replace ROCm Libraries Only", command=self.replace_only_btn_clicked)
        self.replace_button.grid(row=1, column=0, pady=5, padx=5, sticky="ew")

        # --- Troubleshooting Frame ---
        troubleshoot_frame = ttk.LabelFrame(self.master, text="Troubleshooting", padding=(10, 5))
        troubleshoot_frame.grid(row=3, column=0, columnspan=2, pady=5, padx=10, sticky="ew")
        troubleshoot_frame.columnconfigure(1, weight=1)
        self.fix_button = ttk.Button(troubleshoot_frame, text="Fix 0xc0000005 Error", command=self.fix_05Error)
        self.fix_button.grid(row=0, column=0, columnspan=2, pady=5, padx=5, sticky="ew")
        ttk.Label(troubleshoot_frame, text="GitHub Personal Access Token:").grid(row=1, column=0, pady=5, sticky="w")
        self.github_access_token_entry = ttk.Entry(troubleshoot_frame, textvariable=self.github_access_token_var)
        self.github_access_token_entry.grid(row=1, column=1, pady=5, padx=5, sticky="ew")
        # Placeholder logic
        # self.github_access_token_entry.insert(0, self.github_access_token_placeholder)
        self.github_access_token_var.set(self.github_access_token_placeholder)
        self.github_access_token_entry.config(foreground="grey")
        self.github_access_token_entry.bind("<FocusIn>", self.on_github_access_token_entry_focus_in)
        self.github_access_token_entry.bind("<FocusOut>", self.on_github_access_token_entry_focus_out)
        ttk.Label(troubleshoot_frame, text="GitHub Personal Access Token will NOT be used when using proxy.").grid(row=2, columnspan=2, pady=5, sticky="ew")

        # --- Status and Progress ---
        status_frame = ttk.Frame(self.master, padding=(10, 5))
        status_frame.grid(row=4, column=0, columnspan=2, pady=10, padx=10, sticky="ew")
        status_frame.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(status_frame, length=300, mode="determinate")
        self.progress.grid(row=0, column=0, columnspan=2, pady=(5,0), sticky="ew")
        self.speed_label = ttk.Label(status_frame, text="")
        self.speed_label.grid(row=1, column=0, pady=(5,0), sticky="w")
        self.status_label = ttk.Label(status_frame, text="Ready.")
        self.status_label.grid(row=2, column=0, pady=(5,0), sticky="w")
        
        # --- Footer ---
        footer_frame = ttk.Frame(self.master)
        footer_frame.grid(row=5, column=0, columnspan=2, padx=10, sticky="se")
        self.master.rowconfigure(5, weight=1)
        
        # Clickable GitHub Link
        link_label = tk.Label(footer_frame, text="GitHub:", font=("Arial", 8), fg="black")
        link_label.pack(side="left", pady=(10,5))
        self.source_label = tk.Label(footer_frame, text=self.github_url.split("/")[-2] + "/" + self.github_url.split("/")[-1], font=("Arial", 8, "underline"), fg="blue", cursor="hand2")
        self.source_label.pack(side="left", pady=(10,5))
        self.source_label.bind("<Button-1>", self.open_github_link)

    def find_ollama_path(self) -> Optional[str]:
        """Find the Ollama installation path automatically or by asking the user."""
        # 1. Check Windows Registry
        try:
            hkey = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Ollama")
            install_path = winreg.QueryValueEx(hkey, "InstallLocation")[0]
            winreg.CloseKey(hkey)
            if os.path.exists(install_path):
                logging.info(f"Found Ollama via registry: {install_path}")
                return install_path
        except FileNotFoundError:
            logging.warning("Ollama not found in HKLM Uninstall registry key.")
        except Exception as e:
            logging.error(f"Error reading registry: {e}")

        # 2. Check default path
        default_path = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama")
        if os.path.exists(default_path):
            logging.info(f"Found Ollama at default path: {default_path}")
            return default_path

        # 3. Ask the user
        if messagebox.askokcancel("Ollama Not Found", "Could not automatically locate the Ollama installation directory. Would you like to select it manually?"):
            user_path = filedialog.askdirectory(title="Please select your Ollama installation folder")
            if user_path and os.path.exists(os.path.join(user_path, "ollama.exe")):
                logging.info(f"User selected Ollama path: {user_path}")
                return user_path
        
        messagebox.showerror("Error", "Ollama installation path could not be determined. Cannot continue.")
        return None


    def open_github_link(self, event=None):
        """Open the project's GitHub page in a web browser."""
        webbrowser.open_new_tab(self.github_url)

    def check_version_thread(self):
        """Start version check in separate thread."""
        threading.Thread(target=self.check_version, daemon=True).start()

    def show_API_rate_limit_messagebox(self):
        messagebox.showerror(
                "API Rate Limit Exceeded",
                "GitHub limits unauthenticated requests to 60 per hour per IP address. \n" \
                    "To avoid hitting this rate limit, you can use the GitHub Personal Access Token (PAT) for authentication."
            )

    def check_version(self):
        """Check for new version and prompt for installation."""
        try:
            self.status_label.config(text="Checking for new version...")
            self.latest_version = self.get_latest_release()
            if messagebox.askyesno("Latest Version", f"Latest version found: {self.latest_version}\nDo you want to download and install now?"):
                self.download_and_install()
        except APILimitRateError:
            self.show_API_rate_limit_messagebox()
            self.status_label.config(text="Error checking version.")
        except Exception as e:
            logging.error(f"Version check failed: {e}")
            messagebox.showerror("Error", f"Version check failed: {e}")
            self.status_label.config(text="Error checking version.")
    
    def on_github_access_token_entry_focus_in(self, event):
        """Handle focus in on GitHub Personal Access Token entry to remove placeholder."""
        if self.github_access_token_entry.get() == self.github_access_token_placeholder:
            self.github_access_token_var.set("")
            self.github_access_token_entry.config(foreground="black")

    def on_github_access_token_entry_focus_out(self, event):
        """Handle focus out on GitHub Personal Access Token entry to restore placeholder if empty."""
        if not self.github_access_token_entry.get():
            self.github_access_token_var.set(self.github_access_token_placeholder)
            self.github_access_token_entry.config(foreground="grey")

    def get_latest_release(self) -> str:
        """Get latest release version from GitHub API."""
        url = "https://api.github.com/repos/likelovewant/ollama-for-amd/releases/latest"

        github_access_token = self.github_access_token_var.get().strip()
        if github_access_token == self.github_access_token_placeholder:
            github_access_token = ""

        response = requests.get(
            url=url,
            headers={
                "Authorization": f"Bearer {github_access_token}"
            }
            if github_access_token and not self.proxy_selector.get_selected_proxy_url()
            else None,
        )
        if (response.status_code == 403 or response.status_code == 429) and (
            response.headers["x-ratelimit-remaining"]
            and int(response.headers["x-ratelimit-remaining"]) == 0
        ):
            raise APILimitRateError
        else:
            response.raise_for_status()
        return response.json()["tag_name"]

    def download_and_install(self):
        """Download and install specified version."""
        exe_url = f"{self.base_url}/{self.latest_version}/OllamaSetup.exe"
        proxy_url = self.proxy_selector.get_selected_proxy_url()
        if proxy_url:
            exe_url = f"{proxy_url}{exe_url}"
        exe_filename = os.path.join(self.latest_version, "OllamaSetup.exe")
        os.makedirs(self.latest_version, exist_ok=True)
        try:
            self.status_label.config(text=f"Downloading {os.path.basename(exe_filename)}...")
            self.download_file(exe_url, exe_filename)
            self.status_label.config(text="Installing Ollama...")
            self.install_exe(exe_filename)
            self.status_label.config(text="Extracting and replacing libraries...")
            self.download_and_replace_rocblas()
        except APILimitRateError:
            self.show_API_rate_limit_messagebox()
            self.status_label.config(text="Installation failed.")
        except Exception as e:
            logging.error(f"Installation failed: {e}")
            messagebox.showerror("Error", f"Installation failed: {e}")
            self.status_label.config(text="Installation failed.")

    def download_file(self, url: str, filename: str):
        """Download file with progress tracking."""
        try:
            github_access_token = self.github_access_token_var.get().strip()
            if github_access_token == self.github_access_token_placeholder:
                github_access_token = ""
            
            response = requests.get(
                url,
                headers={
                    "Authorization": f"Bearer {github_access_token}"
                }
                if github_access_token and not self.proxy_selector.get_selected_proxy_url()
                else None, 
                stream=True
            )
            if (response.status_code == 403 or response.status_code == 429) and (
                response.headers["x-ratelimit-remaining"]
                and int(response.headers["x-ratelimit-remaining"]) == 0
            ):
                raise APILimitRateError
            else:
                response.raise_for_status()
            total_size = int(response.headers.get("content-length", 0))
            if total_size == 0:
                raise ValueError("Content-Length header is missing or zero.")
            block_size = 1024
            written = 0
            start_time = time.time()
            with open(filename, "wb") as file, tqdm(total=total_size, unit="iB", unit_scale=True, desc=os.path.basename(filename)) as progress_bar:
                for data in response.iter_content(block_size):
                    size = file.write(data)
                    written += size
                    progress_bar.update(size)
                    self.update_progress(written, total_size)
                    self.update_speed(written, start_time)
            self.speed_label.config(text="")
        except Exception as e:
            logging.error(f"Download failed for {url}: {e}")
            if os.path.exists(filename):
                os.remove(filename)
            raise

    def update_progress(self, current: int, total: int):
        """Update progress bar."""
        if total > 0:
            self.progress["value"] = int((current / total) * 100)
            self.master.update_idletasks()

    def update_speed(self, downloaded: int, start_time: float):
        """Update download speed display."""
        elapsed_time = time.time() - start_time
        if elapsed_time > 0.5:
            speed = downloaded / (1024 * elapsed_time)
            self.speed_label.config(text=f"Speed: {speed:.2f} KB/s")
            self.master.update_idletasks()

    def install_exe(self, filename: str):
        """Install downloaded executable."""
        try:
            self.master.update_idletasks()
            subprocess.run([filename, "/SILENT"], check=True)
            self.status_label.config(text="OLLAMA installed successfully.")
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            logging.error(f"Installation failed: {e}")
            raise

    def replace_only_btn_clicked(self):
        """Handle replace ROCm libraries button click."""
        self.status_label.config(text="Starting ROCm library replacement...")
        try:
            self.latest_version = self.get_latest_release()
            os.makedirs(self.latest_version, exist_ok=True)
            self.download_and_replace_rocblas()
        except Exception as e:
            logging.error(f"ROCm replacement failed: {e}")
            messagebox.showerror("Error", f"Failed to get latest release info: {e}")
            self.status_label.config(text="Error replacing ROCm libraries.")

    def download_and_replace_rocblas(self):
        """Download and replace ROCm libraries for selected GPU."""
        self.gpu_model = self.gpu_var.get()
        if not self.gpu_model:
            messagebox.showerror("Error", "Please select a GPU model first.")
            return

        rocm_url = get_rocm_url(self.gpu_model)
        if not rocm_url:
            messagebox.showerror("Error", f"No ROCm file found for {self.gpu_model}")
            return
        
        proxy_url = self.proxy_selector.get_selected_proxy_url()
        if proxy_url:
            rocm_url = f"{proxy_url}{rocm_url}"
        
        try:
            rocm_filename = os.path.basename(rocm_url)
            rocm_zip_path = os.path.join(self.latest_version, rocm_filename)
            if not os.path.exists(rocm_zip_path):
                self.status_label.config(text=f"Downloading {rocm_filename}...")
                self.download_file(rocm_url, rocm_zip_path)
            else:
                self.status_label.config(text="ROCm libraries already downloaded.")
            self.status_label.config(text="Extracting and replacing libraries...")
            self.extract_and_replace_rocblas(rocm_zip_path)
        except APILimitRateError:
            self.show_API_rate_limit_messagebox()
        except Exception as e:
            logging.error(f"ROCm library replacement failed: {e}")
            messagebox.showerror("Error", f"ROCm library replacement failed: {e}")
            self.status_label.config(text="Error replacing ROCm libraries.")

    def extract_and_replace_rocblas(self, zip_path: str):
        """Extract and replace ROCm libraries from zip file."""
        ollama_base_path = self.find_ollama_path()
        if not ollama_base_path:
            self.status_label.config(text="Ollama not found. Aborted.")
            return

        rocblas_dll_for_rocm_path = os.path.join(ollama_base_path, "lib", "ollama", "rocm")
        library_path = os.path.join(rocblas_dll_for_rocm_path, "rocblas", "library")
        temp_dir = tempfile.mkdtemp()
        try:
            self.status_label.config(text=f"Extracting {os.path.basename(zip_path)}...")
            with py7zr.SevenZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(path=temp_dir)

            extracted_content_path = temp_dir
            if len(os.listdir(temp_dir)) == 1:
                nested_dir = os.path.join(temp_dir, os.listdir(temp_dir)[0])
                if os.path.isdir(nested_dir):
                    extracted_content_path = nested_dir
            
            rocblas_dll_src = os.path.join(extracted_content_path, "rocblas.dll")
            library_src = os.path.join(extracted_content_path, "library")
            if not os.path.exists(rocblas_dll_src): raise FileNotFoundError("rocblas.dll not found in the extracted archive.")
            if not os.path.exists(library_src): raise FileNotFoundError("'library' folder not found in the extracted archive.")

            os.makedirs(rocblas_dll_for_rocm_path, exist_ok=True)
            os.makedirs(library_path, exist_ok=True)

            self.status_label.config(text="Copying rocblas.dll...")
            shutil.copy2(rocblas_dll_src, rocblas_dll_for_rocm_path)
            self.status_label.config(text="Copying library folder...")
            shutil.copytree(library_src, library_path, dirs_exist_ok=True)
            self.status_label.config(text="ROCm libraries updated successfully.")
            messagebox.showinfo("Success", "Ollama has been updated successfully.\nPlease restart Ollama for changes to take effect.")
        except Exception as e:
            logging.error(f"Library extraction failed: {e}")
            self.status_label.config(text=f"Library extraction failed: {str(e)}")
            raise
        finally:
            shutil.rmtree(temp_dir)

    def fix_05Error(self):
        """Fix common 0xc0000005 error by copying libraries."""
        self.status_label.config(text="Attempting to fix 0xc0000005 Error...")
        
        ollama_base_path = self.find_ollama_path()
        if not ollama_base_path:
            self.status_label.config(text="Ollama not found. Aborted.")
            return

        try:
            source_dir = os.path.join(ollama_base_path, "lib", "ollama")
            dest_dir = os.path.join(source_dir, "runners", "rocm_v6.2.4")

            os.makedirs(dest_dir, exist_ok=True)
            files_to_copy = [f for f in os.listdir(source_dir) if f.endswith(".dll")]
            for filename in files_to_copy:
                shutil.copy2(os.path.join(source_dir, filename), dest_dir)
                logging.info(f"Copied {filename} to runners directory.")
            self.status_label.config(text="0xc0000005 Error fix applied successfully.")
            messagebox.showinfo("Success", "The fix has been applied. Please try running Ollama again.")
        except Exception as e:
            logging.error(f"Error fix failed: {e}")
            self.status_label.config(text=f"Error fix failed: {str(e)}")
            messagebox.showerror("Error", f"Applying the fix failed: {e}")

    def load_settings(self):
        """Load saved settings from file."""
        try:
            if os.path.exists("settings.txt"):
                with open("settings.txt", "r") as f:
                    saved_gpu = f.readline().strip()
                    if saved_gpu in GPU_ROCM_MAPPING:
                        self.gpu_var.set(saved_gpu)
        except Exception as e:
            logging.error(f"Failed to load settings: {e}")

    def save_settings(self):
        """Save current settings to file."""
        try:
            with open("settings.txt", "w") as f:
                f.write(f"{self.gpu_var.get()}\n")
        except Exception as e:
            logging.error(f"Failed to save settings: {e}")

    def on_closing(self):
        """Handle application closing."""
        try:
            self.save_settings()
        except Exception as e:
            logging.error(f"Error during shutdown: {e}")
        finally:
            self.master.destroy()

def main():
    """Main entry point for the application."""
    if not is_admin():
        if messagebox.askyesno("Administrator Privileges Required", "This application requires administrator privileges to modify program files.\nWould you like to restart as an administrator?"):
            restart_as_admin()
        return

    try:
        root = tk.Tk()
        app = OllamaInstallerGUI(root)
        root.protocol("WM_DELETE_WINDOW", app.on_closing)
        root.mainloop()
    except Exception as e:
        logging.critical(f"Application failed to start: {e}", exc_info=True)
        messagebox.showerror("Critical Error", f"Application failed to start: {e}\nCheck ollama_installer.log for details.")

if __name__ == "__main__":
    main()