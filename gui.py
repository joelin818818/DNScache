import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import threading # MOD: 已添加 threading 导入
import os # MOD: 添加 os 模块导入，用于 os.path.basename
import time # MOD: 添加 time 模块导入，用于生成临时文件名
import json # MOD: 添加 json 模块导入，用于保存临时文件
import shutil # MOD: 添加 shutil 模块导入，用于复制文件

# MOD: 导入后端类
from dns_cache_tool import DNSCacheTool, Config, DNSRateLimiter # MOD: 已添加 DNSRateLimiter

class ConfigEditorDialog(tk.Toplevel):
    def __init__(self, parent, config_instance: Config, dns_tool_instance: DNSCacheTool):
        super().__init__(parent)
        self.transient(parent) # 设置为在主窗口之上
        self.grab_set()      # 设置为模态窗口

        self.title("编辑配置")
        self.parent = parent # 用于访问 App 类的方法，如 gui_message_callback
        self.config_instance = config_instance
        self.dns_tool_instance = dns_tool_instance
        self.entry_widgets = [] # 用于存储 (entry_widget, section, option_key) 的列表

        notebook = ttk.Notebook(self)
        
        sections = self.config_instance.config.sections()
        for section_key in sections:
            section_frame = ttk.Frame(notebook, padding="10")
            notebook.add(section_frame, text=self.config_instance.get_name(section_key)) # 使用get_name获取中文节名

            options = self.config_instance.config.options(section_key)
            for i, option_key in enumerate(options):
                option_name = self.config_instance.get_name(option_key) # 使用get_name获取中文选项名
                current_value = self.config_instance.get(section_key, option_key)
                
                ttk.Label(section_frame, text=f"{option_name}:").grid(row=i, column=0, padx=5, pady=5, sticky=tk.W)
                
                entry_var = tk.StringVar(value=current_value)
                entry = ttk.Entry(section_frame, textvariable=entry_var, width=50)
                entry.grid(row=i, column=1, padx=5, pady=5, sticky=tk.EW)
                
                self.entry_widgets.append((entry_var, section_key, option_key))
            section_frame.columnconfigure(1, weight=1) # 使输入框可扩展
            
        notebook.pack(expand=True, fill="both", padx=10, pady=10)

        # 按钮框架
        buttons_frame = ttk.Frame(self, padding="10")
        buttons_frame.pack(fill=tk.X)

        save_button = ttk.Button(buttons_frame, text="保存", command=self.save_configuration)
        save_button.pack(side=tk.RIGHT, padx=5)

        cancel_button = ttk.Button(buttons_frame, text="取消", command=self.destroy)
        cancel_button.pack(side=tk.RIGHT, padx=5)
        
        self.protocol("WM_DELETE_WINDOW", self.destroy) # 处理窗口关闭按钮
        self.geometry("600x400") # 根据需要调整大小

    def save_configuration(self):
        try:
            for entry_var, section, option in self.entry_widgets:
                new_value = entry_var.get()
                self.config_instance.set(section, option, new_value)
            
            success, message = self.config_instance.save_config()
            
            if success:
                # 使用新设置更新 DNSCacheTool 实例
                self.dns_tool_instance.target_count = self.config_instance.getint('General', 'TargetCount')
                # 使用新值重新初始化速率限制器
                self.dns_tool_instance.rate_limiter = DNSRateLimiter(
                    queries_per_second=self.config_instance.getint('DNS', 'QueriesPerSecond')
                )
                # DNSCacheTool 的 self.config 是同一个实例，因此它会自动看到其他直接 get 的更改。
                # 如果 DNSCacheTool 在其自己的属性中更广泛地缓存了配置值，请在此处更新它们。

                self.parent.gui_message_callback(f"配置已成功保存: {message}")
                self.parent.status_bar_text_var.set("配置已保存。")
            else:
                self.parent.gui_message_callback(f"保存配置时出错: {message}", is_error=True)
                messagebox.showerror("保存错误", f"无法保存配置:\n{message}", parent=self)
                return # 如果保存失败则不销毁窗口
        except Exception as e:
            self.parent.gui_message_callback(f"保存配置时发生异常: {e}", is_error=True)
            messagebox.showerror("保存错误", f"发生意外错误:\n{e}", parent=self)
            return # 不销毁窗口

        self.destroy()


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("DNS 缓存工具 GUI") 
        self.geometry("800x650") # 稍微增加高度以获得更好的布局

        # --- 变量 ---
        self.start_domain_var = tk.StringVar()
        self.only_subdomains_var = tk.BooleanVar()
        self.status_bar_text_var = tk.StringVar()
        self.status_bar_text_var.set("准备就绪。正在初始化后端...")

        # --- 初始化后端 ---
        # 注意: dns_cache_tool.py 中的 Config 类在其 __init__ 中加载其配置
        # 并且其 load_config/save_config 方法返回状态消息。
        # 这些消息目前尚未在此处捕获以供显示，但如果需要可以添加。
        self.config_instance = Config() 
        # 将 GUI 特定的回调传递给 DNSCacheTool
        self.dns_tool_instance = DNSCacheTool(
            progress_callback=self.gui_progress_callback,
            message_callback=self.gui_message_callback
        )
        self.status_bar_text_var.set("后端已初始化。准备就绪。")


        # --- 主布局 ---
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(expand=True, fill=tk.BOTH)

        # 创建左右窗格
        left_pane = ttk.Frame(main_frame, padding="5")
        left_pane.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))

        right_pane = ttk.Frame(main_frame, padding="5")
        right_pane.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH)
        
        # --- 左侧窗格控件 ---
        self._create_domain_collection_frame(left_pane)
        self._create_domain_file_ops_frame(left_pane)
        self._create_actions_export_frame(left_pane)
        self._create_settings_performance_frame(left_pane)

        # --- 右侧窗格控件 (显示区域) ---
        self._create_display_area_frame(right_pane)

        # --- 状态栏 (底部) ---
        self._create_status_bar()

    def _create_domain_collection_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="域名收集", padding="10")
        frame.pack(fill=tk.X, pady=5)

        ttk.Label(frame, text="起始域名:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.start_domain_entry = ttk.Entry(frame, textvariable=self.start_domain_var, width=30)
        self.start_domain_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)

        self.only_subdomains_check = ttk.Checkbutton(frame, text="仅收集子域名", variable=self.only_subdomains_var)
        self.only_subdomains_check.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W)

        self.collect_button = ttk.Button(frame, text="开始收集", command=self.start_collection_cb) 
        self.collect_button.grid(row=2, column=0, columnspan=2, padx=5, pady=10)
        
        frame.columnconfigure(1, weight=1) # 使输入框可扩展

    def _create_domain_file_ops_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="域名文件操作", padding="10")
        frame.pack(fill=tk.X, pady=5)

        self.load_query_button = ttk.Button(frame, text="加载域名并开始DNS查询", command=self.load_domains_for_query_cb) 
        self.load_query_button.pack(fill=tk.X, padx=5, pady=5)

        self.import_button = ttk.Button(frame, text="导入域名列表 (添加到集合)", command=self.import_domain_list_cb) 
        self.import_button.pack(fill=tk.X, padx=5, pady=5)

    def _create_actions_export_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="操作/导出", padding="10")
        frame.pack(fill=tk.X, pady=5)

        self.export_button = ttk.Button(frame, text="导出DNS查询结果", command=self.export_dns_results_cb) 
        self.export_button.pack(fill=tk.X, padx=5, pady=5)

    def _create_settings_performance_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="设置与性能", padding="10")
        frame.pack(fill=tk.X, pady=5)

        self.config_button = ttk.Button(frame, text="编辑配置", command=self.edit_configuration_cb) 
        self.config_button.pack(fill=tk.X, padx=5, pady=5)

        self.perf_test_button = ttk.Button(frame, text="运行性能测试", command=self.run_performance_test_cb) 
        self.perf_test_button.pack(fill=tk.X, padx=5, pady=5)

    def _create_display_area_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="输出与日志", padding="10")
        frame.pack(expand=True, fill=tk.BOTH)

        self.display_text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, height=10, width=50)
        self.display_text.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)
        self.display_text.configure(state='disabled') # 初始为只读

    def _create_status_bar(self):
        status_bar_frame = ttk.Frame(self, relief=tk.SUNKEN, padding=(2, 5))
        status_bar_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.status_bar_label = ttk.Label(status_bar_frame, textvariable=self.status_bar_text_var, anchor=tk.W)
        self.status_bar_label.pack(fill=tk.X)

    # --- 用于后端的GUI回调 ---
    def gui_progress_callback(self, message_prefix, current_count, *args):
        # DNSCacheTool process_domain 回调: (message, current_collected, target_count)
        # DNSCacheTool batch_query_dns 回调: (message_prefix, success_count, processed_count, total_domain_count)
        
        status_msg = ""
        display_msg = ""

        if "正在处理域名" in message_prefix: # 来自 collect_domains -> process_domain
            # message_prefix 在这里类似于 "正在处理域名: example.com"
            # current_count 是 len(self.collected_domains)
            # args[0] 是 self.target_count
            target_count = args[0] if args else "?"
            domain_being_processed = message_prefix.split(':')[-1].strip()
            status_msg = f"收集中: {domain_being_processed} ({current_count}/{target_count})"
            if current_count % 10 == 0 or current_count == target_count : # 定期更新显示区域
                 display_msg = f"已收集: {current_count} 个域名。当前: {domain_being_processed}"
        
        elif "DNS查询进度" in message_prefix: # 来自 batch_query_dns
            # message_prefix 是 "DNS查询进度: X%"
            # current_count 是 success_count
            # args[0] 是 processed_count, args[1] 是 total_domain_count
            processed_count = args[0] if args else "?"
            total_domains = args[1] if len(args) > 1 else "?"
            status_msg = f"{message_prefix} (成功:{current_count}/已处理:{processed_count}/总数:{total_domains})"
            if processed_count != "?" and (int(processed_count) % 50 == 0 or int(processed_count) == int(total_domains)):
                display_msg = status_msg
        else: # 通用消息
            status_msg = f"{message_prefix}: {current_count}"
            if args:
                status_msg += f" / {args[0]}"
                if len(args) > 1:
                    status_msg += f" (总计: {args[1]})"

        if status_msg:
            self.status_bar_text_var.set(status_msg)
        if display_msg:
            self.add_message_to_display(display_msg)

    def gui_message_callback(self, message, is_error=False):
        prefix = "[错误] " if is_error else "[信息] "
        self.add_message_to_display(prefix + message)
        # 同时更新状态栏以显示重要消息，例如错误或特定的信息
        if is_error:
            self.status_bar_text_var.set(f"错误: {message[:100]}") # 在状态栏中显示截断的错误信息
        elif "完成" in message or "已保存" in message : # 在状态栏中显示关键的成功消息
             self.status_bar_text_var.set(message)


    # --- 按钮回调 ---
    def start_collection_cb(self):
        start_domain = self.start_domain_var.get()
        if not start_domain:
            messagebox.showerror("错误", "起始域名不能为空。")
            return

        only_subdomains = self.only_subdomains_var.get()
        
        self.collect_button.config(state=tk.DISABLED)
        self.add_message_to_display(f"开始为 '{start_domain}' 收集域名 (仅子域名: {only_subdomains})...")
        self.status_bar_text_var.set(f"正在为 {start_domain} 收集域名...")

        def collection_task():
            try:
                # 后端 dns_tool_instance.collect_domains 将使用 gui_progress_callback 和 gui_message_callback
                collected_count, final_file_path = self.dns_tool_instance.collect_domains(start_domain, only_subdomains)
                
                # 这个最终消息在这里很有用，因为后端的 message_callback 可能没有完整的上下文
                success_msg = f"'{start_domain}' 的域名收集完成。收集到 {collected_count} 个域名。"
                if final_file_path:
                    success_msg += f" 已保存到: {final_file_path}"
                self.gui_message_callback(success_msg) # 使用我们的消息回调
                self.status_bar_text_var.set(f"{start_domain} 的收集完成。")

            except Exception as e:
                self.gui_message_callback(f"为 '{start_domain}' 收集域名时出错: {e}", is_error=True)
                self.status_bar_text_var.set("收集失败。")
            finally:
                # 确保按钮在主线程中重新启用
                self.after(0, lambda: self.collect_button.config(state=tk.NORMAL))

        # 在新线程中运行后端任务以保持GUI响应
        thread = threading.Thread(target=collection_task)
        thread.daemon = True # 允许主程序即使线程正在运行也能退出
        thread.start()

    def _disable_long_operation_buttons(self):
        self.collect_button.config(state=tk.DISABLED)
        self.load_query_button.config(state=tk.DISABLED)
        self.import_button.config(state=tk.DISABLED)
        # self.export_button.config(state=tk.DISABLED) # 导出通常很快
        self.perf_test_button.config(state=tk.DISABLED)

    def _enable_long_operation_buttons(self):
        self.collect_button.config(state=tk.NORMAL)
        self.load_query_button.config(state=tk.NORMAL)
        self.import_button.config(state=tk.NORMAL)
        # self.export_button.config(state=tk.NORMAL)
        self.perf_test_button.config(state=tk.NORMAL)

    def load_domains_for_query_cb(self):
        filepath = filedialog.askopenfilename(
            title="选择域名文件",
            filetypes=(("JSON 文件", "*.json"), ("文本文件", "*.txt"), ("CSV 文件", "*.csv"), ("所有文件", "*.*"))
        )
        if not filepath:
            self.status_bar_text_var.set("域名加载已取消。")
            return

        self.add_message_to_display(f"正在从以下位置加载域名: {filepath}")
        self.status_bar_text_var.set(f"正在从 {os.path.basename(filepath)} 加载域名...")
        
        # 后端 load_domains_from_file 使用 message_callback 来处理成功/失败
        loaded_domains = self.dns_tool_instance.load_domains_from_file(filepath) 
        # 后端中的 load_domains_from_file 现在也会设置 self.dns_tool_instance.collected_domains
        # 和 self.dns_tool_instance.current_source_file

        if not loaded_domains: # load_domains_from_file 在失败时返回空集合
            self.status_bar_text_var.set(f"从 {os.path.basename(filepath)} 加载域名失败。")
            # load_domains_from_file 内的消息回调应该已经提供了详细信息。
            return

        # 如果域名已加载，则在新线程中查询它们
        self.add_message_to_display(f"成功加载 {len(loaded_domains)} 个域名。开始DNS查询...")
        self.status_bar_text_var.set(f"正在查询 {len(loaded_domains)} 个域名...")
        self._disable_long_operation_buttons()

        def batch_query_task():
            try:
                # 后端 batch_query_dns 使用进度和消息回调
                # 此处传递 file_path 很重要，以便导出功能可以将其用于命名
                success_count, total_count, dns_results = self.dns_tool_instance.batch_query_dns(file_path=filepath) 
                
                # 完成后的最终消息
                msg = f"{os.path.basename(filepath)} 的批量DNS查询完成。成功: {success_count}/{total_count}。"
                self.gui_message_callback(msg) # 使用主消息回调
                self.status_bar_text_var.set(f"{os.path.basename(filepath)} 的查询完成。")
            except Exception as e:
                self.gui_message_callback(f"对 '{os.path.basename(filepath)}' 进行批量DNS查询时出错: {e}", is_error=True)
                self.status_bar_text_var.set("批量DNS查询失败。")
            finally:
                self.after(0, self._enable_long_operation_buttons)
        
        thread = threading.Thread(target=batch_query_task)
        thread.daemon = True
        thread.start()

    def import_domain_list_cb(self):
        filepath = filedialog.askopenfilename(
            title="选择要导入的域名文件",
            filetypes=(("JSON 文件", "*.json"), ("CSV 文件", "*.csv"), ("文本文件", "*.txt"), ("所有文件", "*.*"))
        )
        if not filepath:
            self.status_bar_text_var.set("域名导入已取消。")
            return

        self.add_message_to_display(f"正在从以下位置导入域名: {filepath}")
        self.status_bar_text_var.set(f"正在从 {os.path.basename(filepath)} 导入域名...")
        
        # 后端 load_domains_from_file 使用 message_callback 处理成功/失败消息
        # 并更新 self.dns_tool_instance.collected_domains
        imported_domains = self.dns_tool_instance.load_domains_from_file(filepath)

        if not imported_domains:
            # 错误消息应已由 load_domains_from_file 的回调显示
            self.status_bar_text_var.set(f"从 {os.path.basename(filepath)} 导入域名失败。")
            return
        
        # 成功导入的消息由 load_domains_from_file 的回调处理。
        self.status_bar_text_var.set(f"已导入 {len(imported_domains)} 个域名。准备就绪。")

        if messagebox.askyesno("查询 DNS", f"成功导入 {len(imported_domains)} 个域名。是否要对当前集合执行DNS查询?"):
            self.add_message_to_display(f"开始对所有 {len(self.dns_tool_instance.collected_domains)} 个收集到的域名进行DNS查询...")
            self.status_bar_text_var.set(f"正在查询 {len(self.dns_tool_instance.collected_domains)} 个域名...")
            self._disable_long_operation_buttons()

            def batch_query_task_for_import():
                try:
                    # 查询当前收集的域名 (包括新导入的域名)
                    # 传递 file_path=None 以指示查询 self.collected_domains
                    success_count, total_count, dns_results = self.dns_tool_instance.batch_query_dns(file_path=None) 
                    
                    msg = f"导入列表的批量DNS查询完成。成功: {success_count}/{total_count}。"
                    self.gui_message_callback(msg)
                    self.status_bar_text_var.set("导入列表的查询完成。")
                except Exception as e:
                    self.gui_message_callback(f"导入列表的批量DNS查询出错: {e}", is_error=True)
                    self.status_bar_text_var.set("导入列表的批量DNS查询失败。")
                finally:
                    self.after(0, self._enable_long_operation_buttons)
            
            thread = threading.Thread(target=batch_query_task_for_import)
            thread.daemon = True
            thread.start()

    def export_dns_results_cb(self):
        if not self.dns_tool_instance.dns_results:
            messagebox.showinfo("无结果", "没有可导出的DNS查询结果。请先运行查询。")
            self.status_bar_text_var.set("导出已取消：无结果。")
            return

        file_types = [("JSON 文件", "*.json"), ("CSV 文件", "*.csv")]
        # asksaveasfilename 返回所选文件的完整路径 (如果取消则为空字符串)
        # 如果用户未键入，则会自动附加所选文件类型的扩展名。
        export_filepath = filedialog.asksaveasfilename(
            title="导出DNS查询结果",
            defaultextension=".json", # 如果用户未指定且未选择类型，则为默认值
            filetypes=file_types
        )

        if not export_filepath:
            self.status_bar_text_var.set("导出已取消。")
            return

        # 从所选文件名扩展名确定格式
        chosen_format = ""
        if export_filepath.endswith(".json"):
            chosen_format = "json"
        elif export_filepath.endswith(".csv"):
            chosen_format = "csv"
        else:
            # 如果 defaultextension 和 filetypes 按预期工作，
            # 或者如果在此对话框之前我们强制选择，则理想情况下不应发生这种情况。
            messagebox.showerror("错误", "无法从文件名确定导出格式。请使用 .json 或 .csv 扩展名。")
            self.status_bar_text_var.set("导出失败：未知格式。")
            return
        
        self.add_message_to_display(f"正在将DNS结果导出为 {chosen_format.upper()} 到 {export_filepath}...")
        self.status_bar_text_var.set(f"正在导出为 {chosen_format.upper()}...")

        try:
            # 后端的 export_results 方法现在会生成自己的文件名，
            # 但GUI理想情况下应建议名称/路径。
            # 目前，我们将让后端命名它，但通知用户实际路径。
            # 假设此步骤中 export_results 将使用该格式。
            # 后端 `export_results` 返回它使用的实际路径。
            
            # 后端 `export_results` 已设计为在其 `data_dir` 中创建自己的带时间戳的文件名，
            # 我们只需要使用格式调用它。
            
            actual_saved_path = self.dns_tool_instance.export_results(format_type=chosen_format)

            if actual_saved_path:
                self.gui_message_callback(f"成功将DNS结果导出到: {actual_saved_path}")
                self.status_bar_text_var.set("导出成功。")
            else:
                # 错误消息应已由 export_results 内的回调显示
                self.gui_message_callback("导出失败。有关详细信息，请参见先前的消息。", is_error=True)
                self.status_bar_text_var.set("导出失败。")
        except Exception as e:
            self.gui_message_callback(f"导出期间出错: {e}", is_error=True)
            self.status_bar_text_var.set("导出错误。")


    def edit_configuration_cb(self):
        config_dialog = ConfigEditorDialog(self, self.config_instance, self.dns_tool_instance)
        self.wait_window(config_dialog) # 等待对话框关闭

    def run_performance_test_cb(self):
        perf_dialog = PerformanceTestDialog(self, self.config_instance, self.dns_tool_instance)
        self.wait_window(perf_dialog)


    # --- 辅助方法 ---
    def add_message_to_display(self, message):
        self.display_text.configure(state='normal') # 启用写入
        self.display_text.insert(tk.END, message + "\n")
        self.display_text.see(tk.END) # 滚动到底部
        self.display_text.configure(state='disabled') # 禁用写入

class PerformanceTestDialog(tk.Toplevel):
    def __init__(self, parent, config_instance: Config, dns_tool_instance: DNSCacheTool):
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()
        self.title("运行性能测试")
        self.parent = parent
        self.config_instance = config_instance
        self.dns_tool_instance = dns_tool_instance
        self.tester_instance = None # 将保存 DNSPerformanceTester 实例
        self.optimal_config_path = None # 用于存储 optimal_config.ini 的路径

        # --- 变量 ---
        self.domain_source_var = tk.StringVar(value="default")
        self.selected_file_path_var = tk.StringVar(value="未选择文件")
        
        # --- 布局 ---
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(expand=True, fill=tk.BOTH)

        # 域名来源框架
        source_frame = ttk.LabelFrame(main_frame, text="测试域名来源", padding="10")
        source_frame.pack(fill=tk.X, pady=5)

        self.rb_current = ttk.Radiobutton(source_frame, text="使用当前收集的域名", variable=self.domain_source_var, value="current")
        self.rb_current.pack(anchor=tk.W, padx=5)
        if not self.dns_tool_instance.collected_domains:
            self.rb_current.config(state=tk.DISABLED)

        self.rb_file = ttk.Radiobutton(source_frame, text="从文件加载域名:", variable=self.domain_source_var, value="file")
        self.rb_file.pack(anchor=tk.W, padx=5, pady=(5,0))
        
        file_input_frame = ttk.Frame(source_frame)
        file_input_frame.pack(fill=tk.X, padx=(25, 5)) # 在单选按钮下缩进
        self.browse_button = ttk.Button(file_input_frame, text="浏览...", command=self._browse_file_cb)
        self.browse_button.pack(side=tk.LEFT, padx=(0,5))
        self.selected_file_label = ttk.Label(file_input_frame, textvariable=self.selected_file_path_var, wraplength=350)
        self.selected_file_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.rb_default = ttk.Radiobutton(source_frame, text="使用默认测试域名 (内置)", variable=self.domain_source_var, value="default")
        self.rb_default.pack(anchor=tk.W, padx=5, pady=(0,5))

        # 显示区域
        display_frame = ttk.LabelFrame(main_frame, text="测试输出与结果", padding="10")
        display_frame.pack(expand=True, fill=tk.BOTH, pady=5)
        self.display_text = scrolledtext.ScrolledText(display_frame, wrap=tk.WORD, height=15)
        self.display_text.pack(expand=True, fill=tk.BOTH)
        self.display_text.configure(state='disabled')

        # 控制按钮框架
        controls_frame = ttk.Frame(main_frame, padding=(0, 10, 0, 0))
        controls_frame.pack(fill=tk.X)
        
        self.start_test_button = ttk.Button(controls_frame, text="开始测试", command=self._start_test_cb)
        self.start_test_button.pack(side=tk.LEFT, padx=5)

        self.apply_button = ttk.Button(controls_frame, text="应用推荐设置", command=self._apply_recommendations_cb, state=tk.DISABLED)
        self.apply_button.pack(side=tk.LEFT, padx=5)
        
        close_button = ttk.Button(controls_frame, text="关闭", command=self.destroy)
        close_button.pack(side=tk.RIGHT, padx=5)

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.geometry("700x550")
        self.resizable(True, True)

    def _add_test_output(self, message, is_error=False):
        # 确保GUI更新在主线程中完成
        def append_message():
            self.display_text.configure(state='normal')
            prefix = "[错误] " if is_error else ""
            self.display_text.insert(tk.END, prefix + message + "\n")
            self.display_text.see(tk.END)
            self.display_text.configure(state='disabled')
        self.after(0, append_message)

    def _browse_file_cb(self):
        filepath = filedialog.askopenfilename(
            title="选择性能测试的域名文件",
            filetypes=(("JSON 文件", "*.json"), ("文本文件", "*.txt"), ("CSV 文件", "*.csv"), ("所有文件", "*.*"))
        )
        if filepath:
            self.selected_file_path_var.set(filepath)
            self.domain_source_var.set("file") # 选择 'file' 单选按钮
        else:
            if not self.selected_file_path_var.get() or self.selected_file_path_var.get() == "未选择文件":
                 self.selected_file_path_var.set("未选择文件")
                 # 可选：如果没有为“文件”模式选择先前的文件，则恢复为默认值
                 # if self.domain_source_var.get() == "file":
                 # self.domain_source_var.set("default")


    def _toggle_controls_during_test(self, is_testing):
        state = tk.DISABLED if is_testing else tk.NORMAL
        self.start_test_button.config(state=state)
        self.rb_current.config(state=state if self.dns_tool_instance.collected_domains else tk.DISABLED)
        self.rb_file.config(state=state)
        self.browse_button.config(state=state)
        self.rb_default.config(state=state)
        # 应用按钮根据结果可用性单独处理

    def _start_test_cb(self):
        self._toggle_controls_during_test(True)
        self.apply_button.config(state=tk.DISABLED) # 在新测试开始时禁用应用按钮
        self.optimal_config_path = None # 重置先前的优化路径
        self.display_text.configure(state='normal')
        self.display_text.delete('1.0', tk.END) # 清除先前的输出
        self.display_text.configure(state='disabled')
        
        self._add_test_output("性能测试已开始...")
        self.parent.status_bar_text_var.set("性能测试正在运行...")

        test_domains_file_for_tester = None
        source_choice = self.domain_source_var.get()
        temp_file_to_delete = None

        try:
            if source_choice == "current":
                if not self.dns_tool_instance.collected_domains:
                    self._add_test_output("错误: 没有收集到可用于 'current' 来源的域名。", is_error=True)
                    self._toggle_controls_during_test(False)
                    return
                # 将当前域名保存到临时文件
                temp_dir = self.dns_tool_instance.data_dir # 使用现有的 data_dir
                if not os.path.exists(temp_dir): os.makedirs(temp_dir, exist_ok=True)
                temp_file_to_delete = os.path.join(temp_dir, f"temp_perf_test_domains_{int(time.time())}.json")
                with open(temp_file_to_delete, 'w', encoding='utf-8') as f:
                    json.dump(list(self.dns_tool_instance.collected_domains), f)
                test_domains_file_for_tester = temp_file_to_delete
                self._add_test_output(f"使用当前 {len(self.dns_tool_instance.collected_domains)} 个收集到的域名 (保存到临时文件: {temp_file_to_delete})。")
            
            elif source_choice == "file":
                selected_path = self.selected_file_path_var.get()
                if not selected_path or selected_path == "未选择文件" or not os.path.exists(selected_path):
                    self._add_test_output("错误: 'file' 来源选择的文件无效或未选择文件。", is_error=True)
                    self._toggle_controls_during_test(False)
                    return
                test_domains_file_for_tester = selected_path
                self._add_test_output(f"使用文件中的域名: {test_domains_file_for_tester}")
            
            elif source_choice == "default":
                test_domains_file_for_tester = None # DNSPerformanceTester 处理此情况
                self._add_test_output("使用来自 DNSPerformanceTester 的默认测试域名。")
            else:
                self._add_test_output("错误: 选择了未知的域名来源。", is_error=True)
                self._toggle_controls_during_test(False)
                return

            self.tester_instance = DNSPerformanceTester(
                test_domains_file=test_domains_file_for_tester,
                output_dir=os.path.join(self.dns_tool_instance.data_dir, "test_results"), # 将结果保存在 data_dir 的子文件夹中
                config=self.config_instance,
                output_callback=lambda msg, is_error=False: self._add_test_output(msg, is_error=is_error)
            )

            def _run_test_thread_target():
                results = None
                try:
                    results = self.tester_instance.run_tests()
                except Exception as e:
                    self._add_test_output(f"性能测试失败: {e}", is_error=True)
                    self.parent.status_bar_text_var.set("性能测试错误。")
                finally:
                    self._toggle_controls_during_test(False)
                    if results:
                        best_params, readable_results_path, opt_config_path = results
                        self.optimal_config_path = opt_config_path # 存储以供应用按钮使用
                        
                        recommend_text, _ = self.tester_instance.get_recommendations_text()
                        self._add_test_output("\n--- 建议 ---")
                        self._add_test_output(recommend_text)
                        self._add_test_output(f"\n详细的可读结果已保存到: {readable_results_path}")
                        self._add_test_output(f"优化配置文件已保存到: {opt_config_path}")
                        
                        self.apply_button.config(state=tk.NORMAL)
                        self.parent.status_bar_text_var.set("性能测试完成。建议可用。")
                    else:
                        self._add_test_output("性能测试未产生建议。", is_error=True)
                        self.parent.status_bar_text_var.set("性能测试完成 (无建议)。")
                    
                    if temp_file_to_delete and os.path.exists(temp_file_to_delete):
                        try:
                            os.remove(temp_file_to_delete)
                            self._add_test_output(f"已清理临时文件: {temp_file_to_delete}")
                        except Exception as e_del:
                            self._add_test_output(f"删除临时文件 {temp_file_to_delete} 时出错: {e_del}", is_error=True)
            
            thread = threading.Thread(target=_run_test_thread_target)
            thread.daemon = True
            thread.start()

        except Exception as e_setup: # 捕获线程开始前的设置错误
            self._add_test_output(f"设置性能测试时出错: {e_setup}", is_error=True)
            self._toggle_controls_during_test(False)
            self.parent.status_bar_text_var.set("性能测试设置错误。")
            if temp_file_to_delete and os.path.exists(temp_file_to_delete):
                try: os.remove(temp_file_to_delete)
                except: pass


    def _apply_recommendations_cb(self):
        if not self.optimal_config_path or not os.path.exists(self.optimal_config_path):
            messagebox.showerror("错误", "未找到优化配置文件或未运行测试。", parent=self)
            return

        try:
            # 将 optimal_config.ini 复制到主 config.ini
            main_config_file = self.config_instance.config_file # 例如 "config.ini"
            shutil.copy2(self.optimal_config_path, main_config_file)
            self._add_test_output(f"已将优化设置从 {self.optimal_config_path} 应用到 {main_config_file}。")
            
            # 在主Config实例中重新加载配置并更新DNSCacheTool
            success, message = self.config_instance.load_config()
            if success:
                self.dns_tool_instance.target_count = self.config_instance.getint('General', 'TargetCount')
                self.dns_tool_instance.rate_limiter = DNSRateLimiter(
                    queries_per_second=self.config_instance.getint('DNS', 'QueriesPerSecond')
                )
                # 通知主应用程序
                self.parent.gui_message_callback(f"配置已从 {main_config_file} 更新并重新加载。")
                self.parent.status_bar_text_var.set("已应用并重新加载新配置。")
                messagebox.showinfo("成功", "推荐设置已应用并保存。", parent=self)
            else:
                self.parent.gui_message_callback(f"重新加载新配置时出错: {message}", is_error=True)
                messagebox.showerror("错误", f"无法重新加载新配置: {message}", parent=self)

        except Exception as e:
            self.parent.gui_message_callback(f"应用推荐设置时出错: {e}", is_error=True)
            messagebox.showerror("错误", f"无法应用设置: {e}", parent=self)


if __name__ == "__main__":
    app = App()
    app.mainloop()
