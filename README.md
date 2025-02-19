# Ollama-For-AMD-Installer

## Overview
Special thanks to [likelovewant](https://github.com/likelovewant/) for creating the [ollama-for-amd library](https://github.com/likelovewant/ollama-for-amd). 

This project simplifies the installation process of likelovewant's library, making it easier for users to manage and update their AMD GPU-compatible Ollama installations.

## Features

- **Automated Version Management**: Checks and installs the latest version of Ollama for AMD
- **ROCm Library Management**: Updates ROCm libraries with GPU-specific optimizations
- **Error Resolution**: Includes fixes for common issues like the `0xc0000005` error
- **Proxy Support**: Optional proxy configuration for users with connection issues

## Prerequisites

- Python 3.10 or higher
- Required Python packages: `py7zr`, `tqdm`

## Screenshot
![Application Interface](./screenshot.png)

## Installation

### Option 1: Download Release
Download the latest release from the [releases page](https://github.com/ByronLeeeee/Ollama-For-AMD-Installer/releases).

### Option 2: Build from Source
1. Clone the repository:
   ```bash
   git clone https://github.com/ByronLeeeee/Ollama-For-AMD-Installer.git
   cd Ollama-For-AMD-Installer
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Running the Application

#### Using the Release Version
Run `Ollama-For-AMD-Installer.exe` with administrator privileges.

#### Using Source Code
```bash
python ollama_installer.py
```

### Using the Interface

1. **GPU Selection**
   - Select your AMD GPU model from the dropdown menu
   - This selection is used to ensure compatibility when replacing ROCm libraries
   - Different GPU models require different optimized libraries

2. **Installation Options**
   - **Check for New Version**: Updates to the latest Ollama for AMD release
   - **Replace ROCm Libraries**: Updates GPU-specific libraries based on your selected GPU model
   - **Fix 0xc0000005 Error**: Resolves a common runtime error

3. **Proxy Settings** (Optional)
   - By default, **No Proxy** is required for most users
   - If you experience connection issues, you can:
     - Select from predefined proxy servers
     - Add your custom proxy
     - Test proxy performance to find the fastest option
   - Available proxy options include (But some may not work, please test them first):
     - GHProxy
     - GitHub Mirror
     - FastGit
     - CF Worker
     - Custom proxy configurations

## Contributing

Contributions are welcome! Feel free to:
- Submit pull requests
- Report bugs
- Request new features
- Improve documentation

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Thanks to the contributors and maintainers of the libraries and tools used in this project

---

For support or questions, please open an issue on GitHub.