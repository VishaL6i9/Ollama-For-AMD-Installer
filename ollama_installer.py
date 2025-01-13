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
from typing import Dict, List

# Set up logging
logging.basicConfig(filename='ollama_installer.log', level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')

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
    "gfx90c": "rocm.gfx90c.for.hip.sdk.6.1.2.7z"
}

BASE_URL = "https://github.com/likelovewant/ROCmLibs-for-gfx1103-AMD780M-APU/releases/download/v0.6.1.2/"


def get_rocm_url(gpu_model):
    if gpu_model in GPU_ROCM_MAPPING:
        return BASE_URL + GPU_ROCM_MAPPING[gpu_model]
    else:
        return None


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def restart_as_admin():
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    sys.exit()

class ProxySelector:
    DEFAULT_PROXIES = {
        "Default (No Proxy)": "",
        "GHProxy": "https://ghproxy.com/",
        "GitHub Mirror": "https://github.moeyy.xyz/",
        "FastGit": "https://raw.fastgit.org/",
        "CF Worker": "https://gh.api.99988866.xyz/"
    }
    
    def __init__(self, master, row: int = 1):
        self.master = master
        self.proxies: Dict[str, str] = self.load_proxies()
        self.selected_proxy = tk.StringVar()
        self.custom_proxy = tk.StringVar()
        self.ping_results: Dict[str, float] = {}
        
        self.create_widgets(row)
        
    def create_widgets(self, row: int):
        # Proxy selection frame
        proxy_frame = ttk.LabelFrame(self.master, text="Proxy Settings", padding=5)
        proxy_frame.grid(row=row, column=0, columnspan=2, pady=5, padx=10, sticky="ew")
        
        # Proxy dropdown
        ttk.Label(proxy_frame, text="Select Proxy:").grid(row=0, column=0, pady=5, padx=5, sticky="w")
        self.proxy_combo = ttk.Combobox(proxy_frame, textvariable=self.selected_proxy, width=30)
        self.update_proxy_list()
        self.proxy_combo.grid(row=0, column=1, columnspan=2, pady=5, padx=5, sticky="ew")
        
        # Custom proxy input
        ttk.Label(proxy_frame, text="Custom Proxy:").grid(row=1, column=0, pady=5, padx=5, sticky="w")
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
        self.result_text.grid(row=3, column=0, columnspan=3, pady=5, padx=5, sticky="ew")
        
    def load_proxies(self) -> Dict[str, str]:
        """Load proxies from config file or return defaults"""
        try:
            if os.path.exists('proxy_config.json'):
                with open('proxy_config.json', 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading proxy config: {e}")
        return self.DEFAULT_PROXIES.copy()
    
    def save_proxies(self):
        """Save current proxy list to config file"""
        try:
            with open('proxy_config.json', 'w') as f:
                json.dump(self.proxies, f, indent=2)
        except Exception as e:
            print(f"Error saving proxy config: {e}")
    
    def update_proxy_list(self):
        """Update the proxy dropdown list"""
        proxy_list = list(self.proxies.keys())
        self.proxy_combo['values'] = proxy_list
        if proxy_list:
            self.proxy_combo.set(proxy_list[0])
    
    def add_custom_proxy(self):
        """Add custom proxy to the list"""
        custom_url = self.custom_proxy.get().strip()
        if not custom_url:
            return
            
        if not custom_url.startswith(('http://', 'https://')):
            custom_url = 'https://' + custom_url
            
        if not custom_url.endswith('/'):
            custom_url += '/'
            
        # Add to proxy list
        proxy_name = f"Custom ({custom_url})"
        self.proxies[proxy_name] = custom_url
        self.save_proxies()
        self.update_proxy_list()
        self.proxy_combo.set(proxy_name)
        self.custom_proxy.set('')  # Clear entry
        
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
    def __init__(self, master):
        self.master = master
        master.title("Ollama For AMD Installer")
        master.geometry("450x500")  

        self.repo = "likelovewant/ollama-for-amd"
        self.base_url = f"https://github.com/{self.repo}/releases/download"
        self.rocm_url = "https://github.com/likelovewant/ROCmLibs-for-gfx1103-AMD780M-APU/releases/download/v0.6.1.2"

        self.gpu_var = tk.StringVar()       
        self.create_widgets()
        self.proxy_selector = ProxySelector(master, row=7) 
        
        self.load_settings()

    def create_widgets(self):
            # GPU Model selection
        gpu_frame = ttk.LabelFrame(self.master, text="GPU Settings", padding=5)
        gpu_frame.grid(row=0, column=0, columnspan=2, pady=5, padx=10, sticky="ew")
        
        ttk.Label(gpu_frame, text="GPU Model:").grid(row=0, column=0, pady=5, padx=5, sticky="w")
        self.gpu_combo = ttk.Combobox(gpu_frame, textvariable=self.gpu_var)
        self.gpu_combo['values'] = list(GPU_ROCM_MAPPING.keys())
        self.gpu_combo.grid(row=0, column=1, pady=5, padx=5, sticky="ew")

        self.check_button = ttk.Button(
            self.master, text="Check for New Version", command=self.check_version_thread)
        self.check_button.grid(row=2, column=0, columnspan=2, pady=10, padx=10, sticky="ew")

        self.replace_button = ttk.Button(
            self.master, text="Replace ROCm Libraries Only", command=self.download_and_replace_rocblas)
        self.replace_button.grid(row=3, column=0, pady=10, padx=10, sticky="ew")

        self.fix_button = ttk.Button(
            self.master, text="Fix 0xc0000005 Error", command=self.fix_05Error)
        self.fix_button.grid(row=3, column=1, columnspan=2, pady=10, padx=10, sticky="ew")

        self.progress = ttk.Progressbar(
            self.master, length=300, mode='determinate')
        self.progress.grid(row=4, column=0, columnspan=2, pady=10, padx=10, sticky="ew")

        self.speed_label = ttk.Label(self.master, text="Download Speed: 0 KB/s")
        self.speed_label.grid(row=5, column=0, columnspan=2, pady=5, padx=10, sticky="w")

        self.status_label = ttk.Label(self.master, text="")
        self.status_label.grid(row=6, column=0, columnspan=2, pady=5, padx=10, sticky="w")

    def get_url_with_proxy(self, url):
        proxy_url = self.proxy_selector.get_selected_proxy_url()
        return f"{proxy_url}{url}" if proxy_url else url


    def check_version_thread(self):
        threading.Thread(target=self.check_version, daemon=True).start()

    def check_version(self):
        try:
            self.status_label.config(text="Checking for new version...")
            latest_version = self.get_latest_release()
            if messagebox.askyesno("New Version", f"New version found: {latest_version}\nDo you want to download and install?"):
                self.download_and_install(latest_version)
        except requests.RequestException as e:
            logging.error(f"Network error: {e}")
            messagebox.showerror("Error", f"Network error: {e}")
        except Exception as e:
            logging.error(f"Unknown error: {e}")
            messagebox.showerror("Error", f"An unknown error occurred: {e}")

    def get_latest_release(self):
        url = f"https://cdn.jsdelivr.net/gh/{self.repo}/releases/latest"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()["tag_name"]

    def download_and_install(self, version):
        exe_url = self.get_url_with_proxy(
            f"{self.base_url}/{version}/OllamaSetup.exe")
        exe_filename = "OllamaSetup.exe"

        try:
            self.download_file(exe_url, exe_filename)
            self.install_exe(exe_filename)
            self.download_and_replace_rocblas()
        except Exception as e:
            logging.error(f"Error during download or installation: {e}")
            messagebox.showerror("Error", f"Error during download or installation: {e}")

    def download_file(self, url, filename):
        try:
            if not self.is_valid_url(url):
                raise ValueError("Invalid URL")
            
            response = requests.get(url, stream=True)
            total_size = int(response.headers.get('content-length', 0))

            if total_size == 0:
                print("File size is zero or unknown.")
                return
            
            block_size = 1024  # 1 KB
            written = 0
            start_time = time.time()

            with open(filename, 'wb') as file, tqdm(
                    desc=filename,
                    total=total_size,
                    unit='iB',
                    unit_scale=True,
                    unit_divisor=1024,
            ) as progress_bar:
                for data in response.iter_content(block_size):
                    size = file.write(data)
                    written += size
                    progress_bar.update(size)
                    self.update_progress(written, total_size)
                    self.update_speed(written, start_time)
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
        except Exception as e:
            print(f"An error occurred: {e}")
            if os.path.exists(filename):
                os.remove(filename)
    
    def is_valid_url(self, url):
        return bool(requests.utils.urlparse(url).netloc)

    def update_progress(self, current, total):
        if not (isinstance(current, (int, float)) and isinstance(total, (int, float))):
            raise ValueError("Both 'current' and 'total' must be numbers.")
        
        try:
            if total == 0:
                progress = 0
            else:
                progress = int((current / total) * 100)
            
            self.progress['value'] = progress
            self.master.update_idletasks()
        except Exception as e:
            print(f"An error occurred: {e}")

    def update_speed(self, downloaded, start_time):
        try:
            elapsed_time = time.time() - start_time
            if elapsed_time < 0.001:
                text = "Calculating speed..."
            else:
                speed = downloaded / (1024 * elapsed_time)
                text = f"Download Speed: {speed:.2f} KB/s"
            
            self.speed_label.config(text=text)
            self.master.update_idletasks()
        except Exception as e:
            print(f"Error updating speed: {e}")

    def install_exe(self, filename):
        self.status_label.config(text="Installing...")
        self.master.update_idletasks()
        subprocess.run([filename, "/SILENT"], check=True)
        self.status_label.config(text="OLLAMA For AMD installed")

    def download_and_replace_rocblas(self):
        gpu_model = self.gpu_var.get()
        rocm_url = get_rocm_url(gpu_model)
        if rocm_url:
            rocm_url = self.get_url_with_proxy(rocm_url)
            local_path = os.path.join("rocblas", os.path.basename(rocm_url))
            if not os.path.exists(local_path):
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                self.download_file(rocm_url, local_path)
            self.extract_and_replace_rocblas(local_path)
        else:
            messagebox.showerror("Error", f"No ROCm file found for {gpu_model}")

    def extract_and_replace_rocblas(self, zip_path: str):
        rocblas_path = os.path.expandvars(
            r'%LOCALAPPDATA%\Programs\Ollama\lib\ollama')
        library_path = os.path.join(rocblas_path, r'rocblas\library')

        try:
            # Create temporary directory
            with tempfile.TemporaryDirectory() as temp_dir:
                print(f"Extracting to temporary directory: {temp_dir}")

                # Extract to temporary directory
                with py7zr.SevenZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(path=temp_dir)

                # Check if rocblas.dll exists in the temporary directory
                rocblas_dll_path = os.path.join(temp_dir, 'rocblas.dll')
                if not os.path.exists(rocblas_dll_path):
                    raise FileNotFoundError("rocblas.dll file not found")

                # Check if library folder exists in the temporary directory
                temp_library_path = os.path.join(temp_dir, 'library')
                if not os.path.exists(temp_library_path):
                    raise FileNotFoundError("library folder not found")

                # Copy rocblas.dll to the target path
                shutil.copy(rocblas_dll_path, rocblas_path)
                print(f"Copied rocblas.dll to {rocblas_path}")

                # Copy library folder to the target path
                if os.path.exists(library_path):
                    shutil.rmtree(library_path)  # Delete existing library folder
                shutil.copytree(temp_library_path, library_path)  # Copy entire folder
                print(f"Copied library folder to {library_path}")

                self.status_label.config(text="ROCm libraries updated")

        except Exception as e:
            self.status_label.config(text=f"Extraction failed: {str(e)}")

    def fix_05Error(self):
        self.status_label.config(text="Fixing 0xc0000005 Error...")
        source_dir = os.path.expandvars(
            r'%LOCALAPPDATA%\Programs\Ollama\lib\ollama')
        library_dir = os.path.expandvars(
            r'%LOCALAPPDATA%\Programs\Ollama\lib\ollama\rocblas\library')
        destination_dir = os.path.expandvars(
            r'%LOCALAPPDATA%\Programs\Ollama\lib\ollama\runners\rocm_v6.1')

        try:
            # Traverse all files in the source directory
            for filename in os.listdir(source_dir):
                source_file = os.path.join(source_dir, filename)

                # Check if it is a file (not a folder)
                if os.path.isfile(source_file):
                    destination_file = os.path.join(destination_dir, filename)
                    shutil.copy2(source_file, destination_file)
            
            for filename in os.listdir(library_dir):
                library_file = os.path.join(library_dir, filename)

                # Check if it is a file (not a folder)
                if os.path.isfile(library_file):
                    library_path = os.path.join(destination_dir, 'library')
                    if not os.path.exists(library_path):
                        os.makedirs(library_path)
                    destination_file = os.path.join(library_path, filename)
                    shutil.copy2(library_file, destination_file)    

            self.status_label.config(text="Fix successful!")
        except Exception as e:
            self.status_label.config(text=f"File copy failed: {str(e)}")

    def load_settings(self):
        try:
            with open('settings.txt', 'r') as f:
                self.gpu_var.set(f.readline().strip())
                # Remove the proxy setting loading
        except FileNotFoundError:
            pass

    def save_settings(self):
        with open('settings.txt', 'w') as f:
            f.write(f"{self.gpu_var.get()}\n")

    def on_closing(self):
        self.save_settings()
        self.master.destroy()


if __name__ == "__main__":
    try:
        if not is_admin():
            if messagebox.askyesno("Insufficient Permissions", 
                "Administrator privileges are required to run this program.\nDo you want to restart as administrator?"):
                restart_as_admin()
            else:
                sys.exit()

        root = tk.Tk()
        app = OllamaInstallerGUI(root)
        root.protocol("WM_DELETE_WINDOW", app.on_closing)
        root.mainloop()
    except Exception as e:
        logging.error(f"Critical error: {str(e)}")
        messagebox.showerror("Error", f"Critical error occurred: {str(e)}")
