import tkinter as tk
from tkinter import ttk, messagebox
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
from typing import Dict, List, Optional, Tuple

# Set up logging with more detailed configuration
logging.basicConfig(
    filename="ollama_installer.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(module)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# GPU to ROCm library mapping
GPU_ROCM_MAPPING = {
    "gfx1010-xnack-": "rocm.gfx1010-xnack-.for.hip.sdk.6.1.2.7z",
    "gfx1011": "rocm.gfx1011.for.hip.sdk.6.1.2.7z",
    "gfx1012-xnack-": "rocm.gfx1012-xnack-.for.hip.sdk.6.1.2.7z",
    "gfx1031": "rocm.gfx1031.for.hip.sdk.6.1.2.7z",
    "gfx1031 (optimized)": "rocm.gfx1031.for.hip.sdk.6.1.2.optimized.with.little.wu.s.logic.7z",
    "gfx1032": "rocm.gfx1032.for.hip.sdk.6.1.2.7z",
    "gfx1034": "rocm.gfx1034.for.hip.sdk.6.1.2.7z",
    "gfx1035": "rocm.gfx1035.for.hip.sdk.6.1.2.7z",
    "gfx1036": "rocm.gfx1036.for.hip.sdk.6.1.2.7z",
    "gfx1103 (AMD 780M)": "rocm.gfx1103.AMD.780M.phoenix.V4.0.for.hip.sdk.6.1.2.7z",
    "gfx803 (Vega 10)": "rocm.gfx803.optic.vega10.logic.hip.sdk.6.1.2.7z",
    "gfx902": "rocm.gfx902.for.hip.sdk.6.1.2.7z",
    "gfx90c-xnack-": "rocm.gfx90c-xnack-.for.hip.sdk.6.1.2.7z",
    "gfx90c": "rocm.gfx90c.for.hip.sdk.6.1.2.7z",
}

BASE_URL = "https://github.com/likelovewant/ROCmLibs-for-gfx1103-AMD780M-APU/releases/download/v0.6.1.2/"


def get_rocm_url(gpu_model: str) -> Optional[str]:
    """Get the ROCm download URL for a given GPU model."""
    if gpu_model in GPU_ROCM_MAPPING:
        return BASE_URL + GPU_ROCM_MAPPING[gpu_model]
    return None


def is_admin() -> bool:
    """Check if the program is running with administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
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
        "GHProxy": "https://ghproxy.com/",
        "GitHub Mirror": "https://github.moeyy.xyz/",
        "FastGit": "https://raw.fastgit.org/",
        "CF Worker": "https://gh.api.99988866.xyz/"
    }

    def __init__(self, master, row: int = 1):
        """Initialize proxy selector component."""
        self.master = master
        self.proxies: Dict[str, str] = self.load_proxies()
        self.selected_proxy = tk.StringVar(value="Default (No Proxy)")
        self.custom_proxy = tk.StringVar()
        self.ping_results: Dict[str, float] = {}
        self.create_widgets(row)

    def create_widgets(self, row: int):
        """Create and layout proxy selector GUI components."""

        # Proxy settings frame
        proxy_frame = ttk.LabelFrame(self.master, text="Proxy Settings", padding=5)
        proxy_frame.grid(row=row, column=0, columnspan=2, pady=5, padx=10, sticky="ew")

        # Proxy selection dropdown
        ttk.Label(proxy_frame, text="Select Proxy:").grid(
            row=0, column=0, pady=5, padx=5, sticky="w"
        )
        self.proxy_combo = ttk.Combobox(
            proxy_frame, textvariable=self.selected_proxy, width=30
        )
        self.update_proxy_list()
        self.proxy_combo.grid(
            row=0, column=1, columnspan=2, pady=5, padx=5, sticky="ew"
        )

        # Custom proxy entry
        ttk.Label(proxy_frame, text="Custom Proxy:").grid(
            row=1, column=0, pady=5, padx=5, sticky="w"
        )
        custom_entry = ttk.Entry(proxy_frame, textvariable=self.custom_proxy, width=30)
        custom_entry.grid(row=1, column=1, pady=5, padx=5, sticky="ew")

        # Add custom proxy button
        add_btn = ttk.Button(proxy_frame, text="Add", command=self.add_custom_proxy)
        add_btn.grid(row=1, column=2, pady=5, padx=5, sticky="e")

        # Test proxies button
        test_btn = ttk.Button(proxy_frame, text="Test Proxies", command=self.start_proxy_test)
        test_btn.grid(row=2, column=0, columnspan=3, pady=5, padx=5, sticky="ew")

        # Ping results
        self.result_text = tk.Text(proxy_frame, height=4, width=40)
        self.result_text.grid(
            row=3, column=0, columnspan=3, pady=5, padx=5, sticky="ew"
        )

    def update_proxy_list(self):
        """Update the proxy dropdown list."""
        proxy_list = list(self.proxies.keys())
        self.proxy_combo["values"] = proxy_list
        if not self.selected_proxy.get() in proxy_list:
            self.selected_proxy.set(proxy_list[0])

    def get_selected_proxy_url(self) -> Optional[str]:
        """Get currently selected proxy URL."""
        proxy_name = self.selected_proxy.get()
        if proxy_name == "Default (No Proxy)":
            return None
        return self.proxies.get(proxy_name)

    def add_custom_proxy(self):
        """Add custom proxy URL to available proxies."""
        custom_url = self.custom_proxy.get().strip()
        if not custom_url:
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
            save_proxies = {
                k: v for k, v in self.proxies.items() if k != "Default (No Proxy)"
            }
            with open("proxy_config.json", "w") as f:
                json.dump(save_proxies, f, indent=2)
        except Exception as e:
            logging.error(f"Error saving proxy config: {e}")

    def test_proxy(self, name: str, url: str) -> float:
            """Test a single proxy's response time"""
            
            test_url = f"{url}https://github.com/ByronLeeeee/Ollama-For-AMD-Installer/blob/main/requirements.txt"

            try:
                start_time = time.time()
                response = requests.get(test_url, timeout=5)
                if response.status_code == 200:
                    return time.time() - start_time
            except Exception:
                pass
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
            
            # Update result display
            self.master.after(0, self.update_result_display, name, response_time)
        
        # Sort proxies by response time
        sorted_proxies = dict(sorted(self.ping_results.items(), key=lambda x: x[1]))
        best_proxy = next(iter(sorted_proxies))
        
        # Auto-select best proxy
        self.master.after(0, self.proxy_combo.set, best_proxy)
        self.result_text.insert(tk.END, f"\nBest proxy: {best_proxy}\n")
        self.result_text.insert(tk.END, f"Done!\n")
        self.result_text.see(tk.END)

    
    def update_result_display(self, name: str, response_time: float):
        """Update the result display with proxy test results"""
        if response_time == float('inf'):
            result = f"{name}: Failed\n"
        else:
            result = f"{name}: {response_time:.2f}s\n"
        self.result_text.insert(tk.END, result)
        self.result_text.see(tk.END)
    
    def get_selected_proxy_url(self) -> str:
        """Get the currently selected proxy URL"""
        proxy_name = self.selected_proxy.get()
        return self.proxies.get(proxy_name, "")

class OllamaInstallerGUI:
    """Main GUI application for Ollama installation and management."""

    def __init__(self, master):
        """Initialize main application GUI."""
        self.master = master
        master.title("Ollama For AMD Installer")
        master.geometry("450x520")

        self.repo = "likelovewant/ollama-for-amd"
        self.base_url = f"https://github.com/{self.repo}/releases/download"

        self.gpu_var = tk.StringVar()
        self.create_widgets()
        self.proxy_selector = ProxySelector(master, row=7)

        self.load_settings()

    def create_widgets(self):
        """Create and layout main application GUI components."""
        gpu_frame = ttk.LabelFrame(self.master, text="GPU Settings", padding=5)
        gpu_frame.grid(row=0, column=0, columnspan=2, pady=5, padx=10, sticky="ew")

        ttk.Label(gpu_frame, text="GPU Model:").grid(
            row=0, column=0, pady=5, padx=5, sticky="w"
        )
        self.gpu_combo = ttk.Combobox(gpu_frame, textvariable=self.gpu_var)
        self.gpu_combo["values"] = list(GPU_ROCM_MAPPING.keys())
        self.gpu_combo.grid(row=0, column=1, pady=5, padx=5, sticky="ew")

        self.check_button = ttk.Button(
            self.master, text="Check for New Version", command=self.check_version_thread
        )
        self.check_button.grid(
            row=2, column=0, columnspan=2, pady=10, padx=10, sticky="ew"
        )

        self.replace_button = ttk.Button(
            self.master,
            text="Replace ROCm Libraries Only",
            command=self.replace_only_btn_clicked,
        )
        self.replace_button.grid(row=3, column=0, pady=10, padx=10, sticky="ew")

        self.fix_button = ttk.Button(
            self.master, text="Fix 0xc0000005 Error", command=self.fix_05Error
        )
        self.fix_button.grid(row=3, column=1, pady=10, padx=10, sticky="ew")

        self.progress = ttk.Progressbar(self.master, length=300, mode="determinate")
        self.progress.grid(row=4, column=0, columnspan=2, pady=10, padx=10, sticky="ew")

        self.speed_label = ttk.Label(self.master, text="Download Speed: 0 KB/s")
        self.speed_label.grid(
            row=5, column=0, columnspan=2, pady=5, padx=10, sticky="w"
        )

        self.status_label = ttk.Label(self.master, text="")
        self.status_label.grid(
            row=6, column=0, columnspan=2, pady=5, padx=10, sticky="w"
        )

        self.source_label = ttk.Label(
            self.master,
            text="Github: ByronLeeeee/Ollama-For-AMD-Installer",
            font=("Arial", 8),
        )
        self.source_label.grid(
            row=8, column=0, columnspan=2, pady=5, padx=10, sticky="se"
        )

    def check_version_thread(self):
        """Start version check in separate thread."""
        threading.Thread(target=self.check_version, daemon=True).start()

    def check_version(self):
        """Check for new version and prompt for installation."""
        try:
            self.status_label.config(text="Checking for new version...")
            self.latest_version = self.get_latest_release()
            if messagebox.askyesno(
                "Latest Version",
                f"Latest version found: {self.latest_version}\nDo you want to download and install now?",
            ):
                self.download_and_install()
        except Exception as e:
            logging.error(f"Version check failed: {e}")
            messagebox.showerror("Error", f"Version check failed: {e}")

    def get_latest_release(self) -> str:
        """Get latest release version from GitHub API."""
        url = "https://api.github.com/repos/likelovewant/ollama-for-amd/releases/latest"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()["tag_name"]

    def download_and_install(self):
        """Download and install specified version."""
        exe_url = f"{self.base_url}/{self.latest_version}/OllamaSetup.exe"
        libs_url = f"{self.base_url}/{self.latest_version}/ollama-windows-amd64.7z"
        if self.proxy_selector.get_selected_proxy_url():
            exe_url = f"{self.proxy_selector.get_selected_proxy_url()}{exe_url}"
            libs_url = f"{self.proxy_selector.get_selected_proxy_url()}{libs_url}"

        exe_filename = f"{self.latest_version}/OllamaSetup.exe"
        self.libs_filename = f"{self.latest_version}/ollama-windows-amd64.7z"

        if not os.path.exists(self.latest_version):
            os.makedirs(self.latest_version)

        try:
            self.status_label.config(text=f"Downloading {exe_filename}...")
            self.download_file(exe_url, exe_filename)
            self.status_label.config(text=f"Downloading {self.libs_filename}...")
            self.download_file(libs_url, self.libs_filename)
            self.status_label.config(text="Installing Ollama...")
            self.install_exe(exe_filename)
            self.status_label.config(text="Extracting and replacing libraries...")
            self.download_and_replace_rocblas()
        except Exception as e:
            logging.error(f"Installation failed: {e}")
            messagebox.showerror("Error", f"Installation failed: {e}")

    def download_file(self, url: str, filename: str):
        """Download file with progress tracking."""
        try:
            response = requests.get(url, stream=True)
            total_size = int(response.headers.get("content-length", 0))

            if total_size == 0:
                raise ValueError("Invalid file size")

            block_size = 1024
            written = 0
            start_time = time.time()

            with open(filename, "wb") as file, tqdm(
                total=total_size, unit="iB", unit_scale=True
            ) as progress_bar:
                for data in response.iter_content(block_size):
                    size = file.write(data)
                    written += size
                    progress_bar.update(size)
                    self.update_progress(written, total_size)
                    self.update_speed(written, start_time)

        except Exception as e:
            logging.error(f"Download failed: {e}")
            if os.path.exists(filename):
                os.remove(filename)
            raise

    def update_progress(self, current: int, total: int):
        """Update progress bar."""
        try:
            progress = int((current / total) * 100)
            self.progress["value"] = progress
            self.master.update_idletasks()
        except Exception as e:
            logging.error(f"Progress update failed: {e}")

    def update_speed(self, downloaded: int, start_time: float):
        """Update download speed display."""
        try:
            elapsed_time = time.time() - start_time
            if elapsed_time < 0.001:
                speed_text = "Calculating speed..."
            else:
                speed = downloaded / (1024 * elapsed_time)
                speed_text = f"Download Speed: {speed:.2f} KB/s"
            self.speed_label.config(text=speed_text)
            self.master.update_idletasks()
        except Exception as e:
            logging.error(f"Speed update failed: {e}")

    def install_exe(self, filename: str):
        """Install downloaded executable."""
        try:
            self.master.update_idletasks()
            subprocess.run([filename, "/SILENT"], check=True)
            self.status_label.config(text="OLLAMA installed successfully")
        except subprocess.SubprocessError as e:
            logging.error(f"Installation failed: {e}")
            raise

    def replace_only_btn_clicked(self):
        """Handle replace ROCm libraries button click."""
        self.latest_version = self.get_latest_release()
        self.libs_filename = f"{self.latest_version}/ollama-windows-amd64.7z"
        if not os.path.exists(self.latest_version):
            os.makedirs(self.latest_version)
        if not os.path.exists(self.libs_filename):
            libs_url = f"{self.base_url}/{self.latest_version}/ollama-windows-amd64.7z"
            if self.proxy_selector.get_selected_proxy_url():
                libs_url = f"{self.proxy_selector.get_selected_proxy_url()}{libs_url}"
            self.status_label.config(text=f"Downloading {self.libs_filename}...")
            self.download_file(libs_url, self.libs_filename)
        self.download_and_replace_rocblas()


    def download_and_replace_rocblas(self):
        """Download and replace ROCm libraries for selected GPU."""
        gpu_model = self.gpu_var.get()
        if not gpu_model:
            messagebox.showerror("Error", "Please select a GPU model first")
            return

        rocm_url = get_rocm_url(gpu_model)
        if not rocm_url:
            messagebox.showerror("Error", f"No ROCm file found for {gpu_model}")
            return

        if self.proxy_selector.get_selected_proxy_url():
            rocm_url = f"{self.proxy_selector.get_selected_proxy_url()}{rocm_url}"

        try:
            hip_rocblas_path = os.path.join("hip_rocblas", os.path.basename(rocm_url))
            os.makedirs(os.path.dirname(hip_rocblas_path), exist_ok=True)

            if not os.path.exists(hip_rocblas_path):
                self.status_label.config(text="Downloading ROCm libraries...")
                self.download_file(rocm_url, hip_rocblas_path)
            else:
                self.status_label.config(text="ROCm libraries already downloaded")

            self.status_label.config(text="Extracting and replacing libraries...")
            self.extract_and_replace_rocblas(hip_rocblas_path)

        except Exception as e:
            logging.error(f"ROCm library replacement failed: {e}")
            messagebox.showerror("Error", f"ROCm library replacement failed: {e}")

    def extract_and_replace_rocblas(self, zip_path: str):
        """Extract and replace ROCm libraries from zip file."""
        ollama_base_path = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama")
        ollama_path = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\lib\ollama")
        rocblas_dll_for_rocm_path = os.path.join(ollama_path, "rocm")
        library_path = os.path.join(rocblas_dll_for_rocm_path, "rocblas", "library")

        try:
            temp_dir = os.path.join(self.latest_version, "temp")
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)
            logging.info(f"Extracting to unzip directory: {temp_dir}")

            # Extract archive
            with py7zr.SevenZipFile(self.libs_filename, "r") as libs_ref:
                libs_to_ollama_path = os.path.join(temp_dir,"windows-amd64")
                self.status_label.config(text="Extracting ollama-windows-amd64...")
                libs_ref.extractall(path=temp_dir)

            with py7zr.SevenZipFile(zip_path, "r") as zip_ref:
                libs_to_rocm_path = os.path.join(temp_dir,"rocm")
                if not os.path.exists(libs_to_rocm_path):
                    os.makedirs(libs_to_rocm_path)
                self.status_label.config(text="Extracting ROCm libraries...")
                zip_ref.extractall(path=libs_to_rocm_path)

            # Verify required files
            lib_for_ollama_path = os.path.join(libs_to_ollama_path, "lib")

            rocblas_dll_for_rocm_tempfiles_path = os.path.join(libs_to_rocm_path, "rocblas.dll")
            library_for_rocm_tempfiles_path = os.path.join(libs_to_rocm_path, "library")

            if not os.path.exists(rocblas_dll_for_rocm_tempfiles_path):
                raise FileNotFoundError("rocblas.dll not found in archive")
            if not os.path.exists(library_for_rocm_tempfiles_path):
                raise FileNotFoundError("library folder not found in archive")

            # Copy files
            # Copy ollama-windows-amd64 to ollama base folder
            self.status_label.config(text="Copying ollama-windows-amd64...")
            logging.info("Copying ollama-windows-amd64")
            # Instead of using shutil.copytree directly, you could:
            if os.path.exists(os.path.join(ollama_base_path, "lib", "ollama", "rocm")):
                shutil.rmtree(os.path.join(ollama_base_path, "lib", "ollama", "rocm"))
            shutil.copytree(lib_for_ollama_path, os.path.join(ollama_base_path, "lib"), dirs_exist_ok=True)
            logging.info(f"Copied lib to {ollama_base_path}")

            # Copy rocblas.dll to rocm folder
            self.status_label.config(text="Copying rocblas.dll...")
            logging.info("Copying rocblas.dll")
            shutil.copy2(rocblas_dll_for_rocm_tempfiles_path, rocblas_dll_for_rocm_path)
            logging.info(f"Copied rocblas.dll to {rocblas_dll_for_rocm_path}")

            self.status_label.config(text="Copying library folder...")
            logging.info("Copying library folder")
            shutil.copytree(library_for_rocm_tempfiles_path, library_path, dirs_exist_ok=True)
            logging.info(f"Copied library folder to {library_path}")

            self.status_label.config(text="ROCm libraries updated successfully")
            self.status_label.config(
                text="Installation complete. Please restart Ollama for changes to take effect."
            )
            shutil.rmtree(temp_dir)

        except Exception as e:
            logging.error(f"Library extraction failed: {e}")
            self.status_label.config(text=f"Library extraction failed: {str(e)}")
            raise

    def fix_05Error(self):
        """Fix common 0xc0000005 error by copying libraries."""
        self.status_label.config(text="Fixing 0xc0000005 Error...")

        try:
            source_dir = os.path.expandvars(
                r"%LOCALAPPDATA%\Programs\Ollama\lib\ollama"
            )
            library_dir = os.path.expandvars(
                r"%LOCALAPPDATA%\Programs\Ollama\lib\ollama\rocblas\library"
            )
            destination_dir = os.path.expandvars(
                r"%LOCALAPPDATA%\Programs\Ollama\lib\ollama\runners\rocm_v6.1"
            )

            # Create destination directory if it doesn't exist
            os.makedirs(destination_dir, exist_ok=True)

            # Copy main directory files
            for filename in os.listdir(source_dir):
                source_file = os.path.join(source_dir, filename)
                if os.path.isfile(source_file):
                    shutil.copy2(source_file, destination_dir)
                    logging.info(f"Copied {filename} to runners directory")

            # Copy library files
            if os.path.exists(library_dir):
                library_path = os.path.join(destination_dir, "library")
                os.makedirs(library_path, exist_ok=True)

                for filename in os.listdir(library_dir):
                    library_file = os.path.join(library_dir, filename)
                    if os.path.isfile(library_file):
                        shutil.copy2(library_file, library_path)
                        logging.info(f"Copied library file {filename}")

            self.status_label.config(text="0xc0000005 Error fix applied successfully")

        except Exception as e:
            logging.error(f"Error fix failed: {e}")
            self.status_label.config(text=f"Error fix failed: {str(e)}")
            raise

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
    try:
        if not is_admin():
            if messagebox.askyesno(
                "Insufficient Permissions",
                "Administrator privileges are required.\nRestart as administrator?",
            ):
                restart_as_admin()
            sys.exit()

        root = tk.Tk()
        app = OllamaInstallerGUI(root)
        root.protocol("WM_DELETE_WINDOW", app.on_closing)
        root.mainloop()
    except Exception as e:
        logging.critical(f"Application failed to start: {e}", exc_info=True)
        messagebox.showerror(
            "Critical Error",
            f"Application failed to start: {e}\nCheck logs for details.",
        )


if __name__ == "__main__":
    main()
