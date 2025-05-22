import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import threading # MOD: Added threading import

# MOD: Import backend classes
from dns_cache_tool import DNSCacheTool, Config, DNSRateLimiter # MOD: Added DNSRateLimiter

class ConfigEditorDialog(tk.Toplevel):
    def __init__(self, parent, config_instance: Config, dns_tool_instance: DNSCacheTool):
        super().__init__(parent)
        self.transient(parent) # Set to be on top of the main window
        self.grab_set()      # Make modal

        self.title("Edit Configuration")
        self.parent = parent # To access App's methods like gui_message_callback
        self.config_instance = config_instance
        self.dns_tool_instance = dns_tool_instance
        self.entry_widgets = [] # List to store (entry_widget, section, option_key)

        notebook = ttk.Notebook(self)
        
        sections = self.config_instance.config.sections()
        for section_key in sections:
            section_frame = ttk.Frame(notebook, padding="10")
            notebook.add(section_frame, text=self.config_instance.get_name(section_key))

            options = self.config_instance.config.options(section_key)
            for i, option_key in enumerate(options):
                option_name = self.config_instance.get_name(option_key)
                current_value = self.config_instance.get(section_key, option_key)
                
                ttk.Label(section_frame, text=f"{option_name}:").grid(row=i, column=0, padx=5, pady=5, sticky=tk.W)
                
                entry_var = tk.StringVar(value=current_value)
                entry = ttk.Entry(section_frame, textvariable=entry_var, width=50)
                entry.grid(row=i, column=1, padx=5, pady=5, sticky=tk.EW)
                
                self.entry_widgets.append((entry_var, section_key, option_key))
            section_frame.columnconfigure(1, weight=1)
            
        notebook.pack(expand=True, fill="both", padx=10, pady=10)

        # Buttons Frame
        buttons_frame = ttk.Frame(self, padding="10")
        buttons_frame.pack(fill=tk.X)

        save_button = ttk.Button(buttons_frame, text="Save", command=self.save_configuration)
        save_button.pack(side=tk.RIGHT, padx=5)

        cancel_button = ttk.Button(buttons_frame, text="Cancel", command=self.destroy)
        cancel_button.pack(side=tk.RIGHT, padx=5)
        
        self.protocol("WM_DELETE_WINDOW", self.destroy) # Handle window close button
        self.geometry("600x400") # Adjust size as needed

    def save_configuration(self):
        try:
            for entry_var, section, option in self.entry_widgets:
                new_value = entry_var.get()
                self.config_instance.set(section, option, new_value)
            
            success, message = self.config_instance.save_config()
            
            if success:
                # Update DNSCacheTool instance with new settings
                self.dns_tool_instance.target_count = self.config_instance.getint('General', 'TargetCount')
                # Re-initialize rate limiter with new value
                self.dns_tool_instance.rate_limiter = DNSRateLimiter(
                    queries_per_second=self.config_instance.getint('DNS', 'QueriesPerSecond')
                )
                # The DNSCacheTool's self.config is the same instance, so it sees changes automatically for other direct gets.
                # If DNSCacheTool cached config values in its own attributes more extensively, update them here.

                self.parent.gui_message_callback(f"Configuration saved successfully: {message}")
                self.parent.status_bar_text_var.set("Configuration saved.")
            else:
                self.parent.gui_message_callback(f"Error saving configuration: {message}", is_error=True)
                messagebox.showerror("Save Error", f"Could not save configuration:\n{message}", parent=self)
                return # Don't destroy if save failed
        except Exception as e:
            self.parent.gui_message_callback(f"Exception while saving configuration: {e}", is_error=True)
            messagebox.showerror("Save Error", f"An unexpected error occurred:\n{e}", parent=self)
            return # Don't destroy

        self.destroy()


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("DNS Cache Tool GUI") # MOD: Updated title slightly
        self.geometry("800x650") # MOD: Increased height for better layout

        # --- Variables ---
        self.start_domain_var = tk.StringVar()
        self.only_subdomains_var = tk.BooleanVar()
        self.status_bar_text_var = tk.StringVar()
        self.status_bar_text_var.set("Ready. Initialize backend...")

        # --- Initialize Backend ---
        # Note: The Config class from dns_cache_tool.py loads its config in its __init__
        # and its load_config/save_config methods return status messages.
        # These are not yet captured here for display, but can be if needed.
        self.config_instance = Config() 
        # Pass GUI-specific callbacks to DNSCacheTool
        self.dns_tool_instance = DNSCacheTool(
            progress_callback=self.gui_progress_callback,
            message_callback=self.gui_message_callback
        )
        self.status_bar_text_var.set("Backend initialized. Ready.")


        # --- Main Layout ---
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(expand=True, fill=tk.BOTH)

        # Create left and right panes
        left_pane = ttk.Frame(main_frame, padding="5")
        left_pane.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))

        right_pane = ttk.Frame(main_frame, padding="5")
        right_pane.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH)
        
        # --- Left Pane Widgets ---
        self._create_domain_collection_frame(left_pane)
        self._create_domain_file_ops_frame(left_pane)
        self._create_actions_export_frame(left_pane)
        self._create_settings_performance_frame(left_pane)

        # --- Right Pane Widgets (Display Area) ---
        self._create_display_area_frame(right_pane)

        # --- Status Bar (Bottom) ---
        self._create_status_bar()

    def _create_domain_collection_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="Domain Collection", padding="10")
        frame.pack(fill=tk.X, pady=5)

        ttk.Label(frame, text="Start Domain:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.start_domain_entry = ttk.Entry(frame, textvariable=self.start_domain_var, width=30)
        self.start_domain_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)

        self.only_subdomains_check = ttk.Checkbutton(frame, text="Only collect subdomains", variable=self.only_subdomains_var)
        self.only_subdomains_check.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W)

        self.collect_button = ttk.Button(frame, text="Start Collection", command=self.start_collection_cb) 
        self.collect_button.grid(row=2, column=0, columnspan=2, padx=5, pady=10)
        
        frame.columnconfigure(1, weight=1) # Make entry expandable

    def _create_domain_file_ops_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="Domain File Operations", padding="10")
        frame.pack(fill=tk.X, pady=5)

        self.load_query_button = ttk.Button(frame, text="Load Domains & Start DNS Query", command=self.load_domains_for_query_cb) # MOD: Store button reference
        self.load_query_button.pack(fill=tk.X, padx=5, pady=5)

        self.import_button = ttk.Button(frame, text="Import Domain List (Adds to Collection)", command=self.import_domain_list_cb) # MOD: Store button reference
        self.import_button.pack(fill=tk.X, padx=5, pady=5)

    def _create_actions_export_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="Actions/Export", padding="10")
        frame.pack(fill=tk.X, pady=5)

        self.export_button = ttk.Button(frame, text="Export DNS Query Results", command=self.export_dns_results_cb) # MOD: Store button reference
        self.export_button.pack(fill=tk.X, padx=5, pady=5)

    def _create_settings_performance_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="Settings & Performance", padding="10")
        frame.pack(fill=tk.X, pady=5)

        self.config_button = ttk.Button(frame, text="Edit Configuration", command=self.edit_configuration_cb) # MOD: Store button reference
        self.config_button.pack(fill=tk.X, padx=5, pady=5)

        self.perf_test_button = ttk.Button(frame, text="Run Performance Test", command=self.run_performance_test_cb) # MOD: Store button reference
        self.perf_test_button.pack(fill=tk.X, padx=5, pady=5)

    def _create_display_area_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="Output & Logs", padding="10")
        frame.pack(expand=True, fill=tk.BOTH)

        self.display_text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, height=10, width=50)
        self.display_text.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)
        self.display_text.configure(state='disabled') # Read-only initially

    def _create_status_bar(self):
        status_bar_frame = ttk.Frame(self, relief=tk.SUNKEN, padding=(2, 5))
        status_bar_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.status_bar_label = ttk.Label(status_bar_frame, textvariable=self.status_bar_text_var, anchor=tk.W)
        self.status_bar_label.pack(fill=tk.X)

    # --- Placeholder Callbacks ---
    # --- GUI Callbacks for Backend ---
    def gui_progress_callback(self, message_prefix, current_count, *args):
        # DNSCacheTool process_domain callback: (message, current_collected, target_count)
        # DNSCacheTool batch_query_dns callback: (message_prefix, success_count, processed_count, total_domain_count)
        
        status_msg = ""
        display_msg = ""

        if "正在处理域名" in message_prefix: # From collect_domains -> process_domain
            # message_prefix here is like "正在处理域名: example.com"
            # current_count is len(self.collected_domains)
            # args[0] is self.target_count
            target_count = args[0] if args else "?"
            domain_being_processed = message_prefix.split(':')[-1].strip()
            status_msg = f"Collecting: {domain_being_processed} ({current_count}/{target_count})"
            if current_count % 10 == 0 or current_count == target_count : # Update display area periodically
                 display_msg = f"Collected: {current_count} domains. Current: {domain_being_processed}"
        
        elif "DNS查询进度" in message_prefix: # From batch_query_dns
            # message_prefix is "DNS查询进度: X%"
            # current_count is success_count
            # args[0] is processed_count, args[1] is total_domain_count
            processed_count = args[0] if args else "?"
            total_domains = args[1] if len(args) > 1 else "?"
            status_msg = f"{message_prefix} (S:{current_count}/P:{processed_count}/T:{total_domains})"
            if processed_count != "?" and (int(processed_count) % 50 == 0 or int(processed_count) == int(total_domains)):
                display_msg = status_msg
        else: # Generic message
            status_msg = f"{message_prefix}: {current_count}"
            if args:
                status_msg += f" / {args[0]}"
                if len(args) > 1:
                    status_msg += f" (Total: {args[1]})"

        if status_msg:
            self.status_bar_text_var.set(status_msg)
        if display_msg:
            self.add_message_to_display(display_msg)

    def gui_message_callback(self, message, is_error=False):
        prefix = "[ERROR] " if is_error else "[INFO] "
        self.add_message_to_display(prefix + message)
        # Also update status bar for important messages, maybe just errors or specific infos
        if is_error:
            self.status_bar_text_var.set(f"Error: {message[:100]}") # Show truncated error in status
        elif "完成" in message or "已保存" in message : # Show key success messages in status bar
             self.status_bar_text_var.set(message)


    # --- Placeholder Callbacks ---
    def start_collection_cb(self):
        start_domain = self.start_domain_var.get()
        if not start_domain:
            messagebox.showerror("Error", "Start Domain cannot be empty.")
            return

        only_subdomains = self.only_subdomains_var.get()
        
        self.collect_button.config(state=tk.DISABLED)
        self.add_message_to_display(f"Starting domain collection for '{start_domain}' (Subdomains only: {only_subdomains})...")
        self.status_bar_text_var.set(f"Collecting domains for {start_domain}...")

        def collection_task():
            try:
                # The backend dns_tool_instance.collect_domains will use the gui_progress_callback and gui_message_callback
                collected_count, final_file_path = self.dns_tool_instance.collect_domains(start_domain, only_subdomains)
                
                # This final message is useful here as the backend's message_callback might not have full context
                success_msg = f"Domain collection finished for '{start_domain}'. Collected {collected_count} domains."
                if final_file_path:
                    success_msg += f" Saved to: {final_file_path}"
                self.gui_message_callback(success_msg) # Use our message callback
                self.status_bar_text_var.set(f"Collection complete for {start_domain}.")

            except Exception as e:
                self.gui_message_callback(f"Error during domain collection for '{start_domain}': {e}", is_error=True)
                self.status_bar_text_var.set("Collection failed.")
            finally:
                # Ensure button is re-enabled in the main thread
                self.after(0, lambda: self.collect_button.config(state=tk.NORMAL))

        # Run the backend task in a new thread to keep the GUI responsive
        thread = threading.Thread(target=collection_task)
        thread.daemon = True # Allows main program to exit even if threads are running
        thread.start()

    def _disable_long_operation_buttons(self):
        self.collect_button.config(state=tk.DISABLED)
        self.load_query_button.config(state=tk.DISABLED)
        self.import_button.config(state=tk.DISABLED)
        # self.export_button.config(state=tk.DISABLED) # Export is usually quick
        self.perf_test_button.config(state=tk.DISABLED)

    def _enable_long_operation_buttons(self):
        self.collect_button.config(state=tk.NORMAL)
        self.load_query_button.config(state=tk.NORMAL)
        self.import_button.config(state=tk.NORMAL)
        # self.export_button.config(state=tk.NORMAL)
        self.perf_test_button.config(state=tk.NORMAL)

    def load_domains_for_query_cb(self):
        filepath = filedialog.askopenfilename(
            title="Select Domain File",
            filetypes=(("JSON files", "*.json"), ("Text files", "*.txt"), ("CSV files", "*.csv"), ("All files", "*.*"))
        )
        if not filepath:
            self.status_bar_text_var.set("Domain loading cancelled.")
            return

        self.add_message_to_display(f"Loading domains from: {filepath}")
        self.status_bar_text_var.set(f"Loading domains from {os.path.basename(filepath)}...")
        
        # The backend load_domains_from_file uses message_callback for success/failure
        loaded_domains = self.dns_tool_instance.load_domains_from_file(filepath) 
        # load_domains_from_file in backend now also sets self.dns_tool_instance.collected_domains
        # and self.dns_tool_instance.current_source_file

        if not loaded_domains: # load_domains_from_file returns empty set on failure
            self.status_bar_text_var.set(f"Failed to load domains from {os.path.basename(filepath)}.")
            # Message callback within load_domains_from_file should have provided details.
            return

        # If domains are loaded, proceed to query them in a new thread
        self.add_message_to_display(f"Successfully loaded {len(loaded_domains)} domains. Starting DNS query...")
        self.status_bar_text_var.set(f"Querying {len(loaded_domains)} domains...")
        self._disable_long_operation_buttons()

        def batch_query_task():
            try:
                # Backend batch_query_dns uses progress and message callbacks
                # It's important that file_path is passed here so export can use it for naming
                success_count, total_count, dns_results = self.dns_tool_instance.batch_query_dns(file_path=filepath) 
                
                # Final message after completion
                msg = f"Batch DNS query complete for {os.path.basename(filepath)}. Successful: {success_count}/{total_count}."
                self.gui_message_callback(msg) # Use the main message callback
                self.status_bar_text_var.set(f"Query for {os.path.basename(filepath)} complete.")
            except Exception as e:
                self.gui_message_callback(f"Error during batch DNS query for '{os.path.basename(filepath)}': {e}", is_error=True)
                self.status_bar_text_var.set("Batch DNS query failed.")
            finally:
                self.after(0, self._enable_long_operation_buttons)
        
        thread = threading.Thread(target=batch_query_task)
        thread.daemon = True
        thread.start()

    def import_domain_list_cb(self):
        filepath = filedialog.askopenfilename(
            title="Select Domain File to Import",
            filetypes=(("JSON files", "*.json"), ("CSV files", "*.csv"), ("Text files", "*.txt"), ("All files", "*.*"))
        )
        if not filepath:
            self.status_bar_text_var.set("Domain import cancelled.")
            return

        self.add_message_to_display(f"Importing domains from: {filepath}")
        self.status_bar_text_var.set(f"Importing domains from {os.path.basename(filepath)}...")
        
        # The backend load_domains_from_file uses message_callback for success/failure messages
        # and updates self.dns_tool_instance.collected_domains
        imported_domains = self.dns_tool_instance.load_domains_from_file(filepath)

        if not imported_domains:
            # Error message would have been shown by the callback from load_domains_from_file
            self.status_bar_text_var.set(f"Failed to import domains from {os.path.basename(filepath)}.")
            return
        
        # Message for successful import is handled by load_domains_from_file's callback.
        # self.add_message_to_display(f"Successfully imported {len(imported_domains)} domains from {os.path.basename(filepath)}.")
        self.status_bar_text_var.set(f"Imported {len(imported_domains)} domains. Ready.")

        if messagebox.askyesno("Query DNS", f"Successfully imported {len(imported_domains)} domains. Do you want to perform DNS queries on the current collection?"):
            self.add_message_to_display(f"Starting DNS query for all {len(self.dns_tool_instance.collected_domains)} collected domains...")
            self.status_bar_text_var.set(f"Querying {len(self.dns_tool_instance.collected_domains)} domains...")
            self._disable_long_operation_buttons()

            def batch_query_task_for_import():
                try:
                    # Query currently collected domains (which includes the newly imported ones)
                    # Pass file_path=None to indicate querying self.collected_domains
                    success_count, total_count, dns_results = self.dns_tool_instance.batch_query_dns(file_path=None) 
                    
                    msg = f"Batch DNS query for imported list complete. Successful: {success_count}/{total_count}."
                    self.gui_message_callback(msg)
                    self.status_bar_text_var.set("Query for imported list complete.")
                except Exception as e:
                    self.gui_message_callback(f"Error during batch DNS query for imported list: {e}", is_error=True)
                    self.status_bar_text_var.set("Batch DNS query for imported list failed.")
                finally:
                    self.after(0, self._enable_long_operation_buttons)
            
            thread = threading.Thread(target=batch_query_task_for_import)
            thread.daemon = True
            thread.start()

    def export_dns_results_cb(self):
        message = "GUI: Export DNS Query Results clicked (Not fully implemented yet)"
        print(message) # Keep for now if not fully implemented
        if not self.dns_tool_instance.dns_results:
            messagebox.showinfo("No Results", "No DNS query results available to export. Please run a query first.")
            self.status_bar_text_var.set("Export cancelled: No results.")
            return

        file_types = [("JSON files", "*.json"), ("CSV files", "*.csv")]
        # asksaveasfilename returns the full path to the selected file (or empty string if cancelled)
        # The extension from the selected filetype is automatically appended if the user doesn't type it.
        export_filepath = filedialog.asksaveasfilename(
            title="Export DNS Query Results",
            defaultextension=".json", # Default if user doesn't specify and type is not selected
            filetypes=file_types
        )

        if not export_filepath:
            self.status_bar_text_var.set("Export cancelled.")
            return

        # Determine format from the chosen filename extension
        chosen_format = ""
        if export_filepath.endswith(".json"):
            chosen_format = "json"
        elif export_filepath.endswith(".csv"):
            chosen_format = "csv"
        else:
            # This case should ideally not happen if defaultextension and filetypes work as expected
            # or if we enforce a choice before this dialog.
            messagebox.showerror("Error", "Could not determine export format from filename. Please use .json or .csv extension.")
            self.status_bar_text_var.set("Export failed: Unknown format.")
            return
        
        self.add_message_to_display(f"Exporting DNS results as {chosen_format.upper()} to {export_filepath}...")
        self.status_bar_text_var.set(f"Exporting as {chosen_format.upper()}...")

        try:
            # The backend's export_results method now generates its own filename,
            # but the GUI should ideally suggest a name/path.
            # For now, we'll let the backend name it but inform the user of the actual path.
            # Let's assume for this step that export_results will use the format.
            # The backend `export_results` returns the actual path it used.
            
            # The backend `export_results` is already designed to create its own filename.
            # The GUI `export_filepath` is more of a suggestion for the *directory* and *base name* if the backend were to accept it.
            # Since the backend `export_results` creates its own timestamped filename in its `data_dir`,
            # we just need to call it with the format.
            
            actual_saved_path = self.dns_tool_instance.export_results(format_type=chosen_format)

            if actual_saved_path:
                self.gui_message_callback(f"Successfully exported DNS results to: {actual_saved_path}")
                self.status_bar_text_var.set("Export successful.")
            else:
                # Error message should have been displayed by the callback within export_results
                self.gui_message_callback("Export failed. See previous messages for details.", is_error=True)
                self.status_bar_text_var.set("Export failed.")
        except Exception as e:
            self.gui_message_callback(f"Error during export: {e}", is_error=True)
            self.status_bar_text_var.set("Export error.")


    def edit_configuration_cb(self):
        # message = "GUI: Edit Configuration clicked (Not implemented yet)"
        # print(message)
        # self.add_message_to_display(message)
        # self.status_bar_text_var.set("Edit Configuration window would open...")
        config_dialog = ConfigEditorDialog(self, self.config_instance, self.dns_tool_instance)
        self.wait_window(config_dialog) # Wait for the dialog to close

    def run_performance_test_cb(self):
        # message = "GUI: Run Performance Test clicked (Not implemented yet)"
        # print(message)
        # self.add_message_to_display(message)
        # self.status_bar_text_var.set("Performance test initiated...")
        perf_dialog = PerformanceTestDialog(self, self.config_instance, self.dns_tool_instance)
        self.wait_window(perf_dialog)


    # --- Helper Methods ---
    def add_message_to_display(self, message):
        self.display_text.configure(state='normal') # Enable writing
        self.display_text.insert(tk.END, message + "\n")
        self.display_text.see(tk.END) # Scroll to the end
        self.display_text.configure(state='disabled') # Disable writing

class PerformanceTestDialog(tk.Toplevel):
    def __init__(self, parent, config_instance: Config, dns_tool_instance: DNSCacheTool):
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()
        self.title("Run Performance Test")
        self.parent = parent
        self.config_instance = config_instance
        self.dns_tool_instance = dns_tool_instance
        self.tester_instance = None # Will hold the DNSPerformanceTester instance
        self.optimal_config_path = None # To store path of optimal_config.ini

        # --- Variables ---
        self.domain_source_var = tk.StringVar(value="default")
        self.selected_file_path_var = tk.StringVar(value="No file selected")
        
        # --- Layout ---
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(expand=True, fill=tk.BOTH)

        # Domain Source Frame
        source_frame = ttk.LabelFrame(main_frame, text="Test Domain Source", padding="10")
        source_frame.pack(fill=tk.X, pady=5)

        self.rb_current = ttk.Radiobutton(source_frame, text="Use current collected domains", variable=self.domain_source_var, value="current")
        self.rb_current.pack(anchor=tk.W, padx=5)
        if not self.dns_tool_instance.collected_domains:
            self.rb_current.config(state=tk.DISABLED)

        self.rb_file = ttk.Radiobutton(source_frame, text="Load domains from file:", variable=self.domain_source_var, value="file")
        self.rb_file.pack(anchor=tk.W, padx=5, pady=(5,0))
        
        file_input_frame = ttk.Frame(source_frame)
        file_input_frame.pack(fill=tk.X, padx=(25, 5)) # Indent under radio button
        self.browse_button = ttk.Button(file_input_frame, text="Browse...", command=self._browse_file_cb)
        self.browse_button.pack(side=tk.LEFT, padx=(0,5))
        self.selected_file_label = ttk.Label(file_input_frame, textvariable=self.selected_file_path_var, wraplength=350)
        self.selected_file_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.rb_default = ttk.Radiobutton(source_frame, text="Use default test domains (internal)", variable=self.domain_source_var, value="default")
        self.rb_default.pack(anchor=tk.W, padx=5, pady=(0,5))

        # Display Area
        display_frame = ttk.LabelFrame(main_frame, text="Test Output & Results", padding="10")
        display_frame.pack(expand=True, fill=tk.BOTH, pady=5)
        self.display_text = scrolledtext.ScrolledText(display_frame, wrap=tk.WORD, height=15)
        self.display_text.pack(expand=True, fill=tk.BOTH)
        self.display_text.configure(state='disabled')

        # Controls Frame
        controls_frame = ttk.Frame(main_frame, padding=(0, 10, 0, 0))
        controls_frame.pack(fill=tk.X)
        
        self.start_test_button = ttk.Button(controls_frame, text="Start Test", command=self._start_test_cb)
        self.start_test_button.pack(side=tk.LEFT, padx=5)

        self.apply_button = ttk.Button(controls_frame, text="Apply Recommended Settings", command=self._apply_recommendations_cb, state=tk.DISABLED)
        self.apply_button.pack(side=tk.LEFT, padx=5)
        
        close_button = ttk.Button(controls_frame, text="Close", command=self.destroy)
        close_button.pack(side=tk.RIGHT, padx=5)

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.geometry("700x550")
        self.resizable(True, True)

    def _add_test_output(self, message, is_error=False):
        # Ensures updates to GUI are done in the main thread
        def append_message():
            self.display_text.configure(state='normal')
            prefix = "[ERROR] " if is_error else ""
            self.display_text.insert(tk.END, prefix + message + "\n")
            self.display_text.see(tk.END)
            self.display_text.configure(state='disabled')
        self.after(0, append_message)

    def _browse_file_cb(self):
        filepath = filedialog.askopenfilename(
            title="Select Domain File for Performance Test",
            filetypes=(("JSON files", "*.json"), ("Text files", "*.txt"), ("CSV files", "*.csv"), ("All files", "*.*"))
        )
        if filepath:
            self.selected_file_path_var.set(filepath)
            self.domain_source_var.set("file") # Select the 'file' radio button
        else:
            if not self.selected_file_path_var.get() or self.selected_file_path_var.get() == "No file selected":
                 self.selected_file_path_var.set("No file selected")
                 # Optionally, revert to default if no file was previously selected for "file" mode
                 # if self.domain_source_var.get() == "file":
                 # self.domain_source_var.set("default")


    def _toggle_controls_during_test(self, is_testing):
        state = tk.DISABLED if is_testing else tk.NORMAL
        self.start_test_button.config(state=state)
        self.rb_current.config(state=state if self.dns_tool_instance.collected_domains else tk.DISABLED)
        self.rb_file.config(state=state)
        self.browse_button.config(state=state)
        self.rb_default.config(state=state)
        # Apply button is handled separately based on results availability

    def _start_test_cb(self):
        self._toggle_controls_during_test(True)
        self.apply_button.config(state=tk.DISABLED) # Disable apply button at start of new test
        self.optimal_config_path = None # Reset previous optimal path
        self.display_text.configure(state='normal')
        self.display_text.delete('1.0', tk.END) # Clear previous output
        self.display_text.configure(state='disabled')
        
        self._add_test_output("Performance test started...")
        self.parent.status_bar_text_var.set("Performance test running...")

        test_domains_file_for_tester = None
        source_choice = self.domain_source_var.get()
        temp_file_to_delete = None

        try:
            if source_choice == "current":
                if not self.dns_tool_instance.collected_domains:
                    self._add_test_output("Error: No domains collected to use for 'current' source.", is_error=True)
                    self._toggle_controls_during_test(False)
                    return
                # Save current domains to a temporary file
                temp_dir = self.dns_tool_instance.data_dir # Use existing data_dir
                if not os.path.exists(temp_dir): os.makedirs(temp_dir, exist_ok=True)
                temp_file_to_delete = os.path.join(temp_dir, f"temp_perf_test_domains_{int(time.time())}.json")
                with open(temp_file_to_delete, 'w', encoding='utf-8') as f:
                    json.dump(list(self.dns_tool_instance.collected_domains), f)
                test_domains_file_for_tester = temp_file_to_delete
                self._add_test_output(f"Using current {len(self.dns_tool_instance.collected_domains)} collected domains (saved to temp file: {temp_file_to_delete}).")
            
            elif source_choice == "file":
                selected_path = self.selected_file_path_var.get()
                if not selected_path or selected_path == "No file selected" or not os.path.exists(selected_path):
                    self._add_test_output("Error: Invalid or no file selected for 'file' source.", is_error=True)
                    self._toggle_controls_during_test(False)
                    return
                test_domains_file_for_tester = selected_path
                self._add_test_output(f"Using domains from file: {test_domains_file_for_tester}")
            
            elif source_choice == "default":
                test_domains_file_for_tester = None # DNSPerformanceTester handles this
                self._add_test_output("Using default test domains from DNSPerformanceTester.")
            else:
                self._add_test_output("Error: Unknown domain source selected.", is_error=True)
                self._toggle_controls_during_test(False)
                return

            self.tester_instance = DNSPerformanceTester(
                test_domains_file=test_domains_file_for_tester,
                output_dir=os.path.join(self.dns_tool_instance.data_dir, "test_results"), # Save results in a subfolder of data_dir
                config=self.config_instance,
                output_callback=lambda msg, is_error=False: self._add_test_output(msg, is_error=is_error)
            )

            def _run_test_thread_target():
                results = None
                try:
                    results = self.tester_instance.run_tests()
                except Exception as e:
                    self._add_test_output(f"Performance test failed: {e}", is_error=True)
                    self.parent.status_bar_text_var.set("Performance test error.")
                finally:
                    self._toggle_controls_during_test(False)
                    if results:
                        best_params, readable_results_path, opt_config_path = results
                        self.optimal_config_path = opt_config_path # Store for apply button
                        
                        recommend_text, _ = self.tester_instance.get_recommendations_text()
                        self._add_test_output("\n--- Recommendations ---")
                        self._add_test_output(recommend_text)
                        self._add_test_output(f"\nDetailed readable results saved to: {readable_results_path}")
                        self._add_test_output(f"Optimal config file saved to: {opt_config_path}")
                        
                        self.apply_button.config(state=tk.NORMAL)
                        self.parent.status_bar_text_var.set("Performance test complete. Recommendations available.")
                    else:
                        self._add_test_output("Performance test did not produce recommendations.", is_error=True)
                        self.parent.status_bar_text_var.set("Performance test complete (no recommendations).")
                    
                    if temp_file_to_delete and os.path.exists(temp_file_to_delete):
                        try:
                            os.remove(temp_file_to_delete)
                            self._add_test_output(f"Cleaned up temporary file: {temp_file_to_delete}")
                        except Exception as e_del:
                            self._add_test_output(f"Error deleting temporary file {temp_file_to_delete}: {e_del}", is_error=True)
            
            thread = threading.Thread(target=_run_test_thread_target)
            thread.daemon = True
            thread.start()

        except Exception as e_setup: # Catch errors in setup before thread starts
            self._add_test_output(f"Error setting up performance test: {e_setup}", is_error=True)
            self._toggle_controls_during_test(False)
            self.parent.status_bar_text_var.set("Performance test setup error.")
            if temp_file_to_delete and os.path.exists(temp_file_to_delete):
                try: os.remove(temp_file_to_delete)
                except: pass


    def _apply_recommendations_cb(self):
        if not self.optimal_config_path or not os.path.exists(self.optimal_config_path):
            messagebox.showerror("Error", "Optimal configuration file not found or test not run.", parent=self)
            return

        try:
            # Copy optimal_config.ini to main config.ini
            main_config_file = self.config_instance.config_file # e.g., "config.ini"
            shutil.copy2(self.optimal_config_path, main_config_file)
            self._add_test_output(f"Applied optimal settings from {self.optimal_config_path} to {main_config_file}.")
            
            # Reload config in main Config instance and update DNSCacheTool
            success, message = self.config_instance.load_config()
            if success:
                self.dns_tool_instance.target_count = self.config_instance.getint('General', 'TargetCount')
                self.dns_tool_instance.rate_limiter = DNSRateLimiter(
                    queries_per_second=self.config_instance.getint('DNS', 'QueriesPerSecond')
                )
                # Notify main app
                self.parent.gui_message_callback(f"Configuration updated and reloaded from {main_config_file}.")
                self.parent.status_bar_text_var.set("Applied and reloaded new configuration.")
                messagebox.showinfo("Success", "Recommended settings applied and saved.", parent=self)
            else:
                self.parent.gui_message_callback(f"Error reloading new configuration: {message}", is_error=True)
                messagebox.showerror("Error", f"Failed to reload new configuration: {message}", parent=self)

        except Exception as e:
            self.parent.gui_message_callback(f"Error applying recommended settings: {e}", is_error=True)
            messagebox.showerror("Error", f"Failed to apply settings: {e}", parent=self)


if __name__ == "__main__":
    app = App()
    app.mainloop()
