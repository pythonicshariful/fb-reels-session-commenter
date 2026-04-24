import json
import os
import pickle
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

# Import the core logic
import pklgenerator
import reel_comment

# Initialize CustomTkinter
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

CONFIG_FILE = "gui_config.json"

DEVICE_PRESETS = {
    "iPhone 12/13/14 (390x844)": (390, 844),
    "iPhone XR/11/12 Pro Max (414x896)": (414, 896),
    "Pixel 7 (412x915)": (412, 915),
    "Samsung Galaxy S20 (360x800)": (360, 800),
    "Large Mobile (480x1000)": (480, 1000),
    "Full Screen": "MAX",
    "Custom": None
}

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("FB Reels Auto-Commenter")
        self.geometry("750x950")

        # Layout configuration
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(7, weight=1)

        # Title
        self.label_title = ctk.CTkLabel(self, text="FB Reels Auto-Commenter", font=ctk.CTkFont(size=24, weight="bold"))
        self.label_title.grid(row=0, column=0, padx=20, pady=(20, 10))

        # PKL Directory
        self.frame_pkl = ctk.CTkFrame(self)
        self.frame_pkl.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.frame_pkl.grid_columnconfigure(0, weight=1)
        
        self.label_pkl = ctk.CTkLabel(self.frame_pkl, text="PKL Directory:")
        self.label_pkl.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="w")
        
        self.entry_pkl = ctk.CTkEntry(self.frame_pkl, placeholder_text="Select folder containing .pkl files")
        self.entry_pkl.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        
        self.btn_browse = ctk.CTkButton(self.frame_pkl, text="Browse", width=80, command=self.browse_pkl)
        self.btn_browse.grid(row=1, column=1, padx=5, pady=10)
        
        self.btn_generate = ctk.CTkButton(self.frame_pkl, text="Generate PKL", width=100, fg_color="green", hover_color="darkgreen", command=self.generate_pkl_start)
        self.btn_generate.grid(row=1, column=2, padx=5, pady=10)

        # (Reel URL field removed as per user request)

        # Comment Text
        self.label_comment = ctk.CTkLabel(self, text="Comment Text:")
        self.label_comment.grid(row=3, column=0, padx=30, pady=(10, 0), sticky="w")
        self.textbox_comment = ctk.CTkTextbox(self, height=80)
        self.textbox_comment.grid(row=3, column=0, padx=20, pady=(35, 10), sticky="ew")

        self.frame_settings = ctk.CTkFrame(self)
        self.frame_settings.grid(row=4, column=0, padx=20, pady=10, sticky="ew")
        self.frame_settings.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # Device Preset
        self.label_device = ctk.CTkLabel(self.frame_settings, text="Device Preset:")
        self.label_device.grid(row=0, column=0, padx=10, pady=(10, 0))
        self.option_device = ctk.CTkOptionMenu(self.frame_settings, values=list(DEVICE_PRESETS.keys()), command=self.on_device_change)
        self.option_device.grid(row=1, column=0, padx=10, pady=(0, 10))
        self.option_device.set("Large Mobile (480x1000)")

        # Width / Height
        self.label_width = ctk.CTkLabel(self.frame_settings, text="Width:")
        self.label_width.grid(row=0, column=1, padx=10, pady=(10, 0))
        self.entry_width = ctk.CTkEntry(self.frame_settings, width=60)
        self.entry_width.grid(row=1, column=1, padx=10, pady=(0, 10))
        self.entry_width.insert(0, "480")

        self.label_height = ctk.CTkLabel(self.frame_settings, text="Height:")
        self.label_height.grid(row=0, column=2, padx=10, pady=(10, 0))
        self.entry_height = ctk.CTkEntry(self.frame_settings, width=60)
        self.entry_height.grid(row=1, column=2, padx=10, pady=(0, 10))
        self.entry_height.insert(0, "1000")

        self.label_count = ctk.CTkLabel(self.frame_settings, text="Reels/Acc:")
        self.label_count.grid(row=0, column=3, padx=10, pady=(10, 0))
        self.entry_count = ctk.CTkEntry(self.frame_settings, width=60)
        self.entry_count.grid(row=1, column=3, padx=10, pady=(0, 10))
        self.entry_count.insert(0, "1")
        
        # New Row for Delays
        self.label_min_delay = ctk.CTkLabel(self.frame_settings, text="Min Delay (s):")
        self.label_min_delay.grid(row=2, column=1, padx=10, pady=(10, 0))
        self.entry_min_delay = ctk.CTkEntry(self.frame_settings, width=80)
        self.entry_min_delay.grid(row=3, column=1, padx=10, pady=(0, 10))
        self.entry_min_delay.insert(0, "2.0")

        self.label_max_delay = ctk.CTkLabel(self.frame_settings, text="Max Delay (s):")
        self.label_max_delay.grid(row=2, column=2, padx=10, pady=(10, 0))
        self.entry_max_delay = ctk.CTkEntry(self.frame_settings, width=80)
        self.entry_max_delay.grid(row=3, column=2, padx=10, pady=(0, 10))
        self.entry_max_delay.insert(0, "5.0")

        self.label_browsers = ctk.CTkLabel(self.frame_settings, text="Browsers:")
        self.label_browsers.grid(row=2, column=3, padx=10, pady=(10, 0))
        self.entry_browsers = ctk.CTkEntry(self.frame_settings, width=80)
        self.entry_browsers.grid(row=3, column=3, padx=10, pady=(0, 10))
        self.entry_browsers.insert(0, "1")

        # Buttons
        self.btn_run = ctk.CTkButton(self, text="START AUTOMATION", font=ctk.CTkFont(size=16, weight="bold"), height=50, command=self.start_automation)
        self.btn_run.grid(row=5, column=0, padx=20, pady=20, sticky="ew")

        # Log Display
        self.label_log = ctk.CTkLabel(self, text="Output Logs:")
        self.label_log.grid(row=6, column=0, padx=30, pady=(10, 0), sticky="w")
        self.log_text = ctk.CTkTextbox(self, font=ctk.CTkFont(family="Consolas", size=12))
        self.log_text.grid(row=7, column=0, padx=20, pady=(5, 20), sticky="nsew")

        # Load existing config
        self.load_config()

    def browse_pkl(self):
        directory = filedialog.askdirectory()
        if directory:
            self.entry_pkl.delete(0, tk.END)
            self.entry_pkl.insert(0, directory)

    def on_device_change(self, choice):
        size = DEVICE_PRESETS.get(choice)
        if size == "MAX":
            # Get screen width and height
            w = self.winfo_screenwidth()
            h = self.winfo_screenheight()
            self.entry_width.delete(0, tk.END)
            self.entry_width.insert(0, str(w))
            self.entry_height.delete(0, tk.END)
            self.entry_height.insert(0, str(h))
        elif size:
            self.entry_width.delete(0, tk.END)
            self.entry_width.insert(0, str(size[0]))
            self.entry_height.delete(0, tk.END)
            self.entry_height.insert(0, str(size[1]))

    def generate_pkl_start(self):
        directory = self.entry_pkl.get().strip()
        if not directory:
            directory = filedialog.askdirectory(title="Select folder to save PKL files")
            if not directory: return
            self.entry_pkl.delete(0, tk.END)
            self.entry_pkl.insert(0, directory)

        # Determine next filename
        base_name = "facebook_login_data"
        ext = ".pkl"
        filename = f"{base_name}{ext}"
        i = 2
        while os.path.exists(os.path.join(directory, filename)):
            filename = f"{base_name}{i}{ext}"
            i += 1
        
        target_path = os.path.join(directory, filename)
        
        self.log(f"Starting Session Generator: {filename}...")
        self.btn_generate.configure(state="disabled", text="Working...")
        
        thread = threading.Thread(target=self.run_generator, args=(target_path,))
        thread.daemon = True
        thread.start()

    def run_generator(self, target_path):
        from tkinter import messagebox
        
        try:
            major = pklgenerator._chrome_major_version()
            width, height, dpr, ua = pklgenerator._mobile_emulation_params(major)

            options = pklgenerator.uc.ChromeOptions()
            options.add_argument(f"--user-agent={ua}")
            options.add_argument(f"--window-size={width},{height}")

            driver_kwargs = {"options": options}
            if major is not None:
                driver_kwargs["version_main"] = major
            pklgenerator._prepare_undetected_chromedriver_cache()
            
            self.after(0, lambda: self.log("Opening Facebook Login... Please log in in the new window."))
            driver = pklgenerator.uc.Chrome(**driver_kwargs)
            pklgenerator._apply_mobile_emulation(driver, width, height, dpr, ua)

            try:
                driver.get("https://m.facebook.com/login")
                
                # Instead of input(), we use a messagebox to wait
                messagebox.showinfo("Login Required", "Please log in to Facebook in the browser window.\n\nOnce you are successfully logged in and on the home page, click OK here to save the session.")

                # Get cookies/storage
                cookies = driver.get_cookies()
                local_storage = driver.execute_script("return Object.assign({}, window.localStorage);")
                session_storage = driver.execute_script("return Object.assign({}, window.sessionStorage);")

                data = {
                    "url": driver.current_url,
                    "cookies": cookies,
                    "local_storage": local_storage,
                    "session_storage": session_storage,
                }

                with open(target_path, "wb") as f:
                    pickle.dump(data, f)
                
                self.after(0, lambda: self.log(f"SUCCESS: Session saved to {os.path.basename(target_path)}"))
            finally:
                driver.quit()
        except Exception as e:
            self.after(0, lambda: self.log(f"GENERATOR ERROR: {e}"))
        finally:
            self.after(0, lambda: self.btn_generate.configure(state="normal", text="Generate PKL"))

    def log(self, message):
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)

    def start_automation(self):
        # Gather inputs
        pkl_dir = self.entry_pkl.get().strip()
        reel_url = "https://www.facebook.com/reel/"  # Hardcoded as requested
        comment = self.textbox_comment.get("1.0", tk.END).strip()
        
        try:
            reel_count = int(self.entry_count.get().strip())
            min_delay = float(self.entry_min_delay.get().strip())
            max_delay = float(self.entry_max_delay.get().strip())
            width = int(self.entry_width.get().strip())
            height = int(self.entry_height.get().strip())
            num_browsers = int(self.entry_browsers.get().strip())
        except ValueError:
            self.log("ERROR: Please enter valid numbers.")
            return

        if not pkl_dir:
            self.log("ERROR: PKL Directory is required.")
            return
        if not comment:
            self.log("ERROR: Comment text is required.")
            return

        # Save config
        self.save_config()

        pkl_path = Path(pkl_dir)
        if not pkl_path.exists():
            self.log(f"Path does not exist: {pkl_path}")
            return

        all_pkl_files = reel_comment._discover_pkl_paths(pkl_path)
        if not all_pkl_files:
            self.log(f"No .pkl files found in {pkl_path}")
            return

        self.log(f"Distributing {len(all_pkl_files)} accounts across {num_browsers} browsers...")

        # Split pkl files among browsers
        chunks = [all_pkl_files[i::num_browsers] for i in range(num_browsers)]
        
        # Disable button
        self.btn_run.configure(state="disabled", text="RUNNING...")
        
        # Track finished threads
        self.finished_threads = 0
        self.total_threads = num_browsers

        # Start each browser chunk in its own thread
        for i, chunk in enumerate(chunks):
            if not chunk:
                self.finished_threads += 1
                continue
            
            thread = threading.Thread(
                target=self.run_process, 
                args=(i + 1, chunk, reel_url, comment, reel_count, min_delay, max_delay, width, height)
            )
            thread.daemon = True
            thread.start()

    def run_process(self, browser_id, pkl_files, reel_url, comment, reel_count, min_delay, max_delay, width, height):
        # Override reel_comment._log to point to our GUI log
        def custom_log(msg):
            self.after(0, lambda: self.log(f"[Browser {browser_id}] {msg}"))
        
        # We need a thread-local or instance-local way to switch logs, 
        # but since reel_comment._log is global, 
        # let's just make it prefix with browser ID
        
        try:
            reel_comment.run(
                pkl_paths=pkl_files,
                reel_url=reel_url,
                comment=comment,
                reel_count=reel_count,
                min_delay=min_delay,
                max_delay=max_delay,
                viewport_width=width,
                viewport_height=height,
                logger=custom_log
            )
            
            custom_log("Completed job.")
        except Exception as e:
            custom_log(f"CRITICAL ERROR: {e}")
        finally:
            self.after(0, self.check_all_finished)

    def check_all_finished(self):
        self.finished_threads += 1
        if self.finished_threads >= self.total_threads:
            self.btn_run.configure(state="normal", text="START AUTOMATION")
            self.log("All browsers have finished.")

    def save_config(self):
        config = {
            "pkl_dir": self.entry_pkl.get(),
            "reel_url": self.entry_url.get(),
            "comment": self.textbox_comment.get("1.0", tk.END).strip(),
            "reel_count": self.entry_count.get(),
            "min_delay": self.entry_min_delay.get(),
            "max_delay": self.entry_max_delay.get(),
            "browsers": self.entry_browsers.get(),
            "device": self.option_device.get(),
            "width": self.entry_width.get(),
            "height": self.entry_height.get()
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)
                self.entry_pkl.insert(0, config.get("pkl_dir", ""))
                self.entry_url.insert(0, config.get("reel_url", ""))
                self.textbox_comment.insert("1.0", config.get("comment", ""))
                
                self.entry_count.delete(0, tk.END)
                self.entry_count.insert(0, config.get("reel_count", "1"))
                
                self.entry_min_delay.delete(0, tk.END)
                self.entry_min_delay.insert(0, config.get("min_delay", "2.0"))
                
                self.entry_max_delay.delete(0, tk.END)
                self.entry_max_delay.insert(0, config.get("max_delay", "5.0"))

                self.entry_browsers.delete(0, tk.END)
                self.entry_browsers.insert(0, config.get("browsers", "1"))

                device = config.get("device", "Large Mobile (480x1000)")
                if device in DEVICE_PRESETS:
                    self.option_device.set(device)
                
                self.entry_width.delete(0, tk.END)
                self.entry_width.insert(0, config.get("width", "390"))
                self.entry_height.delete(0, tk.END)
                self.entry_height.insert(0, config.get("height", "1000"))
            except Exception:
                pass

if __name__ == "__main__":
    app = App()
    app.mainloop()
