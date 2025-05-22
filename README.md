# 🌐 DNS Cache Tool GUI 🚀

This is a Python-based DNS utility with a graphical user interface (GUI) built using Tkinter. It helps you discover domains, perform DNS queries, and test DNS performance to optimize your local DNS cache or analyze domain resolution. ✨

[Screenshot of Main Window]

## ✅ Features

-   **Intuitive GUI:** Easy-to-use interface for all operations.
-   **Domain Collection:**
    -   Recursively collect domains starting from an initial domain.
    -   Option to limit collection to subdomains only.
    -   Real-time progress display.
-   **DNS Querying:**
    -   Load domains from a file (JSON, CSV, TXT) and perform batch DNS queries.
    -   Import domain lists to add to your current collection and optionally query them.
-   **Data Management:**
    -   Save collected domains to JSON files.
    *   Export DNS query results to JSON or CSV formats.
-   **Advanced Parsing:** Extracts domains from HTML, and optionally from linked JavaScript, CSS, images, and meta tags.
-   **Performance Optimization:**
    -   Multi-threaded operations for domain collection and DNS querying.
    -   Configurable DNS query rate limiting to avoid overloading servers.
    -   Built-in Performance Tester to find optimal `QueriesPerSecond`, `MaxWorkers`, `Timeout`, and `BatchSize` settings for your environment.
    -   Apply recommended settings with a click.
-   **Configuration:**
    *   Edit application settings (target domain count, query parameters, crawler options) through a dedicated GUI dialog.
    *   Settings saved to `config.ini`.
-   **Standalone Executable:** Can be packaged into a single executable file for use on systems without a Python environment.

## 📥 Installation

### Method 1: Direct Download (Recommended for most users)

1.  Go to the [Releases](https://github.com/your-username/DNSCache/releases) page (replace `your-username/DNSCache` with the actual repository path).
2.  Download the latest version's executable (`.exe` for Windows) or the appropriate archive for your OS.
3.  Run the executable directly. No Python installation is required.

### Method 2: From Source

1.  **Prerequisites:**
    *   Python 3.7 or higher (Tkinter is usually included).
    *   Git (for cloning).
2.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/DNSCache.git # Replace with actual repo path
    cd DNSCache
    ```
3.  **Install dependencies:**
    (This tool primarily uses standard Python libraries. External libraries are listed in `requirements.txt`.)
    ```bash
    pip install -r requirements.txt
    ```
    *Note: `requirements.txt` includes `requests`, `beautifulsoup4`, and `dnspython`.*

## 🎮 GUI Usage

Run the application:

```bash
python gui.py
```

The main window is divided into several sections:

[Screenshot of Main Window with sections highlighted if possible]

1.  **Domain Collection:**
    *   **Start Domain:** Enter the initial domain (e.g., `example.com`).
    *   **Only collect subdomains:** Check this if you only want subdomains of the Start Domain.
    *   **Start Collection Button:** Begins the domain discovery process. Progress will be shown in the "Output & Logs" area and the status bar.

2.  **Domain File Operations:**
    *   **Load Domains & Start DNS Query Button:** Opens a file dialog to select a domain list file (JSON, CSV, TXT). After loading, it automatically starts batch DNS queries for the domains in that file.
    *   **Import Domain List Button:** Opens a file dialog to select a domain list. These domains are added to the current internal collection. You'll be asked if you want to perform DNS queries on the *entire* updated collection.

3.  **Actions/Export:**
    *   **Export DNS Query Results Button:** If DNS query results are available (e.g., after "Load Domains & Start DNS Query" or querying an imported list), this button allows you to save them. A file dialog will prompt for the save location and format (JSON or CSV).

4.  **Settings & Performance:**
    *   **Edit Configuration Button:** Opens a dialog to view and modify application settings (e.g., target domain count for collection, DNS query parameters, crawler options). Changes are saved to `config.ini` and applied to the current session.
        [Screenshot of Configuration Dialog]
    *   **Run Performance Test Button:** Opens a dialog to test DNS performance.
        *   You can choose the domain source for the test: current collected domains, a specific file, or default test domains.
        *   The test runs in the background, with live output in the dialog.
        *   Once complete, it displays recommended settings and allows you to apply them to your `config.ini`.
        [Screenshot of Performance Test Dialog]

5.  **Output & Logs:**
    *   This text area displays status messages, progress updates, error messages, and results from various operations.

6.  **Status Bar:**
    *   Shows brief messages about the current application status or ongoing operations.

## ⚙️ Command-Line Interface (CLI)

For advanced users or automation, a command-line interface is also available:

```bash
python dns_cache_tool.py
```

This will present a menu-driven interface with similar functionalities to the GUI. The `dns_cache_tool.py` script shares the same backend logic and `config.ini` file as `gui.py`.

## 🔧 Configuration File (`config.ini`)

The application uses a `config.ini` file to store settings. You can edit this file directly (if the application is closed) or use the "Edit Configuration" dialog in the GUI. Key sections include:

-   **General**: Target domain count for collection, data storage directory.
-   **DNS**: DNS query parameters (queries per second, max workers, timeout, batch size).
-   **Crawler**: Options for the web crawler (e.g., whether to parse JavaScript, CSS).
-   **Export**: Default export settings.

## 📦 Build Instructions

The project can be packaged into a standalone executable.

### GitHub Actions (Automated Build)

The repository includes a GitHub Actions workflow in `.github/workflows/build.yml`. This workflow automatically builds the application using **PyInstaller** for Windows when a new tag (e.g., `v1.1.0`) is pushed. The resulting executable and a zip bundle are uploaded as release artifacts.

### Manual Build (Local)

You can also build the executable manually on your local machine using PyInstaller.

1.  **Install Dependencies:**
    Ensure you have Python installed and have installed the project's basic dependencies from `requirements.txt`:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Install PyInstaller:**
    If you don't have PyInstaller installed, install it via pip:
    ```bash
    pip install pyinstaller
    ```

3.  **Run PyInstaller:**
    Navigate to the project's root directory in your terminal and run the following command to build `gui.py`:
    ```bash
    pyinstaller --onefile --windowed --icon=favicon.ico --name=DNSCacheGUI gui.py
    ```
    *   `--onefile`: Bundles everything into a single executable file.
    *   `--windowed`: Creates a windowed application (no command-line console appears when run). This is recommended for GUI applications.
    *   `--icon=favicon.ico`: Sets the application icon (make sure `favicon.ico` is in the project root or provide the correct path).
    *   `--name=DNSCacheGUI`: Specifies the name of the output executable.

    After the build process completes, you will find the executable (`DNSCacheGUI.exe` on Windows) inside a `dist` folder in your project directory. Other temporary build files will be in a `build` folder.

## ⚠️ Important Notes

-   **Data Directory:** The application creates a `data` directory in its working path to store collected domain files, exported results, and performance test results.
-   **Threading:** GUI operations that involve backend processing (like domain collection or batch DNS queries) are run in separate threads to keep the UI responsive.
-   **Rate Limiting:** DNS query rate limiting is active by default to prevent issues with DNS servers.

## 🙏 Acknowledgements

-   Tkinter for the GUI framework.
-   Nuitka for Python compilation.

---

Hope this tool is helpful! Feedback and contributions are welcome. 😊
