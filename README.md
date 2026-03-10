# Ollama-For-AMD-Installer

## A Note from the Author
Thank you all for your incredible support! I am committed to maintaining this project to the best of my ability.

However, I have recently upgraded my primary desktop PC to an **NVIDIA RTX 5070 Ti** (It's awesome :D). This means I can no longer personally test the installer on a dedicated AMD graphics card. My development and testing will now rely on the official documentation from the [ollama-for-amd](https://github.com/likelovewant/ollama-for-amd) repository and my laptop, which runs a **Ryzen 6800H APU with 680M graphics (gfx1036)**. While this allows me to validate functionality for many APU users, I appreciate your understanding and welcome community feedback, especially for dGPU-related issues.

## Overview
This tool simplifies the installation and management of the community-driven [ollama-for-amd library](https://github.com/likelovewant/ollama-for-amd). It provides a user-friendly graphical interface to automate the complex process of injecting ROCm libraries into the official Ollama application, ensuring your AMD hardware works seamlessly.

![Ollama-For-AMD-Installer](./screenshot.png)

## Features

- **Automated Workflow**: Supports full installation (Official App + AMD Libraries) or simple library injection for existing setups.
- **Auto-Detection**: Built-in hardware scanner to identify your AMD GPU and automatically select the correct ROCm architecture profile.
- **Smart Downloader**: Handles complex network conditions, including automatic bypass for official downloads and robust error handling for corrupted packages.
- **Troubleshooting Tools**: 
    - One-click fix for the common `0xc0000005` runtime error.
    - Vulkan mode configuration utility.
- **Network Optimization**: Built-in proxy tester to verify and select the fastest connection mirror for GitHub downloads.
- **Modern Interface**: Clean, native-style GUI with real-time console logging for better visibility during installation.

## Installation

### Option 1: Download the Executable
The easiest way to get started is to download the latest `Ollama-For-AMD-Installer.exe` from the [**Releases Page**](https://github.com/ByronLeeeee/Ollama-For-AMD-Installer/releases).

### Option 2: Build from Source
1.  **Clone the repository:**
    ```bash
    git clone https://github.com/ByronLeeeee/Ollama-For-AMD-Installer.git
    cd Ollama-For-AMD-Installer
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```   
   *Prerequisites: Python 3.10+.*

## How to Use

1.  **Run as Administrator**: The application requires administrative privileges to replace system DLLs within the Ollama installation directory.
2.  **GPU Configuration**: 
    - Click **"Auto-Detect"** to have the app identify your AMD hardware, or choose manually from the dropdown list.
3.  **Choose an Action**:
    - **1. Full Install**: Downloads the official Ollama app and injects the necessary AMD libraries.
    - **2. Inject AMD Libs Only**: Use this if you have already installed the official Ollama app and just need to replace the ROCm files.
    - **3. Force Vulkan Mode**: A utility to enable Vulkan acceleration if your GPU is not detected via ROCm.
4.  **Network Setup**: If the download fails, use the "Proxy & Network Settings" section to test available mirrors and select a faster, more stable endpoint.

## Contributing
Contributions are always welcome! Please feel free to open an issue or submit a pull request to:
- Report bugs or suggest improvements.
- Request new features or library support.
- Enhance the documentation.

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.