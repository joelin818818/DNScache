# 🌐 DNS 缓存工具 GUI 🚀

这是一款基于 Python 的 DNS 实用工具，带有使用 Tkinter 构建的图形用户界面 (GUI)。它可以帮助您发现域名、执行 DNS 查询并测试 DNS 性能，以优化您的本地 DNS 缓存或分析域名解析。✨

[主窗口截图]

## ✅ 功能特性

-   **直观的 GUI:** 所有操作均配备易于使用的界面。
-   **域名收集:**
    -   从初始域名开始递归收集域名。
    -   可选择仅收集子域名。
    -   实时进度显示。
-   **DNS 查询:**
    -   从文件 (JSON, CSV, TXT) 加载域名并执行批量 DNS 查询。
    -   导入域名列表以添加到当前集合，并可选择对它们进行查询。
-   **数据管理:**
    -   将收集到的域名保存为 JSON 文件。
    *   将 DNS 查询结果导出为 JSON 或 CSV 格式。
-   **高级解析:** 从 HTML 中提取域名，并可选择从链接的 JavaScript、CSS、图片和 meta 标签中提取。
-   **性能优化:**
    -   域名收集和 DNS 查询的多线程操作。
    -   可配置的 DNS 查询速率限制，以避免服务器过载。
    -   内置性能测试器，为您的环境找到最佳的 `QueriesPerSecond` (每秒查询次数)、`MaxWorkers` (最大工作线程数)、`Timeout` (超时时间) 和 `BatchSize` (批处理大小) 设置。
    -   一键应用推荐设置。
-   **配置:**
    *   通过专用的 GUI 对话框编辑应用程序设置 (目标域名数量、查询参数、爬虫选项等)。
    *   设置保存到 `config.ini`。
-   **独立可执行文件:** 可以打包成单个可执行文件，在没有 Python 环境的系统上使用。

## 📥 安装

### 方法一：直接下载 (推荐大多数用户)

1.  前往 [Releases](https://github.com/your-username/DNSCache/releases) 页面 (请将 `your-username/DNSCache` 替换为实际的仓库路径)。
2.  下载最新版本的可执行文件 (`.exe` 适用于 Windows) 或适用于您操作系统的相应压缩包。
3.  直接运行可执行文件。无需安装 Python 环境。

### 方法二：从源码安装

1.  **先决条件:**
    *   Python 3.7 或更高版本 (通常已包含 Tkinter)。
    *   Git (用于克隆仓库)。
2.  **克隆仓库:**
    ```bash
    git clone https://github.com/your-username/DNSCache.git # 替换为实际的仓库路径
    cd DNSCache
    ```
3.  **安装依赖:**
    (此工具主要使用 Python 标准库。外部库在 `requirements.txt` 中列出。)
    ```bash
    pip install -r requirements.txt
    ```
    *注意: `requirements.txt` 包括 `requests`, `beautifulsoup4`, 和 `dnspython`。*

## 🎮 GUI 使用方法

运行应用程序:

```bash
python gui.py
```

主窗口分为几个部分:

[主窗口各部分高亮截图]

1.  **域名收集 (Domain Collection):**
    *   **起始域名 (Start Domain):** 输入初始域名 (例如: `example.com`)。
    *   **仅收集子域名 (Only collect subdomains):** 如果您只想收集起始域名的子域名，请勾选此项。
    *   **开始收集按钮 (Start Collection Button):** 开始域名发现过程。进度将显示在“输出与日志”区域和状态栏中。

2.  **域名文件操作 (Domain File Operations):**
    *   **加载域名并开始 DNS 查询按钮 (Load Domains & Start DNS Query Button):** 打开文件对话框以选择域名列表文件 (JSON, CSV, TXT)。加载后，它会自动开始对该文件中的域名进行批量 DNS 查询。
    *   **导入域名列表按钮 (Import Domain List Button):** 打开文件对话框以选择域名列表。这些域名将添加到当前的内部收集中。系统会询问您是否要对*整个*更新后的集合执行 DNS 查询。

3.  **操作/导出 (Actions/Export):**
    *   **导出 DNS 查询结果按钮 (Export DNS Query Results Button):** 如果有可用的 DNS 查询结果 (例如，在“加载域名并开始 DNS 查询”或查询导入列表之后)，此按钮允许您保存它们。文件对话框将提示您输入保存位置和格式 (JSON 或 CSV)。

4.  **设置与性能 (Settings & Performance):**
    *   **编辑配置按钮 (Edit Configuration Button):** 打开一个对话框以查看和修改应用程序设置 (例如，收集的目标域名数量、DNS 查询参数、爬虫选项)。更改将保存到 `config.ini` 并应用于当前会话。
        [配置对话框截图]
    *   **运行性能测试按钮 (Run Performance Test Button):** 打开一个对话框以测试 DNS 性能。
        *   您可以选择测试的域名来源：当前收集的域名、特定文件或默认测试域名。
        *   测试在后台运行，实时输出显示在对话框中。
        *   完成后，它会显示推荐的设置，并允许您将其应用于 `config.ini`。
        [性能测试对话框截图]

5.  **输出与日志 (Output & Logs):**
    *   此文本区域显示状态消息、进度更新、错误消息以及各种操作的结果。

6.  **状态栏 (Status Bar):**
    *   显示有关当前应用程序状态或正在进行的操作的简短消息。

## ⚙️ 命令行界面 (CLI)

对于高级用户或自动化需求，还提供了一个命令行界面:

```bash
python dns_cache_tool.py
```

这将呈现一个菜单驱动的界面，其功能与 GUI 类似。`dns_cache_tool.py` 脚本与 `gui.py` 共享相同的后端逻辑和 `config.ini` 文件。

## 🔧 配置文件 (`config.ini`)

应用程序使用 `config.ini` 文件存储设置。您可以直接编辑此文件 (如果应用程序已关闭) 或使用 GUI 中的“编辑配置”对话框。主要部分包括:

-   **General (常规)**: 收集的目标域名数量、数据存储目录。
-   **DNS (DNS查询)**: DNS 查询参数 (每秒查询次数、最大工作线程数、超时时间、批处理大小)。
-   **Crawler (爬虫)**: 网页爬虫的选项 (例如，是否解析 JavaScript、CSS)。
-   **Export (导出)**: 默认导出设置。

## 📦 构建说明

项目可以打包成一个独立的可执行文件。

### GitHub Actions (自动构建)

仓库中包含一个位于 `.github/workflows/build.yml` 的 GitHub Actions 工作流程。当推送新标签 (例如 `v1.1.0`) 时，此工作流程会自动使用 **PyInstaller** 为 Windows 构建应用程序。生成的可执行文件和 zip 压缩包将作为发布附件上传。

### 手动构建 (本地)

您也可以使用 PyInstaller 在本地手动构建可执行文件。

1.  **安装依赖:**
    确保您已安装 Python，并已从 `requirements.txt` 安装了项目的基础依赖：
    ```bash
    pip install -r requirements.txt
    ```

2.  **安装 PyInstaller:**
    如果您尚未安装 PyInstaller，请通过 pip 安装：
    ```bash
    pip install pyinstaller
    ```

3.  **运行 PyInstaller:**
    在终端中导航到项目的根目录，并运行以下命令来构建 `gui.py`：
    ```bash
    pyinstaller --onefile --windowed --icon=favicon.ico --name=DNSCacheGUI gui.py
    ```
    *   `--onefile`: 将所有内容打包到单个可执行文件中。
    *   `--windowed`: 创建一个窗口化应用程序 (运行时不出现命令行控制台)。推荐用于 GUI 应用程序。
    *   `--icon=favicon.ico`: 设置应用程序图标 (请确保 `favicon.ico` 文件位于项目根目录，或提供正确的路径)。
    *   `--name=DNSCacheGUI`: 指定输出可执行文件的名称。

    构建过程完成后，您将在项目目录下的 `dist` 文件夹中找到可执行文件 (`DNSCacheGUI.exe` on Windows)。其他临时构建文件将位于 `build` 文件夹中。

## ⚠️ 重要说明

-   **数据目录:** 应用程序会在其工作路径下创建一个名为 `data` 的目录，用于存储收集到的域名文件、导出的结果和性能测试结果。
-   **多线程:** 涉及后端处理的 GUI 操作 (如域名收集或批量 DNS 查询) 在单独的线程中运行，以保持 UI 响应。
-   **速率限制:**默认启用 DNS 查询速率限制，以防止 DNS 服务器出现问题。

## 🙏 致谢

-   Tkinter 提供 GUI 框架。
-   PyInstaller 提供 Python 编译打包。

---

希望这个工具对您有所帮助！欢迎反馈和贡献。😊
