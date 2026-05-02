import customtkinter as ctk
import serial
import time
import pandas as pd
import matplotlib.pyplot as plt
import threading
from tkinter import filedialog, messagebox
from datetime import datetime

# Configure the modern dark theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class MilliPowerScopeApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("MilliPowerScope - ACS712 Analyzer")
        self.geometry("450x550")
        self.resizable(False, False)

        # Variables
        self.is_measuring = False
        self.serial_port = None

        self.create_widgets()

    def create_widgets(self):
        # Title
        self.title_label = ctk.CTkLabel(self, text="⚡ MilliPowerScope", font=("Roboto", 24, "bold"))
        self.title_label.pack(pady=(20, 30))

        # Port Input
        self.port_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.port_frame.pack(fill="x", padx=40, pady=5)
        ctk.CTkLabel(self.port_frame, text="COM Port:", width=120, anchor="w").pack(side="left")
        self.port_entry = ctk.CTkEntry(self.port_frame, width=150, placeholder_text="e.g., COM3")
        self.port_entry.pack(side="right")

        # Voltage Input
        self.volt_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.volt_frame.pack(fill="x", padx=40, pady=5)
        ctk.CTkLabel(self.volt_frame, text="Voltage (V):", width=120, anchor="w").pack(side="left")
        self.volt_entry = ctk.CTkEntry(self.volt_frame, width=150)
        self.volt_entry.insert(0, "5.0")
        self.volt_entry.pack(side="right")

        # Duration Input
        self.duration_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.duration_frame.pack(fill="x", padx=40, pady=5)
        ctk.CTkLabel(self.duration_frame, text="Duration (Sec):", width=120, anchor="w").pack(side="left")
        self.duration_entry = ctk.CTkEntry(self.duration_frame, width=150)
        self.duration_entry.insert(0, "120")
        self.duration_entry.pack(side="right")

        # Progress Bar
        self.progress_label = ctk.CTkLabel(self, text="Ready", font=("Roboto", 12))
        self.progress_label.pack(pady=(30, 5))
        self.progress_bar = ctk.CTkProgressBar(self, width=370)
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=5)

        # Start Button
        self.start_btn = ctk.CTkButton(self, text="▶ Start Measurement", height=40, fg_color="#28a745", hover_color="#218838", command=self.start_measurement)
        self.start_btn.pack(pady=(20, 10), fill="x", padx=40)

        # Plot from File Button
        self.plot_btn = ctk.CTkButton(self, text="📁 Plot from Existing File", height=40, fg_color="#444444", hover_color="#555555", command=self.plot_from_file)
        self.plot_btn.pack(pady=5, fill="x", padx=40)

    def start_measurement(self):
        if self.is_measuring:
            return

        try:
            self.voltage = float(self.volt_entry.get())
            self.duration = int(self.duration_entry.get())
            self.port = self.port_entry.get().strip()
            
            if not self.port:
                messagebox.showerror("Input Error", "Please enter a valid COM Port (e.g., COM3).")
                return
                
        except ValueError:
            messagebox.showerror("Input Error", "Please enter valid numeric values for Voltage and Duration.")
            return

        # Disable inputs during measurement
        self.start_btn.configure(state="disabled", text="Measuring...")
        self.plot_btn.configure(state="disabled")
        self.progress_bar.set(0)
        
        self.is_measuring = True
        
        # Start reading in a separate thread so UI doesn't freeze
        self.thread = threading.Thread(target=self.read_serial_data)
        self.thread.start()

    def read_serial_data(self):
        data_list = []
        start_time = time.time()

        try:
            ser = serial.Serial(self.port, 115200, timeout=1)
        except Exception as e:
            self.after(0, self.measurement_error, f"Could not connect to {self.port}.\nCheck connection or close Serial Monitor.")
            return

        self.after(0, lambda: self.progress_label.configure(text=f"Reading data from {self.port}..."))

        while (time.time() - start_time) < self.duration:
            try:
                if ser.in_waiting > 0:
                    line = ser.readline().decode('utf-8').strip()
                    if line:
                        current_ma = float(line)
                        elapsed_time = round(time.time() - start_time, 2)
                        
                        # Power (mW) = Voltage (V) * Current (mA)
                        power_mw = current_ma * self.voltage
                        
                        data_list.append({
                            "Time (s)": elapsed_time,
                            "Current (mA)": current_ma,
                            "Power (mW)": power_mw
                        })
                        
                # Update progress bar safely from thread
                progress = (time.time() - start_time) / self.duration
                self.after(0, lambda p=progress: self.progress_bar.set(p))
                
            except Exception:
                pass # Ignore corrupt serial data

        ser.close()
        
        # Ensure progress bar is full at the end
        self.after(0, lambda: self.progress_bar.set(1.0))
        self.after(0, self.measurement_complete, data_list)

    def measurement_error(self, error_msg):
        self.is_measuring = False
        self.start_btn.configure(state="normal", text="▶ Start Measurement")
        self.plot_btn.configure(state="normal")
        self.progress_label.configure(text="Error occurred!")
        self.progress_bar.set(0)
        messagebox.showerror("Connection Error", error_msg)

    def measurement_complete(self, data_list):
        self.is_measuring = False
        self.start_btn.configure(state="normal", text="▶ Start Measurement")
        self.plot_btn.configure(state="normal")
        self.progress_label.configure(text="Measurement Complete!")

        if not data_list:
            messagebox.showwarning("Warning", "No data was received during the time period.")
            return

        # Save to uniquely named Excel file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"measurement_{timestamp}.xlsx"
        
        df = pd.DataFrame(data_list)
        df.to_excel(filename, index=False)
        messagebox.showinfo("Success", f"Data saved successfully to:\n{filename}")
        
        # Plot automatically after measurement
        self.plot_data(df, f"Live Measurement ({filename})")

    def plot_from_file(self):
        # Open file dialog to select past Excel files
        filepath = filedialog.askopenfilename(
            title="Select Measurement File",
            filetypes=(("Excel files", "*.xlsx"), ("All files", "*.*"))
        )
        
        if filepath:
            try:
                df = pd.read_excel(filepath)
                # Quick validation to ensure it's our format
                if "Time (s)" not in df.columns or "Current (mA)" not in df.columns:
                    messagebox.showerror("Error", "The selected file does not contain the required data columns.")
                    return
                
                filename = filepath.split("/")[-1]
                self.plot_data(df, f"Historical Data ({filename})")
            except Exception as e:
                messagebox.showerror("Read Error", f"Could not read the file:\n{e}")

    def plot_data(self, df, title_info):
        # Create standard Matplotlib plots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), dpi=100)
        fig.canvas.manager.set_window_title('MilliPowerScope Viewer')

        # Top Plot: Current
        ax1.plot(df['Time (s)'], df['Current (mA)'], color='dodgerblue', linewidth=1.5, label='Current (mA)')
        ax1.set_title(f'{title_info} - Current vs. Time', fontweight='bold')
        ax1.set_xlabel('Time (Seconds)')
        ax1.set_ylabel('Current (mA)')
        ax1.grid(True, linestyle='--', alpha=0.7)
        ax1.legend(loc='upper right')
        
        # Bottom Plot: Power
        # Support old files that might have "Power (W)" instead of "Power (mW)"
        power_col = 'Power (mW)' if 'Power (mW)' in df.columns else 'Power (W)'
        line_color = 'crimson' if power_col == 'Power (mW)' else 'orange'

        ax2.plot(df['Time (s)'], df[power_col], color=line_color, linewidth=1.5, label=power_col)
        ax2.set_title(f'{title_info} - Power vs. Time', fontweight='bold')
        ax2.set_xlabel('Time (Seconds)')
        ax2.set_ylabel(power_col)
        ax2.grid(True, linestyle='--', alpha=0.7)
        ax2.legend(loc='upper right')
        
        plt.tight_layout()
        plt.show()

if __name__ == "__main__":
    app = MilliPowerScopeApp()
    app.mainloop()
