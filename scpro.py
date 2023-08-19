import asyncio
import re
import threading
import time
import tkinter as tk
from ctypes import byref, c_int, sizeof, windll
from ipaddress import IPv4Network
from tkinter import messagebox, ttk

import customtkinter as ctk
from ttkthemes import ThemedStyle

from core import cyl_async_ping, cyl_async_ssh, cyl_async_telnet, cyl_util
from scanner import scanner


class popupWindow(object):
    def __init__(self, master, title="popupWindow"):
        self.exit_result = False
        self.popup=tk.Toplevel(master)
        self.popup.attributes("-topmost", 1)
        self.popup.title(title)
        self.popup.protocol("WM_DELETE_WINDOW", self.on_popup_close)

    def initial_position(self, master):
        ## Popup position
        master_x = master.winfo_x()
        master_y = master.winfo_y()
        master_width = master.winfo_width()
        master_height = master.winfo_height()
        popup_width = self.popup.winfo_width()
        popup_height = self.popup.winfo_height()

        popup_x = master_x + (master_width - popup_width) // 2
        popup_y = master_y + (master_height - popup_height) // 2
        self.popup.geometry(f"+{popup_x}+{popup_y}")

    def create_input_field(self, label_text, var, row, column):
        label = ttk.Label(self.popup, text=label_text)
        label.grid(row=row, column=column, padx=5, pady=5, sticky="e")

        entry = ttk.Entry(self.popup, textvariable=var)
        entry.grid(row=row, column=column+1, padx=5, pady=5, sticky="w")

    def save_and_exit(self):
        self.exit_result = True
        self.popup.destroy()

    def on_popup_close(self):
        self.exit_result = False
        self.popup.destroy()


class popupWindow_Configure(popupWindow):
    def __init__(self, master, ssh_password, os_connection_mode):

        super().__init__(master, "Configure")

        self.ssh_password = ssh_password
        self.os_connection_mode = os_connection_mode
        self.os_connection_mode_var = tk.StringVar(value=self.os_connection_mode)

        ## Create UI
        self.create_ui()

        ## Popup position
        self.initial_position(master)

    def create_ui(self):
        connection_mode_label = ttk.Label(self.popup, text="OS Connection mode:")
        connection_mode_ssh = ttk.Radiobutton(self.popup, text="SSH",
                                              variable=self.os_connection_mode_var,
                                              value="SSH",
                                              command=self.toggle_password_entry)

        connection_mode_telnet = ttk.Radiobutton(self.popup,
                                                 text="Telnet",
                                                 variable=self.os_connection_mode_var,
                                                 value="Telnet",
                                                 command=self.toggle_password_entry)

        # Passwd entry
        self.password_label = ttk.Label(self.popup, text="Password:")
        self.password_entry = ttk.Entry(self.popup, width=30)

        # Button
        save_button = ttk.Button(self.popup, text="Save",
                                 command=self.save_configuration)

        # Arrange
        connection_mode_label.grid( row=0, column=0, padx=5,  pady=5, sticky="w")
        connection_mode_telnet.grid(row=1, column=0, padx=20, pady=5, sticky="w")
        connection_mode_ssh.grid(row=2, column=0, padx=20, pady=5,  sticky="w")
        self.password_label.grid(row=3, column=0, padx=5,  pady=5,  sticky="e")
        self.password_entry.grid(row=3, column=1, padx=5,  pady=5,  sticky="w", columnspan=3)
        save_button.grid(        row=4, column=3, padx=5,  pady=10, sticky="e")


    def toggle_password_entry(self):
        if self.os_connection_mode_var.get() == "SSH":
            self.password_label.grid(row=3, column=0, padx=5, pady=5, sticky="e")
            self.password_entry.grid(row=3, column=1, columnspan=3, padx=5, pady=5, sticky="w")
        else:
            self.password_label.grid_remove()
            self.password_entry.grid_remove()

    def save_configuration(self):
        self.os_connection_mode = self.os_connection_mode_var.get()
        if self.os_connection_mode_var.get() == "SSH":
            if self.password_entry.get():
                self.ssh_password = self.password_entry.get()

        self.save_and_exit()


class popupWindow_Ping(popupWindow):
    def __init__(self, master, ping_config: dict):
        super().__init__(master, "Ping Parameters")

        self.ping_config = ping_config
        
        self.schedule = tk.DoubleVar(value=ping_config["schedule_sec"])
        self.packet_count = tk.DoubleVar(value=ping_config["packet_count"])
        self.interval = tk.DoubleVar(value=ping_config["interval"])
        self.timeout = tk.DoubleVar(value=ping_config["timeout"])

        ## Create UI
        self.create_ui()

        ## Popup position
        self.initial_position(master)

    def create_ui(self):
        self.create_input_field("The schedule in second:", self.schedule, 0, 0)
        self.create_input_field("The number of packet:", self.packet_count, 1, 0)
        self.create_input_field("The interval (sec) between sending each packet:", self.interval, 2, 0)
        self.create_input_field("The timeout (sec) for waiting a reply:", self.timeout, 3, 0)

        submit_button = ttk.Button(self.popup, text="Submit", command=self.save_configuration)
        submit_button.grid(row=4, column=0, columnspan=2, padx=5, pady=5)

    def save_configuration(self):
        self.ping_config = {"schedule_sec": self.schedule.get(),
                            "packet_count": int(self.packet_count.get()),
                            "interval": self.interval.get(),
                            "timeout": self.timeout.get()}

        self.save_and_exit()


class popupWindow_SCP(popupWindow):
    def __init__(self, master, scp_config: dict):
        super().__init__(master, "SCP Setting")
        self.scp_config = scp_config
        
        self.storage_folder = tk.StringVar(value=scp_config["storage_folder"])
        self.config_name = tk.StringVar(value=scp_config["config_name"])

        ## Create UI
        self.create_ui()

        ## Popup position
        self.initial_position(master)

    def create_ui(self):
        self.create_input_field("Storage Folder:", self.storage_folder, 0, 0)
        self.create_input_field("Config Name:", self.config_name, 1, 0)

        submit_button = ttk.Button(self.popup, text="Submit", command=self.save_configuration)
        submit_button.grid(row=2, column=0, columnspan=2, padx=5, pady=5)

    def save_configuration(self):
        self.scp_config = {"storage_folder": self.storage_folder.get(),
                            "config_name": self.config_name.get()}

        self.save_and_exit()


class popupWindow_Add_scan_item(popupWindow):
    def __init__(self, master):
        super().__init__(master, "Add scan item")
        
        self.new_item_value = ()

        self.ip = tk.StringVar()
        self.mac = tk.StringVar()
        self.model = tk.StringVar()

        ## Create UI
        self.create_ui()

        ## Popup position
        self.initial_position(master)

    def create_ui(self):
        self.create_input_field("IP:", self.ip, 0, 0)
        self.create_input_field("MAC:", self.mac, 1, 0)
        self.create_input_field("Model:", self.model, 2, 0)

        submit_button = ttk.Button(self.popup, text="Submit", command=self.save_configuration)
        submit_button.grid(row=3, column=0, columnspan=2, padx=5, pady=5)

    def save_configuration(self):
        if not cyl_util.is_valid_IP(self.ip.get()):
            messagebox.showerror("Error", "Invalid IP !", parent=self.popup)
            return

        if self.mac.get() and not cyl_util.is_valid_MAC(self.mac):
            messagebox.showerror("Error", "Invalid MAC !", parent=self.popup)
            return

        self.new_item_value = (self.ip.get(), self.mac.get(), self.model.get(), 0)

        self.save_and_exit()

class popupWindow_LGW_Cmd(popupWindow):
    def __init__(self, master, action="Add", initialvalue=""):
        super().__init__(master, f"{action} LGW Cmd")

        self.lgw_cmd_list = []
        if action == "Edit":
            self.lgw_cmd_list = [initialvalue]

        self.action = action
        ## Create UI
        self.create_ui()

        ## Popup position
        self.initial_position(master)

    def create_ui(self):
        label = ttk.Label(self.popup, text="Enter LGW Cmd:")
        label.pack(padx=5, pady=5)

        if self.action == "Add":
            self.text = tk.Text(self.popup,
                                wrap="word",
                                background="White",
                                height=10,
                                width=70,
                                font=("Helvetica", 12))
            self.text.pack(padx=5, pady=5, fill="both", expand=True)
        elif self.action == "Edit":
            self.entry = ttk.Entry(self.popup, width=70)
            self.entry.insert(tk.END, self.lgw_cmd_list[0])
            self.entry.pack(padx=5, pady=5)

        submit_button = ttk.Button(self.popup, text=f"{self.action}", command=self.save_configuration)
        submit_button.pack(padx=5, pady=5)

    def save_configuration(self):
        if self.action == "Add":
            self.lgw_cmd_list = str(self.text.get("1.0", "end-1c")).splitlines()
            self.lgw_cmd_list = [cmd.strip() for cmd in self.lgw_cmd_list if cmd.strip()]

        elif self.action == "Edit":
            self.lgw_cmd_list = [str(self.entry.get()).strip()]

        error_cmds = [cmd for cmd in self.lgw_cmd_list if not cyl_util.is_lgw_cmd_format(cmd)]
        if error_cmds:
            error_cmds_msg = "\n".join(error_cmds)
            messagebox.showerror("Error", f"Invalid LGW cmd:\n{error_cmds_msg}", parent=self.popup)
            return
        self.save_and_exit()


class MyApp(ctk.CTk):
# class MyApp(tk.Tk):
    CANNOT_DISABLE_WIDGET = ('Frame',
                            'Menu',
                            'TLable',
                            'TFrame',
                            'Treeview',
                            'Labelframe',
                            'TProgressbar',
                            'TLabelframe')

    def __init__(self, theme="breeze"):
        super().__init__()

        ## for OS connection
        self.ssh_password = "root"
        self.OS_connection_mode = "SSH"

        ## for SCP
        self.scp_config = {"storage_folder": "storage", "config_name": ""}

        ## for OS cmd
        self.default_OS_cmd_timeout_sec = 10
        self.default_LGW_cmd_timeout_sec = 15

        ## Lock
        self.text_output_lock = threading.Lock()
        self.scan_treeview_lock = threading.Lock()
        self.ping_btn_lock = threading.Lock()

        ## for Ping
        self.is_pinging = False
        self.ping_thread = None
        self.ping_config = {"packet_count": 3, "schedule_sec": 1, "interval": 0.2, "timeout": 1}
        self.ping_counter = 0
        self.ping_items = []

        self.initUI(theme=theme)
        

    def initUI(self, theme):
        self.title("SCPro")
        ## Size
        width = self.winfo_screenwidth()
        height = self.winfo_screenheight()
        height = int(height*0.9)
        width = int(width//3)

        self.geometry(f"{width}x{height}+1+1")
        # self.resizable(False, False)

        ## Keep it top.
        # self.attributes("-topmost", 1)

        ## Style
        self.style = ThemedStyle()

        # print(self.style.theme_names())
        self.style.theme_use(theme)

        ttk.Style().configure('my.TButton', font=('Helvetica', 12),
                                            focuscolor='none')
        # ttk.Style().map('my.TButton', foreground=[("active", "White")],
        #                               background=[("active", "#2a6cdd")])

        ttk.Style().configure('my.TLabel', font=('Helvetica', 12))

        ttk.Style().configure('my.TFrame', background='#282b30')

        ttk.Style().configure('my.TEntry', background="#2a6cdd",
                                           selectbackground='#2a6cdd',
                                           selectforeground='White')

        ttk.Style().map('my.TEntry', foreground=[("selected", "White")],
                                     background=[("active", "#2a6cdd")])

        ttk.Style().configure('my.TNotebook', font=('Helvetica', 12),
                                            focuscolor='none')
        ## Title bar color
        HWND = windll.user32.GetParent(self.winfo_id())
        TITLE_BAR_COLOR = 0x00000000
        windll.dwmapi.DwmSetWindowAttribute(HWND, 35,
                                            byref(c_int(TITLE_BAR_COLOR)),
                                            sizeof(c_int))

        ## Background
        # self.configure(background='#515151')
        self.attributes("-alpha", 0.95)

        ## Main Frame
        main_frame = ttk.Frame(self, style="my.TFrame")
        main_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

        ## Base Frame
        self.ip_scan_frame = ttk.Frame(main_frame)
        self.ip_scan_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=5)
        self.init_devices_scan_widget(self.ip_scan_frame)

        ## Text Frame
        self.text_frame = ttk.Frame(main_frame)
        self.text_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=5)
        self.init_text_widget(self.text_frame)

        self.refresh_window_status()


    def disableChildren(self, parent):

        for child in parent.winfo_children():
            wtype = child.winfo_class()
            # print (wtype)
            if wtype not in MyApp.CANNOT_DISABLE_WIDGET:
                child.configure(state='disabled')
            else:
                self.disableChildren(child)

    def enableChildren(self, parent):

        for child in parent.winfo_children():
            wtype = child.winfo_class()
            # print (wtype)
            if wtype not in MyApp.CANNOT_DISABLE_WIDGET:
                child.configure(state='normal')
            else:
                self.enableChildren(child)

    def output_text_insert(self, text: str, tag=None):
        self.text_output_lock.acquire()
        self.output_text.insert(tk.END, f"{text}\n", tag)
        self.output_text.see(tk.END)
        self.output_text.update()
        self.text_output_lock.release()

    def update_history_text(self, item, item_text):
        history_text = self.scan_treeview.item(item,"text")
        new_history_text = f"\n{item_text}" if not history_text else f"{history_text}\n\n{item_text}"
        self.scan_treeview_lock.acquire()
        self.scan_treeview.item(item, text=new_history_text)
        self.scan_treeview_lock.release()


    def init_devices_scan_widget(self, base_frame):

        # IP range label
        ip_range_label = ttk.Label(base_frame,
                                   text="IP address range/Network:",
                                   style="my.TLabel")

        # Input entry
        # self.ip_range_entry = ttk.Entry(base_frame,
        #                            style='my.TEntry')
        self.ip_range_entry = tk.Entry(base_frame)
        self.ip_range_entry.config(disabledbackground="#dddddd")
        self.ip_range_entry.insert(tk.END, "192.168.48.0/21")  # Set default value

        # Scan button
        scan_button = ttk.Button(base_frame,
                                 text="Scan",
                                 style="my.TButton",
                                 command=self.btn_click_scan)

        table_title = ttk.Label(base_frame,
                                text="Scan Table:",
                                style="my.TLabel")

        ## Arrange widget
        ip_range_label.grid(     row=0,  column=0, padx=10, pady=5, sticky=tk.W)
        self.ip_range_entry.grid(row=0,  column=1, padx=10, pady=5, sticky=tk.W)
        scan_button.grid(        row=0,  column=2, padx=10, pady=5, sticky=tk.W)
        table_title.grid(        row=1,  column=0, padx=10, pady=5, sticky=tk.W)

        ## Scan table
        table_frame = ttk.Frame(base_frame)
        table_frame.grid(row=2, column=0, columnspan=3, padx=10, pady=0, sticky=tk.W)
        ttk.Style().configure("my.Treeview")
        # ttk.Style().map("my.Treeview",
        #         background=[("selected", "#2a6cdd")],
        #         foreground=[("selected", "white")])

        style_value = ttk.Style()
        style_value.configure("Treeview", rowheight=25, font=("Helvetica", 12))

        self.scan_treeview = ttk.Treeview(table_frame, selectmode="extended", style="my.Treeview", height=10)

        self.scan_treeview["columns"] = ("ip", "mac", "model-id", "ping")
        self.scan_treeview.column("ip",         width=138, minwidth=138, stretch=True, anchor="center")
        self.scan_treeview.column("mac",        width=138, minwidth=138, stretch=True, anchor="center")
        self.scan_treeview.column("model-id",   width=138, minwidth=138, stretch=True, anchor="center")
        self.scan_treeview.column("ping",       width=138, minwidth=138, stretch=True, anchor="center")

        self.scan_treeview["show"] = "headings"
        self.scan_treeview.heading('ip',        text="IP")
        self.scan_treeview.heading('mac',       text="MAC")
        self.scan_treeview.heading('model-id',  text="Model")
        self.scan_treeview.heading('ping',      text="Ping")
        self.scan_treeview.pack(expand=1, fill=tk.BOTH, pady=0)
        self.scan_treeview.bind("<Double-1>", self.scan_treeview_db_click)

        ## scan_treeview_menu
        def remove_scan_treeview_item():
            selected_items = self.scan_treeview.selection()
            self.scan_treeview_lock.acquire()
            for item in selected_items:
                self.scan_treeview.delete(item)
            self.scan_treeview_lock.release()
    
        def add_scan_treeview_item():
            popupWin = popupWindow_Add_scan_item(self)
            self.wait_window(popupWin.popup)

            new_item = popupWin.new_item_value
            if popupWin.exit_result and new_item:
                self.scan_treeview.insert("", "end", values=new_item)

        self.scan_treeview_menu = tk.Menu(self.scan_treeview, tearoff=0)
        self.scan_treeview_menu.add_command(label="Remove",
                                            command=remove_scan_treeview_item)
        self.scan_treeview_menu.add_command(label="Add",
                                            command=add_scan_treeview_item)

        ## scan_treeview_ping_menu
        def join_ping(flag):
            selected_items = self.scan_treeview.selection()
            self.ping_btn_lock.acquire()

            for item in selected_items:
                if flag and item not in self.ping_items:
                    self.ping_items.append(item)

                if flag is False and item in self.ping_items:
                    self.ping_items.remove(item)
                    self.scan_treeview.item(item, tags=())
            self.ping_btn_lock.release()

        self.scan_treeview_ping_menu = tk.Menu(self.scan_treeview, tearoff=0)
        self.scan_treeview_ping_menu.add_command(label="join ping",
                                                 command=lambda: join_ping(True))
        self.scan_treeview_ping_menu.add_command(label="leave ping",
                                                 command=lambda: join_ping(False))

        def show_scan_treeview_menu(event):
            item = self.scan_treeview.identify_row(event.y)
            if item:
                # self.scan_treeview.selection_set(item)
                if self.is_pinging:
                    self.scan_treeview_ping_menu.post(event.x_root, event.y_root)
                else:
                    self.scan_treeview_menu.post(event.x_root, event.y_root)

        self.scan_treeview.bind("<Button-3>", show_scan_treeview_menu)

        self.scan_treeview.tag_configure("offline", background="lightgray")
        self.scan_treeview.tag_configure("online", background="#3dc9cc")
        
        ## Operation button
        def popup_configure_window():
            popupWin = popupWindow_Configure(self,
                                             self.ssh_password,
                                             self.OS_connection_mode)
            self.wait_window(popupWin.popup)
            if popupWin.exit_result:
                self.ssh_password = popupWin.ssh_password
                self.OS_connection_mode = popupWin.os_connection_mode

            self.refresh_window_status()

        self.configure_button = ttk.Button(base_frame,
                                 text="Configure",
                                 style="my.TButton",
                                 command=popup_configure_window)
        self.device_info_button = ttk.Button(base_frame,
                                 text="Get device info",
                                 style="my.TButton",
                                 command=self.btn_click_get_device_info)
        self.ping_alive_button = ttk.Button(base_frame,
                                 text=f"Ping({self.ping_counter})",
                                 style="my.TButton",
                                 command=lambda: self.btn_click_toggle_ping())

        def popup_scp_setting_window():
            popupWin = popupWindow_SCP(self, self.scp_config)
            self.wait_window(popupWin.popup)
            if popupWin.exit_result:
                self.scp_config = popupWin.scp_config

        self.scp_option_button = ttk.Button(base_frame,
                                 text="SCP Setting",
                                 style="my.TButton",
                                 command=lambda: popup_scp_setting_window())
                                 
        self.upload_button = ttk.Button(base_frame,
                                 text="SCP upload",
                                 style="my.TButton",
                                 command=lambda: self.btn_click_scp("upload"))
        self.download_button = ttk.Button(base_frame,
                                 text="SCP download",
                                 style="my.TButton",
                                 command=lambda: self.btn_click_scp("download"))

        ## Arrange
        self.configure_button.grid(  row=3, column=0, padx=10, pady=5, sticky=tk.W)
        self.device_info_button.grid(row=3, column=1, padx=10, pady=5, sticky=tk.W)
        self.ping_alive_button.grid(row=3, column=2, padx=10, pady=5, sticky=tk.W)
        self.scp_option_button.grid(row=4, column=0, padx=10, pady=5, sticky=tk.W)
        self.upload_button.grid(    row=4, column=1, padx=10, pady=5, sticky=tk.W)
        self.download_button.grid(  row=4, column=2, padx=10, pady=5, sticky=tk.W)

    def init_text_widget(self, base_frame):

        tab_control = ttk.Notebook(base_frame, style="my.TNotebook")

        ## Output and Result Tab
        output_result_tab_frame = ttk.Frame(tab_control)
        self.output_text = tk.Text(output_result_tab_frame,
                                   wrap="word",
                                   background="White",
                                   height=21,
                                   font=("Helvetica", 12))
        scrollbar = ttk.Scrollbar(output_result_tab_frame, command=self.output_text.yview)
        self.output_text.config(yscrollcommand=scrollbar.set)

        clear_output_button = ttk.Button(output_result_tab_frame,
                                         text="Clear Output",
                                         style="my.TButton",
                                         command=lambda: self.output_text.delete("1.0", "end"))

        ## Arrange Output and Result Tab
        clear_output_button.pack(side="bottom", padx=10, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.output_text.pack(fill="both", expand=True)

        tab_control.add(output_result_tab_frame, text="Output and Result")

        self.output_text.tag_configure("red", foreground="red", font=("Helvetica", 12, "italic"))
        self.output_text.tag_configure("history", foreground="#224581", font=("Helvetica", 12, "italic"))
        self.output_text.tag_configure("title", foreground="black", font=("Helvetica", 12, "bold"))

        ## Input Cmd Tab
        input_cmd_tab_frame = ttk.Frame(tab_control)
        self.input_text = tk.Text(input_cmd_tab_frame,
                                  wrap="word",
                                  background="White",
                                  height=21,
                                  font=("Helvetica", 12))

        clear_input_button = ttk.Button(input_cmd_tab_frame,
                                        text="Clear Input",
                                        style="my.TButton",
                                        command=lambda: self.input_text.delete("1.0", "end"))

        send_button = ttk.Button(input_cmd_tab_frame,
                                 text="Send OS Cmd",
                                 style="my.TButton",
                                 command=self.btn_click_send_OS_command)

        timeout_label = ttk.Label(input_cmd_tab_frame, text="Timeout (sec):")
        self.timeout_entry = ttk.Entry(input_cmd_tab_frame, width=10)
        self.timeout_entry.insert(0, str(self.default_OS_cmd_timeout_sec))

        # send_button = ttk.Button(input_cmd_tab,
        #                          text="Send OS Cmd",
        #                          style="my.TButton",
        #                          command=self.send_Telnet_command)

        ## Arrange Input Cmd Tab
        self.input_text.pack(fill="both", expand=True)
        clear_input_button.pack(side="right", padx=10, pady=5)
        send_button.pack(side="right", padx=10, pady=5)
        self.timeout_entry.pack(side="right", padx=10, pady=5)
        timeout_label.pack(side="right", padx=10, pady=5)

        tab_control.add(input_cmd_tab_frame, text="OS Cmd")

        ## lgw Cmd Tab
        lgw_cmd_tab_frame = ttk.Frame(tab_control)
        self.lgw_cmd_treeview = ttk.Treeview(lgw_cmd_tab_frame, columns=("command"))

        self.lgw_cmd_treeview["show"] = "headings"
        self.lgw_cmd_treeview.heading("command", text="Command Template")
        self.lgw_cmd_treeview.bind("<Double-1>", self.lgw_cmd_tvw_db_click)

        def edit_lgw_cmd_treeview_item():
            selected_item = self.lgw_cmd_treeview.selection()
            if selected_item:
                old_text = self.lgw_cmd_treeview.set(selected_item)["command"]
                popupWin = popupWindow_LGW_Cmd(self, "Edit", initialvalue=old_text)
                self.wait_window(popupWin.popup)
                if popupWin.exit_result:
                    new_text = popupWin.lgw_cmd_list[0]
                    self.lgw_cmd_treeview.item(selected_item, values=(new_text,))

        self.lgw_cmd_treeview_menu = tk.Menu(self.lgw_cmd_treeview, tearoff=0)
        self.lgw_cmd_treeview_menu.add_command(label="Edit", command=edit_lgw_cmd_treeview_item)

        def show_lgw_cmd_treeview_menu(event):
            item = self.lgw_cmd_treeview.identify_row(event.y)
            if item:
                self.lgw_cmd_treeview.selection_set(item)
                self.lgw_cmd_treeview_menu.post(event.x_root, event.y_root)

        self.lgw_cmd_treeview.bind("<Button-3>", show_lgw_cmd_treeview_menu)

        add_button = ttk.Button(lgw_cmd_tab_frame,
                                text="Add",
                                style="my.TButton",
                                command=self.btn_click_lgw_cmd_add_item)
        
        send_button = ttk.Button(lgw_cmd_tab_frame,
                                 text="Send",
                                 style="my.TButton",
                                 command=self.btn_click_send_lgw_commands)

        lgw_timeout_label = ttk.Label(lgw_cmd_tab_frame, text="Timeout (sec):")
        self.lgw_cmd_timeout_entry = ttk.Entry(lgw_cmd_tab_frame, width=10)
        self.lgw_cmd_timeout_entry.insert(0, str(self.default_LGW_cmd_timeout_sec))

        lgw_cmd_sub_frame = ttk.Frame(lgw_cmd_tab_frame)
        channel_list_label = ttk.Label(lgw_cmd_sub_frame, text="End points:")
        self.channel_list_entry = ttk.Entry(lgw_cmd_sub_frame, width=50)
        self.channel_list_entry.insert(0, 1)

        ## Arrange lgw Cmd Tab
        self.lgw_cmd_treeview.pack(expand=1, fill="both", padx=10, pady=5)
        lgw_cmd_sub_frame.pack(expand=1, fill="both")
        self.channel_list_entry.pack(side="right", padx=10, pady=5)
        channel_list_label.pack(side="right", padx=10, pady=5)

        add_button.pack(side="right", padx=10, pady=5)
        send_button.pack(side="right", padx=10, pady=5)
        self.lgw_cmd_timeout_entry.pack(side="right", padx=10, pady=5)
        lgw_timeout_label.pack(side="right", padx=10, pady=5)
        tab_control.add(lgw_cmd_tab_frame, text="LGW Cmd")

        tab_control.pack(expand=1, fill="both", padx=10, pady=5)

    def btn_click_lgw_cmd_add_item(self):
        popupWin = popupWindow_LGW_Cmd(self)
        self.wait_window(popupWin.popup)
        if popupWin.exit_result:
            lgw_cmd_list = popupWin.lgw_cmd_list
            for cmd in lgw_cmd_list:
                self.lgw_cmd_treeview.insert("", "end", values=(cmd,))

    def lgw_cmd_tvw_db_click(self, event):
        region = self.lgw_cmd_treeview.identify_region(event.x,event.y)
        ## Sort
        if region == "heading":
            col_id = self.lgw_cmd_treeview.identify('column', event.x, event.y)

            rows = [(str(self.lgw_cmd_treeview.set(item, col_id)).lower(), item) 
                        for item in self.lgw_cmd_treeview.get_children('')]
            rows.sort()

            for index, (values, item) in enumerate(rows):
                self.lgw_cmd_treeview.move(item, '', index)
        ## Remove
        elif region == "cell":
            item = self.lgw_cmd_treeview.identify('item', event.x, event.y)
            self.lgw_cmd_treeview.delete(item)

    def btn_click_send_lgw_commands(self):
        selected_items = self.scan_treeview.selection()
        if not selected_items:
            messagebox.showerror("Error", "No devices have been selected.", parent=self)
            return

        selected_cmd_items = self.lgw_cmd_treeview.selection()
        if not selected_cmd_items:
            messagebox.showerror("Error", "No commands have been selected.", parent=self)
            return

        channel_list = MyApp.validate_integer_list(self.channel_list_entry.get())
        # print(channel_list)
        if not channel_list:
            messagebox.showerror("Invalid channel list", "Please enter comma-separated integers.", parent=self)
            return

        timeout_sec = self.lgw_cmd_timeout_entry.get()
        if timeout_sec and not cyl_util.is_float(timeout_sec):
            messagebox.showerror("Error", "timeout value must be float.", parent=self)
            return

        timeout_sec = None if timeout_sec == "" else float(timeout_sec)

        def send_lgw_commands():

            cmd_list = [self.lgw_cmd_treeview.set(item)["command"] for item in selected_cmd_items]
            # print(cmd_list)

            hosts = [self.scan_treeview.set(item) for item in selected_items]
            res = asyncio.run(cyl_async_telnet.send_telnet_9528cmds(hosts,
                                                                    cmd_template_list=cmd_list,
                                                                    channel_list=channel_list,
                                                                    timeout=timeout_sec))
            # print(res)

            ## show
            self.output_text_insert(f"\nSend LGW Cmd:", "title")
            for item in selected_items:
                device = self.scan_treeview.set(item)
                ip = device["ip"]
                cmd_result_list = [cmd_return["result"] for cmd_return in res[ip]]
                self.output_text_insert(f"\n{device}", "title")

                res_text = ""
                for cmd_res in cmd_result_list:
                    text_tag = "red" if not cmd_res[0] else None
                    cmd_res = str(cmd_res).replace('\\r', '').replace('\\n', '\n').replace(')', '\n)')
                    self.output_text_insert(cmd_res, text_tag)
                    res_text += f"{cmd_res}\n"

                item_text = f"LGW Response:\n{res_text}"
                ## update item history
                self.update_history_text(item, item_text)

        thread = threading.Thread(target=send_lgw_commands)
        thread.daemon = True
        thread.start()

    def btn_click_send_OS_command(self):
        selected_items = self.scan_treeview.selection()
        if not selected_items:
            messagebox.showerror("Error", "No devices have been selected.", parent=self)
            return

        timeout_sec = self.timeout_entry.get()
        if timeout_sec and not cyl_util.is_float(timeout_sec):
            messagebox.showerror("Error", "timeout value must be float or keep it empty for waiting forever.", parent=self)
            return

        timeout_sec = None if timeout_sec == "" else float(timeout_sec)

        def send_OS_commands():
        
            input_command = self.input_text.get("1.0", "end-1c")

            cmd_list = input_command.splitlines()

            hosts = [self.scan_treeview.set(item) for item in selected_items]
            
            res = None
            if self.OS_connection_mode == "Telnet":
                res = asyncio.run(cyl_async_telnet.send_telnet_23cmds(hosts,
                                                                      cmd_list=cmd_list,
                                                                      timeout=timeout_sec))
            elif self.OS_connection_mode == "SSH":
                username = "root"
                res = asyncio.run(cyl_async_ssh.send_ssh_cmds(hosts,
                                                              username,
                                                              self.ssh_password,
                                                              cmd_list=cmd_list,
                                                              timeout=timeout_sec))
            # print(res)

            ## show
            self.output_text_insert(f"\nSend OS Cmd:", "title")
            for item in selected_items:
                device = self.scan_treeview.set(item)
                ip = device["ip"]
                cmd_result_list = [cmd_return["result"] for cmd_return in res[ip]]
                self.output_text_insert(f"\n{device}", "title")

                res_text = ""
                for cmd_res in cmd_result_list:
                    text_tag = "red" if not cmd_res[0] else None
                    cmd_res = str(cmd_res).replace('\\r', '').replace('\\n', '\n')
                    self.output_text_insert(cmd_res, text_tag)
                    res_text += f"{cmd_res}\n"

                item_text = f"OS Response:\n{res_text}"
                ## update item history
                self.update_history_text(item, item_text)

        thread = threading.Thread(target=send_OS_commands)
        thread.daemon = True
        thread.start()


    def btn_click_scan(self):
        ip_range = self.ip_range_entry.get()
        target_networks = []
        if not ip_range:
            target_networks = asyncio.run(scanner.async_get_networks())
        else:
            range_token = ip_range.split('.')[-1]

            # Validate input
            try:
                if "-" in range_token:
                    t = range_token.split("-")
                    if cyl_util.is_float(t[0]) and cyl_util.is_float(t[1]):
                        target_networks = scanner.ipv4_range_to_cidr(start=ip_range)
                elif "/" in range_token:
                    t = range_token.split("/")
                    if cyl_util.is_float(t[0]) and cyl_util.is_float(t[1]):
                        target_networks = [IPv4Network(ip_range)]
                else:
                    if cyl_util.is_float(range_token):
                        target_networks = [IPv4Network(ip_range)]
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=self)
                return

        # print(target_networks)
        msg = '\n'.join([str(net) for net in target_networks])
        self.output_text_insert(f"Scan target Network:", "title")
        self.output_text_insert(f"{msg}")
        if not target_networks:
            messagebox.showerror("Error", "Invalid IP range", parent=self)
            return

        ## Disable scan button
        self.output_text_insert(f"\nScan device start...")
        self.disableChildren(self.ip_scan_frame)
        ## clear treeview
        for item in self.scan_treeview.get_children():
            self.scan_treeview.delete(item)
        self.refresh_window_status()

        ## Scan by thread
        thread = threading.Thread(target=self.scan_devices, args=(target_networks,))
        thread.daemon = True
        thread.start()

    @staticmethod
    def OS_out_version_result_filter(result):
        if not result[0]:
            return "Error"
        pattern = r'v[0-9]+\.[0-9]+\.[0-9]+'
        match = re.search(pattern, result[1])
        if match:
            return match.group(0)
        return result[1].strip()

    @staticmethod
    def telnet9528_out_result_filter(result, key: str):
        if not result[0]:
            return "Error"
        if isinstance(result[1], dict) and result[1].get(key) is not None:
            return result[1].get(key)
        return result[1]

    @staticmethod
    def validate_integer_list(integer_list_str):
        try:
            num_list = []
            token_list = [token.strip() for token in integer_list_str.split(",")]
            for token in token_list:
                cut = token.split("-")
                if len(cut) == 1:
                    num_list.append(int(token))
                else:
                    num_list += list(range(int(cut[0]), int(cut[1])+1))

            num_list.sort()
            return num_list
        except Exception as e:
            # print(str(e))
            return []

    def check_alive(self, count=3, interval=0.2, timeout=1):

        # selected_items = self.scan_treeview.selection()
        
        hosts = [self.scan_treeview.set(item)['ip'] for item in self.ping_items]
        ret = asyncio.run(cyl_async_ping.is_hosts_alive(hosts,
                                                        count=count,
                                                        interval=interval,
                                                        timeout=timeout))
        self.ping_counter += 1
        self.ping_btn_lock.acquire()
        self.ping_alive_button.config(text=f"Stop({self.ping_counter})")
        self.ping_btn_lock.release()

        for item in self.ping_items:
            ip = self.scan_treeview.set(item)["ip"]
            ping = int(self.scan_treeview.set(item)["ping"])
            if res := ret.get(ip):
                self.scan_treeview_lock.acquire()
                if res[0] is True:
                    ping += 1
                    self.scan_treeview.set(item, "ping", ping)
                    self.scan_treeview.item(item, tags=("online",))
                    # self.scan_treeview.update()
                else:
                    self.scan_treeview.item(item, tags=("offline",))
                self.scan_treeview_lock.release()

    def scan_devices(self, networks):

        hosts = asyncio.run(scanner.async_scan_networks(networks))

        tid = cyl_util.make_target_id("", 0)
        cmd_template = cyl_util.make_cmd("read-attr", target_id=tid, attr="model-id")
        res = asyncio.run(cyl_async_telnet.send_telnet_9528cmds(hosts, cmd_template_list=[cmd_template]))
        # print(res)
        # print(hosts)
        ## Update treeview
        self.scan_treeview_lock.acquire()
        for host in hosts:
            ip = host['ip']
            cmd_result = res[ip][0]["result"]
            model_id = MyApp.telnet9528_out_result_filter(cmd_result, "value")
            # print(model_id)
            self.scan_treeview.insert("", "end", values=(host['ip'], host['mac'], model_id, 0))
        self.scan_treeview_lock.release()

        ## Enable ip scan frame
        self.enableChildren(self.ip_scan_frame)
        self.refresh_window_status()
        self.output_text_insert(f"Find {len(hosts)} devices.")
        self.output_text_insert(f"Scan device finish!!!\n")


    def scan_treeview_db_click(self, event):
        region = self.scan_treeview.identify_region(event.x,event.y)

        ## Sort
        if region == "heading":
            col_id = self.scan_treeview.identify('column', event.x, event.y)

            rows = [(str(self.scan_treeview.set(item, col_id)).lower(), item) 
                        for item in self.scan_treeview.get_children('')]
            rows.sort()

            for index, (values, item) in enumerate(rows):
                self.scan_treeview.move(item, '', index)

        ## Show history
        elif region == "cell":
            item = self.scan_treeview.identify('item', event.x, event.y)
            device = self.scan_treeview.set(item)
            text = self.scan_treeview.item(item,"text")
            self.output_text_insert(f"\nHistory:\n{device}", "title")
            if text:
                self.output_text_insert(f"{text}", "history")

    
    def btn_click_get_device_info(self):
        selected_items = self.scan_treeview.selection()
        if not selected_items:
            messagebox.showerror("Error", "No devices have been selected.", parent=self)
            return

        def get_device_info():
            ## OS, RS, RN, OTA
            cmd_dict = {"OS": "cat /etc/os_version",
                        "RS": "cat /root/restart_server.sh|grep -Eom 1 'v[0-9]+\.[0-9]+\.[0-9]+'",
                        "RN": "cat /root/restart_network.sh|grep -Eom 1 'v[0-9]+\.[0-9]+\.[0-9]+'",
                        "OTA": "cat /root/ota.sh|grep -Eom 1 'v[0-9]+\.[0-9]+\.[0-9]+'"}

            hosts = [self.scan_treeview.set(item) for item in selected_items]
            
            self.output_text_insert(f"\nGet device info start...")
            res = None
            if self.OS_connection_mode == "Telnet":
                res = asyncio.run(cyl_async_telnet.send_telnet_23cmds(hosts,
                                                                      cmd_list=cmd_dict.values()))
            elif self.OS_connection_mode == "SSH":
                username = "root"
                res = asyncio.run(cyl_async_ssh.send_ssh_cmds(hosts,
                                                              username,
                                                              self.ssh_password,
                                                              cmd_list=cmd_dict.values()))
            # print(res)

            device_info_dict={}
            for item in selected_items:
                ip = self.scan_treeview.set(item)["ip"]
                device_info = {}
                for i, cmd_return in enumerate(res[ip]):
                    device_info[list(cmd_dict.keys())[i]] = MyApp.OS_out_version_result_filter(cmd_return["result"])
                device_info_dict[item] = device_info

            ## FW
            tid = cyl_util.make_target_id("", 0)
            cmd_template = cyl_util.make_cmd("read-attr", target_id=tid, attr="commit-id")
            res = asyncio.run(cyl_async_telnet.send_telnet_9528cmds(hosts, cmd_template_list=[cmd_template]))
            # print(res)

            for item in selected_items:
                ip = self.scan_treeview.set(item)["ip"]
                cmd_result = res[ip][0]["result"]
                commit_id = MyApp.telnet9528_out_result_filter(cmd_result, "value")
                device_info_dict[item]["FW"] = commit_id

            ## LGW
            tid = cyl_util.make_target_id("", 0)
            cmd_template = cyl_util.make_cmd("configure")
            res = asyncio.run(cyl_async_telnet.send_telnet_9528cmds(hosts, cmd_template_list=[cmd_template]))
            # print(res)

            for item in selected_items:
                ip = self.scan_treeview.set(item)["ip"]
                cmd_result = res[ip][0]["result"]
                lgw_ver = MyApp.telnet9528_out_result_filter(cmd_result, "server-version")
                device_info_dict[item]["LGW"] = lgw_ver

            self.output_text_insert(f"Get device info finish!!!\n")

            ## show
            self.output_text_insert(f"\nGet device info:", "title")
            for item in selected_items:
                device = self.scan_treeview.set(item)
                res_text = str(device_info_dict[item]).replace(',', ',\n')
                item_text = f"Device info:\n{res_text}"
                self.output_text_insert(f"\n{device}", "title")
                self.output_text_insert(item_text)

                ## update item history
                self.update_history_text(item, item_text)

        thread = threading.Thread(target=get_device_info)
        thread.daemon = True
        thread.start()


    def btn_click_toggle_ping(self):

        def start_ping():

            def initial_ping_status():
                self.ping_counter = 0
                for item in self.scan_treeview.get_children(''):
                    self.scan_treeview_lock.acquire()
                    self.scan_treeview.set(item, "ping", 0)
                    self.scan_treeview.item(item, tags=())
                    self.scan_treeview.update()
                    self.scan_treeview_lock.release()

                self.ping_alive_button.config(text=f"Ping({self.ping_counter})")

            def ping_loop(schedule_sec, count, interval, timeout):

                while self.is_pinging:
                    self.check_alive(count, interval, timeout)
                    time.sleep(schedule_sec)

            def popup_ping_setting_window():
                popupWin = popupWindow_Ping(self, self.ping_config)
                self.wait_window(popupWin.popup)
                if popupWin.exit_result:
                    self.ping_config = popupWin.ping_config
                return popupWin.exit_result

            ## clear ping counter
            initial_ping_status()
            if not self.ping_thread or not self.ping_thread.is_alive():
                if not popup_ping_setting_window():
                    return

                self.ping_btn_lock.acquire()
                self.ping_items = list(self.scan_treeview.selection())
                self.ping_alive_button.config(text=f"Stop({self.ping_counter})")
                self.ping_btn_lock.release()

                schedule_sec=self.ping_config.get("schedule_sec", 1)
                count=self.ping_config.get("packet_count", 3)
                interval=self.ping_config.get("interval", 0.2)
                timeout=self.ping_config.get("timeout", 1)

                self.output_text_insert("\nPing start...")
                self.output_text_insert(f'Sends ({count}) packet(s) per ({interval}) sec, timeout:({timeout}) sec, schedule every ({schedule_sec}) sec.')
                self.ping_thread = threading.Thread(target=ping_loop, args=(schedule_sec, count, interval, timeout))
                self.ping_thread.daemon = True
                self.is_pinging = True
                self.ping_thread.start()


        def stop_ping():
            if self.ping_thread and self.ping_thread.is_alive():
                self.is_pinging = False
                self.output_text_insert(f"Ping stop!!!\n")

                self.ping_btn_lock.acquire()
                self.ping_items = []
                self.ping_alive_button.config(text=f"Ping({self.ping_counter})")
                self.ping_btn_lock.release()

        if not self.is_pinging:
            start_ping()
        else:
            stop_ping()

    def btn_click_scp(self, action):
        selected_items = self.scan_treeview.selection()
        if not selected_items:
            messagebox.showerror("Error", "No devices have been selected.", parent=self)
            return

        ## upload guard!
        if action == "upload":
            poc_list = [self.scan_treeview.set(item) 
                            for item in selected_items 
                                if self.scan_treeview.set(item).get("model-id")=="POC"]
            all_list = [self.scan_treeview.set(item) 
                            for item in selected_items]

            if len(poc_list) and len(poc_list) != len(all_list):
                messagebox.showerror("Error", "You cannot upload POC device with other devices.", parent=self)
                return


        def do_scp(action, storage, config_name):
            remote_hosts = [self.scan_treeview.set(item)["ip"] for item in selected_items]
            username = "root"
            password = self.ssh_password

            self.output_text_insert(f"\nSCP {action} start...")
            res = asyncio.run(cyl_async_ssh.scp_process(username, 
                                                        password,
                                                        remote_hosts,
                                                        action,
                                                        storage,
                                                        config_name))
            self.output_text_insert(f"SCP {action} finish!!!\n")
            # print(res)
            ## show
            self.output_text_insert(f"SCP {action}:", "title")
            for item in selected_items:
                device = self.scan_treeview.set(item)
                result = res[device["ip"]]
                item_text = f'SCP {action} result: {result}'
                self.output_text_insert(f"\n{device}", "title")
                text_tag = "red" if not result[0] else None
                self.output_text_insert(f"{item_text}", text_tag)

                ## update item history
                self.update_history_text(item, item_text)

        storage = self.scp_config.get("storage_folder", "storage")
        config_name = self.scp_config.get("config_name", "")

        thread = threading.Thread(target=do_scp, args=(action, storage, config_name))
        thread.daemon = True
        thread.start()
    
    def refresh_window_status(self):

        if not self.scan_treeview.get_children(''):
            self.scp_option_button.configure(state='normal')
            self.configure_button.configure(state='normal')
            self.upload_button.configure(state='disabled')
            self.download_button.configure(state='disabled')
            self.ping_alive_button.configure(state='disabled')
            self.device_info_button.configure(state='disabled')
        else:
            if self.OS_connection_mode == "SSH":
                self.scp_option_button.configure(state='normal')
                self.upload_button.configure(state='normal')
                self.download_button.configure(state='normal')
            else:
                self.scp_option_button.configure(state='disabled')
                self.upload_button.configure(state='disabled')
                self.download_button.configure(state='disabled')


a = MyApp()
a.mainloop()


# root = tk.Tk()

# root.style = ttkthemes.ThemedStyle()

# for i, name in enumerate(sorted(root.style.theme_names())):
#     b = ttk.Button(root, text=name, command=lambda name=name:root.style.theme_use(name))
#     b.pack(fill='x')

# root.mainloop()