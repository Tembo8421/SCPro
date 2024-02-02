import asyncio
import os
import re
import threading
import time
import tkinter as tk
from ctypes import byref, c_int, sizeof  # , windll
from ipaddress import IPv4Network
from tkinter import messagebox, ttk

import customtkinter as ctk
from ttkthemes import ThemedStyle

from core import (cyl_async_ping, cyl_async_ssh, cyl_async_telnet, cyl_util,
                  cyl_wrapper)
from scanner import scanner


class TreeviewEditEntry():
    
    def __init__(self, parent, item, column, validate_callback=None):
        ''' If relwidth is set, then width is ignored '''
        self.edit_entry = ttk.Entry(parent)
        self.treeview = parent
        self.item = item
        self.column = column
        self.exit_result = False

        self.validate_callback = validate_callback

        ## get column position info
        x, y, width, height =  self.treeview.bbox(item, column)
        pady = height // 2
        self.edit_entry.place(x=x, y=y+pady, anchor="w", width=width)

        text = self.treeview.set(item, column)
        self.input_txt = text
        self.edit_entry.insert(0, text) 
        # self['state'] = 'readonly'
        # self['readonlybackground'] = 'white'
        # self['selectbackground'] = '#1BA1E2'
        self.edit_entry['exportselection'] = False

        self.edit_entry.focus_force()
        self.select_all()
        
        ## binding
        self.edit_entry.bind("<Return>", self.on_return)
        self.edit_entry.bind("<FocusOut>", lambda *ignore: self.edit_entry.destroy())
        self.edit_entry.bind("<Control-a>", self.select_all)
        self.edit_entry.bind("<Escape>", lambda *ignore: self.edit_entry.destroy())

    def validate_input(self, input_field, input_text):
        if self.validate_callback:
            return self.validate_callback(input_field, input_text)
        return True, ""

    def on_return(self, event):
        input_field = self.treeview.heading(self.column, option="text")
        res, msg = self.validate_input(input_field , self.edit_entry.get())
        if not res:
            messagebox.showerror("Error", f"Invalid {input_field}:{msg} !", parent=self.edit_entry)
            return

        self.exit_result = True
        self.input_txt = self.edit_entry.get()
        self.edit_entry.destroy()

    def select_all(self, *ignore):
        ''' Set selection on the whole text '''
        self.edit_entry.selection_range(0, 'end')

        # returns 'break' to interrupt default key-bindings
        return 'break'

class myTreeviewBindSetter():
    def __init__(self, treeview, callback_dict=None, right_click_menu_callback_dict=None):
        self.treeview = treeview
        self.menu_callback_func = {"Remove": self.remove_selected_items}
        if right_click_menu_callback_dict:
            self.menu_callback_func.update(right_click_menu_callback_dict)

        if callback_dict:
            self.callback_func = callback_dict
    
    def binding(self):
        self.create_menu()
        self.treeview.bind("<Button-3>", self.show_menu)
        self.treeview.bind('<Control-a>', self.select_all)
        self.treeview.bind('<Delete>', lambda event: self.remove_selected_items())
        self.treeview.bind("<Shift-Up>",lambda event: self.movement("Up"))
        self.treeview.bind("<Shift-Down>",lambda event: self.movement("Down"))

        for key, val in self.callback_func.items():
            if val:
                self.treeview.bind(key, lambda event: val(event))
        self.treeview.bind("<Double-1>", self.double_click)

    def movement(self, action="Up"):
        selected_items = self.treeview.selection()
        step = -1 if action == "Up" else 1
        if not selected_items:
            return 'break'
        if self.treeview.index(selected_items[0])+step < 0 or self.treeview.index(selected_items[-1])+step >= len(self.treeview.get_children('')):
            return 'break'

        if action == "Down":
            selected_items = reversed(selected_items)
        for s in selected_items:
            self.treeview.move(s, '', self.treeview.index(s)+step)
        return 'break'

    def create_menu(self):
        self.treeview_menu = tk.Menu(self.treeview, tearoff=0)
        for key, val in self.menu_callback_func.items():
            if val:
                self.treeview_menu.add_command(label=key, command=val)

    @cyl_wrapper.setVar("reverse", False)
    def sort(self, event):
        col_id =  self.treeview.identify('column', event.x, event.y)

        rows = [(str( self.treeview.set(item, col_id)).lower(), item) 
                    for item in  self.treeview.get_children('')]
        rows.sort(reverse=self.sort.reverse)
        self.sort.__dict__["reverse"] ^= True

        for index, (values, item) in enumerate(rows):
             self.treeview.move(item, '', index)

    def double_click(self, event):
        """handel the double click event."""
        region = self.treeview.identify_region(event.x,event.y)
        # print(region)

        ## Clear selection when click on blank
        if region == "nothing":
            self.treeview.selection_remove(self.treeview.selection())
        ## Do sort when click on a heading
        elif region == "heading":
            self.sort(event)
        ## Do edit when click on a cell
        elif region == "cell":
            if self.callback_func.get("<Double-1>"):
                self.callback_func.get("<Double-1>")(event)

    def show_menu(self, event):
        """show right click menu"""
        item = self.treeview.identify_row(event.y)
        if item:
            if not self.treeview.selection():
                self.treeview.selection_set(item)
        self.treeview_menu.post(event.x_root, event.y_root)

    def select_all(self, event):
        selected_items = self.treeview.selection()
        all_items = self.treeview.get_children()
        
        if len(selected_items) == len(all_items):
            self.treeview.selection_remove(*selected_items)
            self.treeview.see(self.treeview.get_children()[0])
        else:
            self.treeview.selection_set(*all_items)
            self.treeview.see(self.treeview.get_children()[-1])

    def remove_selected_items(self):
        selected_items = self.treeview.selection()
        for item in selected_items:
            self.treeview.delete(item)

    def get_treeview(self):
        return self.treeview


class popupWindow(object):
    def __init__(self, master, title="popupWindow"):
        self.exit_result = False
        self.popup=tk.Toplevel(master)
        self.popup.grab_set()
        self.popup.attributes("-topmost", 1)
        self.popup.title(title)
        self.popup.protocol("WM_DELETE_WINDOW", self.on_popup_close)

    def initial_position(self, master):
        ## Popup position
        master_x        = master.winfo_x()
        master_y        = master.winfo_y()
        master_width    = master.winfo_width()
        master_height   = master.winfo_height()
        popup_width     = self.popup.winfo_width()
        popup_height    = self.popup.winfo_height()

        popup_x = master_x + (master_width - popup_width) // 2
        popup_y = master_y + (master_height - popup_height) // 2
        self.popup.geometry(f"+{popup_x}+{popup_y}")

    def create_input_field(self, label_text, var, row, column, width=None):
        label = ttk.Label(self.popup, text=label_text)
        label.grid(row=row, column=column, padx=5, pady=5, sticky="e")

        entry = ttk.Entry(self.popup, textvariable=var, width=width)
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
        self.refresh_window_status()

    def create_ui(self):
        connection_mode_label = ttk.Label(self.popup, text="OS Connection mode:")
        connection_mode_ssh = ttk.Radiobutton(self.popup, text="SSH",
                                              variable=self.os_connection_mode_var,
                                              value="SSH",
                                              command=self.refresh_window_status)

        connection_mode_telnet = ttk.Radiobutton(self.popup,
                                                 text="Telnet",
                                                 variable=self.os_connection_mode_var,
                                                 value="Telnet",
                                                 command=self.refresh_window_status)

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


    def refresh_window_status(self):
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
        
        self.schedule       = tk.DoubleVar(value=ping_config["schedule_sec"])
        self.packet_count   = tk.DoubleVar(value=ping_config["packet_count"])
        self.interval       = tk.DoubleVar(value=ping_config["interval"])
        self.timeout        = tk.DoubleVar(value=ping_config["timeout"])

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

class popupWindow_SCP_Setting(popupWindow):
    def __init__(self, master, scp_config: dict):
        super().__init__(master, "SCP Setting")
        self.scp_config = scp_config
        
        self.storage_folder = tk.StringVar(value=scp_config["storage_folder"])

        ## Create UI
        self.create_ui()

        ## Popup position
        self.initial_position(master)

    def create_ui(self):
        self.create_input_field("Storage Folder:", self.storage_folder, 0, 0, 50)

        table_title = ttk.Label(self.popup,
                                text="Variable Table:",
                                style="my.TLabel")
        table_title.grid(row=1, column=0, padx=5, pady=5)

        table_frame = ttk.Frame(self.popup)
        table_frame.grid(row=2, column=0, columnspan=3, padx=10, pady=0, sticky=tk.W)

        self.variable_treeview = ttk.Treeview(table_frame, selectmode="extended", style="my.Treeview", height=10)

        self.variable_treeview["columns"] = ("variable", "value")
        self.variable_treeview.column("variable", width=150, minwidth=150, stretch=True, anchor="center")
        self.variable_treeview.column("value",    width=300, minwidth=300, stretch=True, anchor="center")

        self.variable_treeview["show"] = "headings"
        self.variable_treeview.heading('variable', text="Variable")
        self.variable_treeview.heading('value', text="Value")
        self.variable_treeview.pack(expand=1, fill=tk.BOTH, pady=0)

        self.variable_treeview.tag_configure("readonly", background="lightgray")
        self.variable_treeview.tag_configure("lock")

        ## initial treeview values
        for key, value in self.scp_config["variables"].items():
            self.variable_treeview.insert("", "end", values=(key, value["value"]), tags=value["tags"])

        ## event handel binding 
        def validate_input(input_field, input_text):
            def validate_variable_name(text):
                l = [self.variable_treeview.set(item)["variable"] 
                        for item in self.variable_treeview.get_children('')]
                if not text:
                    return False, "Variable name cannot be empty!"
                if text in l:
                    return False, "Variable name already exists."
                return True, ""

            if input_field == "Variable":
                return validate_variable_name(input_text)
            return True, ""

        def edit_treeview_item(event):
            item = self.variable_treeview.identify_row(event.y)
            column = self.variable_treeview.identify_column(event.x)
            
            if 'readonly' in self.variable_treeview.item(item, "tags"):
                return
            if item:
                self.variable_treeview.item(item, tags=('lock',))

                validate_callback = validate_input
                entryPopup = TreeviewEditEntry(self.variable_treeview, item, column, validate_callback)

                self.popup.wait_window(entryPopup.edit_entry)
                new_text = entryPopup.input_txt
                if entryPopup.exit_result:
                    self.variable_treeview.set(item, column, value=new_text)
                self.variable_treeview.item(item, tags=())

        def remove_selected_items():
            selected_items = self.variable_treeview.selection()
            for item in selected_items:
                if 'readonly' in self.variable_treeview.item(item, "tags"):
                    continue
                if 'lock' in self.variable_treeview.item(item, "tags"):
                    continue
                self.variable_treeview.delete(item)

        def add_variable_treeview_item():
            input_field_dict = {"Variable": tk.StringVar(), "Value": tk.StringVar()}
            popupWin = popupWindow_input_fields(self.variable_treeview,
                                                "Add Item",
                                                input_field_dict=input_field_dict,
                                                validate_callback=validate_input)
            self.popup.wait_window(popupWin.popup)

            new_item = (*popupWin.input_field_dict.values(),)
            if popupWin.exit_result and new_item:
                self.variable_treeview.insert("", "end", values=new_item)

        callback_dict = {"<Double-1>": edit_treeview_item, "<Delete>": lambda event: remove_selected_items()}
        menu_callback_dict = {"Add": add_variable_treeview_item, "Remove": remove_selected_items}
        myTreeviewBindSetter(self.variable_treeview, callback_dict, menu_callback_dict).binding()

        ## Submit Button
        submit_button = ttk.Button(self.popup, text="Submit", command=self.save_configuration)
        submit_button.grid(row=3, column=0, columnspan=2, padx=5, pady=5)

    def save_configuration(self):
        storage_folder = os.path.abspath(self.storage_folder.get())
        if not os.path.isdir(storage_folder):
            messagebox.showerror("Error", f"'{storage_folder}' is not a folder.", parent=self.popup)
            return

        self.scp_config = {"storage_folder": self.storage_folder.get()}

        result_dict = {}
        for row in self.variable_treeview.get_children():
            key = self.variable_treeview.item(row, "values")[0]
            value = self.variable_treeview.item(row, "values")[1]
            tags = self.variable_treeview.item(row, "tags")
            result_dict[key] = {"value": value, "tags": tags}

        self.scp_config["variables"] = result_dict

        self.save_and_exit()


class popupWindow_SCP(popupWindow):
    ## record last time combobox index
    COMBOBOX_IDX = {"download": 0, "upload": 0}

    def __init__(self, master, action, folder_path):
        super().__init__(master, "Select a config")
        self.target_config = None
        self.config_list = self.get_config_file_list(folder_path, action)
        self.action = action

        ## Create UI
        self.create_ui()

        ## Popup position
        self.initial_position(master)

    def get_config_file_list(self, folder_path, action):
        file_pattern = f"^{action}.*\.json$"
        return [os.path.splitext(file)[0] for file in os.listdir(folder_path) if re.match(file_pattern, file)]

    def on_combobox_keyrelease(self, event):
        # 获取用户输入
        user_input = self.combo_box.get()
        filtered_configs = [config for config in self.config_list if user_input.lower() in config.lower()]
        self.combo_box["values"] = filtered_configs


    def create_ui(self):
        config_label = ttk.Label(self.popup, text="Config:")
        config_label.grid(row=0, column=0, padx=5, pady=5)
        self.combo_box = ttk.Combobox(self.popup,
                    width=25,
                    values=self.config_list,
                    font=("微軟正黑體", 12))

        self.combo_box.bind("<KeyRelease>", self.on_combobox_keyrelease)
        self.combo_box.bind('<Return>', lambda event: self.combo_box.event_generate('<Down>'))
        if len(self.config_list):
            self.combo_box.current(popupWindow_SCP.COMBOBOX_IDX[self.action])
        self.combo_box.grid(row=0, column=1, padx=5, pady=5)

        submit_button = ttk.Button(self.popup, text="Submit", command=self.save_configuration)
        submit_button.grid(row=1, column=0, columnspan=2, padx=5, pady=5)

    def save_configuration(self):
        self.target_config = self.combo_box.get()
        popupWindow_SCP.COMBOBOX_IDX[self.action] = self.combo_box.current()
        self.save_and_exit()

class popupWindow_input_fields(popupWindow):
    """Generate the simple input fields type popup window"""
    def __init__(self, master, title="Input Fields", input_field_dict={}, validate_callback=None):
        super().__init__(master, title)
        
        self.input_field_dict = input_field_dict

        for k, v in input_field_dict.items():
            setattr(self, k, v)

        self.validate_callback = validate_callback

        ## Create UI
        self.create_ui()

        ## Popup position
        self.initial_position(master)

    def create_ui(self):
        for i, k in enumerate(self.input_field_dict):
            self.create_input_field(f"{k}:", getattr(self, k), i, 0)

        submit_button = ttk.Button(self.popup, text="Submit", command=self.save_configuration)
        submit_button.grid(row=3, column=0, columnspan=2, padx=5, pady=5)

    def validate_input(self, input_field, input_text):
        if self.validate_callback:
            return self.validate_callback(input_field, input_text)
        return True, ""

    def save_configuration(self):

        for k in self.input_field_dict:
            res, msg = self.validate_input(k, getattr(self, k).get())
            if not res:
                messagebox.showerror("Error", f"Invalid {k}:{msg} !", parent=self.popup)
                return

        self.input_field_dict = {k: getattr(self, k).get() for k in self.input_field_dict}

        self.save_and_exit()


class popupWindow_Cmd_Operation(popupWindow):
    def __init__(self, master, action="Add", config_value={}, validate_callback=None):
        super().__init__(master, f"{action} Cmds")

        self.config_value = config_value

        self.action = action
        self.validate_callback = validate_callback
        ## Create UI
        self.create_ui()

        ## Popup position
        self.initial_position(master)

    def create_ui(self):
        Op_label = ttk.Label(self.popup, text="Operation Label:")
        Op_label.pack(padx=5, pady=5)
        self.entry = ttk.Entry(self.popup, width=40)
        self.entry.insert(tk.END, self.config_value.get("label", ""))
        self.entry.pack(padx=5, pady=5)

        label = ttk.Label(self.popup, text="Enter Cmds:")
        label.pack(padx=5, pady=5)

        self.text = tk.Text(self.popup,
                            wrap="word",
                            background="White",
                            height=10,
                            width=70,
                            font=("微軟正黑體", 12))
        self.text.pack(padx=5, pady=5, fill="both", expand=True)
        if self.action == "Edit":
            self.text.insert(tk.END, self.config_value.get("text", ""))

        submit_button = ttk.Button(self.popup, text=f"{self.action}", command=self.save_configuration)
        submit_button.pack(padx=5, pady=5)

    def validate_input(self, input_field, input_text):
        if self.validate_callback:
            return self.validate_callback(input_field, input_text)
        return True, ""

    def save_configuration(self):
        cmd_str_list = str(self.text.get("1.0", "end-1c")).splitlines()
        cmd_str_list = [cmd_str.strip() for cmd_str in cmd_str_list if cmd_str.strip()]
        config_value = {"label": str(self.entry.get()), "text": '\n'.join(cmd_str_list)}
        for k in config_value:
            res, msg = self.validate_input(k, config_value.get(k))
            if not res:
                messagebox.showerror("Error", msg, parent=self.popup)
                return

        if not config_value.get("label"):
            config_value["label"] = cmd_str_list[0]

        self.config_value = config_value
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
        self.scp_config = {"storage_folder": "storage", "variables":
        {
            "IP": {"value": "<Scan table 'IP' value.>", "tags": ['readonly']},
            "MAC": {"value": "<Scan table 'MAC' value>", "tags": ['readonly']},
            "MODEL": {"value": "<Scan table 'Model' value>", "tags": ['readonly']}
        }}

        ## for OS cmd
        self.default_OS_cmd_timeout_sec = 10
        self.default_LGW_cmd_timeout_sec = 15

        ## Lock
        self.text_output_lock = threading.Lock()
        self.scan_treeview_lock = threading.Lock()
        self.ping_btn_lock = threading.Lock()

        self.process_threads = {}

        ## for Ping
        self.is_pinging = False
        self.ping_config = {"packet_count": 1, "schedule_sec": 1, "interval": 0.3, "timeout": 1}
        self.ping_counter = 0
        self.ping_items = []

        self.initUI(theme=theme)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def on_closing(self):
        self.output_default_content()
        self.destroy()

    def is_thread_alive(self, key):
        return self.process_threads.get(key) and self.process_threads.get(key).is_alive()

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

        ## Widget Style
        self.style = ThemedStyle()

        # print(self.style.theme_names())
        self.style.theme_use(theme)

        ttk.Style().configure('my.TButton', font=('微軟正黑體', 12),
                                            focuscolor='none')
        # ttk.Style().map('my.TButton', foreground=[("active", "White")],
        #                               background=[("active", "#2a6cdd")])

        ttk.Style().configure('my.TLabel', font=('微軟正黑體', 12))

        ttk.Style().configure('my.TFrame', background='#282b30')

        ttk.Style().configure('my.TEntry', background="#2a6cdd",
                                           selectbackground='#2a6cdd',
                                           selectforeground='White')

        ttk.Style().map('my.TEntry', foreground=[("selected", "White")],
                                     background=[("active", "#2a6cdd")])

        ttk.Style().configure('my.TNotebook', font=('微軟正黑體', 12),
                                            focuscolor='none')
        ## Title bar color
        # HWND = windll.user32.GetParent(self.winfo_id())
        # TITLE_BAR_COLOR = 0x00000000
        # windll.dwmapi.DwmSetWindowAttribute(HWND, 35,
        #                                     byref(c_int(TITLE_BAR_COLOR)),
        #                                     sizeof(c_int))

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
        self.load_default_content()

        self.refresh_window_status()

    def load_default_content(self):
        if SCP_Setting := cyl_util.load_config_json(os.path.join('recall','SCP_Setting.json')):
            self.scp_config = SCP_Setting

        if Scan_items := cyl_util.load_config_json(os.path.join('recall','Scan_items.json')):
            for item_info in Scan_items.get("scan_items"):
                text = item_info["text"]
                values = item_info["values"]
                self.scan_treeview.insert("", "end", text=text, values=values)

            self.OS_connection_mode = Scan_items.get("OS_connection_mode", self.OS_connection_mode)
            scan_network = Scan_items.get("scan_network", self.ip_range_entry.get())
            self.ip_range_entry.delete(0, tk.END)
            self.ip_range_entry.insert(tk.END, scan_network)
        # self.scp_config

        LGW_content = cyl_util.load_config_json(os.path.join('recall','LGW_Cmds.json'))
        OS_content = cyl_util.load_config_json(os.path.join('recall','OS_Cmds.json'))

        if LGW_content:
            for cmd_temp in LGW_content.get("operations", []):
                if not (commands := cmd_temp.get("commands")):
                    continue
                
                commands_str_list = []
                for cmd in commands:
                    cmd_str = cyl_util.make_cmd(cmd.pop("cmd"), **cmd)
                    if cyl_util.is_lgw_cmd_format(cmd_str):
                        commands_str_list.append(cmd_str)

                if not (label := cmd_temp.get("label")):
                    label = commands_str_list[0]
                commands_text = '\n'.join(commands_str_list)
                self.lgw_cmd_treeview.insert("", "end", values=(label,), text=commands_text)

            self.default_LGW_cmd_timeout_sec = LGW_content.get("timeout_sec", self.default_LGW_cmd_timeout_sec)
            self.lgw_cmd_timeout_entry.delete(0, tk.END)
            self.lgw_cmd_timeout_entry.insert(0, str(self.default_LGW_cmd_timeout_sec))
            if channels := LGW_content.get("channels"):
                self.channel_list_entry.delete(0, tk.END)
                self.channel_list_entry.insert(0, channels)

        if OS_content:
            for op in OS_content.get("operations", []):
                if not (commands := op.get("commands")):
                    continue
                if not (label := op.get("label")):
                    label = commands[0]

                commands_text = '\n'.join(commands)
                self.os_cmd_treeview.insert("", "end", values=(label,), text=commands_text)
            self.default_OS_cmd_timeout_sec = OS_content.get("timeout_sec", self.default_OS_cmd_timeout_sec)
            self.os_cmd_timeout_entry.delete(0, tk.END)
            self.os_cmd_timeout_entry.insert(0, str(self.default_OS_cmd_timeout_sec))


    def output_default_content(self):
        ## OS Cmds
        os_cmd_json = {"operations":[], "timeout_sec": int(self.os_cmd_timeout_entry.get())}
        for item in self.os_cmd_treeview.get_children():
            label = self.os_cmd_treeview.set(item, "operation")
            text = self.os_cmd_treeview.item(item, "text")
            os_cmd = {"label": label}
            os_cmd["commands"] = text.splitlines()
            os_cmd_json["operations"].append(os_cmd)
        
        ## LGW Cmds
        lgw_cmd_json = {"operations":[],
                        "channels": self.channel_list_entry.get(),
                        "timeout_sec": int(self.lgw_cmd_timeout_entry.get())}

        for item in self.lgw_cmd_treeview.get_children():
            label = self.lgw_cmd_treeview.set(item, "operation")
            text = self.lgw_cmd_treeview.item(item, "text")
            lgw_cmd = {"label": label}
            lgw_cmd["commands"] = [cyl_util.content9528_to_dict(cmd) for cmd in text.splitlines()]
            lgw_cmd_json["operations"].append(lgw_cmd)

        cyl_util.output_config_json(os_cmd_json, os.path.join('recall','OS_Cmds.json'))
        cyl_util.output_config_json(lgw_cmd_json, os.path.join('recall','LGW_Cmds.json'))
        cyl_util.output_config_json(self.scp_config, os.path.join('recall','SCP_Setting.json'))

        ## LGW Cmds
        scan_items_json = {"scan_network": self.ip_range_entry.get(),
                           "OS_connection_mode": self.OS_connection_mode,
                           "scan_items": []}

        for item in self.scan_treeview.get_children():
            item_data = self.scan_treeview.item(item)
            item_info = {
                "text": item_data["text"],
                "values": item_data["values"]
            }
            scan_items_json["scan_items"].append(item_info)

        cyl_util.output_config_json(scan_items_json, os.path.join('recall','Scan_items.json'))

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
        self.ip_range_entry.bind('<Return>', lambda event: self.btn_click_scan())


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
        # ttk.Style().configure("my.Treeview")
        # ttk.Style().map("my.Treeview",
        #         background=[("selected", "#2a6cdd")],
        #         foreground=[("selected", "white")])

        style_value = ttk.Style()
        style_value.configure("my.Treeview", rowheight=25, font=("微軟正黑體", 12))

        self.scan_treeview = ttk.Treeview(table_frame, selectmode="extended", style="my.Treeview", height=10)

        self.scan_treeview["columns"] = ("ip", "mac", "model-id", "ping", "os", "restart server", "restart network", "ota", "commit-id", "light gateway", "product-id(json)", "product-id")
        # self.scan_treeview["columns"] = ("ip", "mac", "model-id", "ping")
        self.scan_treeview.column("ip",         width=138, minwidth=138, stretch=True, anchor="center")
        self.scan_treeview.column("mac",        width=138, minwidth=138, stretch=True, anchor="center")
        self.scan_treeview.column("model-id",   width=138, minwidth=138, stretch=True, anchor="center")
        self.scan_treeview.column("ping",       width=138, minwidth=138, stretch=True, anchor="center")

        self.scan_treeview.column("os",                 width=0, minwidth=0, stretch=True, anchor="center")
        self.scan_treeview.column("restart server",     width=0, minwidth=0, stretch=True, anchor="center")
        self.scan_treeview.column("restart network",    width=0, minwidth=0, stretch=True, anchor="center")
        self.scan_treeview.column("ota",                width=0, minwidth=0, stretch=True, anchor="center")
        self.scan_treeview.column("commit-id",          width=0, minwidth=0, stretch=True, anchor="center")
        self.scan_treeview.column("light gateway",      width=0, minwidth=0, stretch=True, anchor="center")
        self.scan_treeview.column("product-id(json)",   width=0, minwidth=0, stretch=True, anchor="center")
        self.scan_treeview.column("product-id",         width=0, minwidth=0, stretch=True, anchor="center")


        self.scan_treeview["show"] = "headings"
        self.scan_treeview["displaycolumns"] = ("ip", "mac", "model-id", "ping")
        self.scan_treeview.heading('ip',        text="IP")
        self.scan_treeview.heading('mac',       text="MAC")
        self.scan_treeview.heading('model-id',  text="Model")
        self.scan_treeview.heading('ping',      text="Ping")
        
        self.scan_treeview.heading('os',               text="OS")
        self.scan_treeview.heading('restart server',   text="RS")
        self.scan_treeview.heading('restart network',  text="RN")
        self.scan_treeview.heading('ota',              text="OTA")
        self.scan_treeview.heading('commit-id',        text="FW")
        self.scan_treeview.heading('light gateway',    text="LGW")
        self.scan_treeview.heading('product-id(json)', text="PID(Json)")
        self.scan_treeview.heading('product-id',       text="PID")

        self.scan_treeview.pack(expand=1, fill=tk.BOTH, pady=0)
        self.scan_treeview.bind("<Double-1>", self.scan_treeview_db_click)

        def movement(action="Up"):
            selected_items = self.scan_treeview.selection()
            step = -1 if action == "Up" else 1
            if not selected_items:
                return 'break'
            if self.scan_treeview.index(selected_items[0])+step < 0 or self.scan_treeview.index(selected_items[-1])+step >= len(self.scan_treeview.get_children('')):
                return 'break'

            if action == "Down":
                selected_items = reversed(selected_items)
            for s in selected_items:
                self.scan_treeview.move(s, '', self.scan_treeview.index(s)+step)
            return 'break'
        self.scan_treeview.bind("<Shift-Up>",lambda event: movement("Up"))
        self.scan_treeview.bind("<Shift-Down>",lambda event: movement("Down"))

        ## scan_treeview_menu
        def remove_scan_treeview_item():
            selected_items = self.scan_treeview.selection()
            self.scan_treeview_lock.acquire()
            for item in selected_items:
                self.scan_treeview.delete(item)
            self.refresh_window_status()
            self.scan_treeview_lock.release()
    
        def add_scan_treeview_item():
            def validate_callback(input_field, input_text):
                if input_field == "IP":
                    if not cyl_util.is_valid_IP(input_text):
                        return False
                elif input_field == "MAC":
                    if input_text and not cyl_util.is_valid_MAC(input_text):
                        return False

                return True

            input_field_dict = {"IP": tk.StringVar(value="192.168."), "MAC": tk.StringVar(), "Model": tk.StringVar()}
            popupWin = popupWindow_input_fields(self, "Add Item", input_field_dict=input_field_dict, validate_callback=validate_callback)
            self.wait_window(popupWin.popup)

            new_item = (*popupWin.input_field_dict.values(), 0)
            self.scan_treeview_lock.acquire()
            if popupWin.exit_result and new_item:
                self.scan_treeview.insert("", "end", values=new_item)

            self.refresh_window_status()
            self.scan_treeview_lock.release()

        def clear_scan_treeview_item_text():
            selected_items = self.scan_treeview.selection()
            self.scan_treeview_lock.acquire()
            for item in selected_items:
                self.scan_treeview.item(item, text="")
            self.scan_treeview_lock.release()

        self.scan_treeview_menu = tk.Menu(self.scan_treeview, tearoff=0)
        self.scan_treeview_menu.add_command(label="Remove",
                                            command=remove_scan_treeview_item)
        self.scan_treeview_menu.add_command(label="Add",
                                            command=add_scan_treeview_item)
        self.scan_treeview_menu.add_command(label="Clear history",
                                            command=clear_scan_treeview_item_text)

        ## scan_treeview_ping_menu
        def join_ping(flag):
            """Let selected items join the ping process"""
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
                if not self.scan_treeview.selection():
                    self.scan_treeview.selection_set(item)
            if self.is_thread_alive("Ping"):
                self.scan_treeview_ping_menu.post(event.x_root, event.y_root)
            else:
                self.scan_treeview_menu.post(event.x_root, event.y_root)

        self.scan_treeview.bind("<Button-3>", show_scan_treeview_menu)

        def copy(event):
            """copy the selected item's values by 'ctrl+c'."""
            selected_items = self.scan_treeview.selection() # get selected items
            self.clipboard_clear()  # clear clipboard
            # copy headers
            headings = self.scan_treeview["columns"]
            self.clipboard_append("\t".join(headings) + "\n")
            for item in selected_items:
                # retrieve the values of the row
                values = self.scan_treeview.item(item, 'values')
                values = [str(v) for v in values]
                # values.extend(*self.scan_treeview.item(item, 'values'))
                # append the values separated by \t to the clipboard
                self.clipboard_append("\t".join(values) + "\n")

        def select_all(event):
            selected_items = self.scan_treeview.selection()
            all_items = self.scan_treeview.get_children()
            
            self.scan_treeview_lock.acquire()
            if len(selected_items) == len(all_items):
                self.scan_treeview.selection_remove(*selected_items)
                self.scan_treeview.see(self.scan_treeview.get_children()[0])
            else:
                self.scan_treeview.selection_set(*all_items)
                self.scan_treeview.see(self.scan_treeview.get_children()[-1])
            self.scan_treeview_lock.release()

        self.scan_treeview.bind('<Control-c>', copy)
        self.scan_treeview.bind('<Control-a>', select_all)

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
                                 text="Get Device Info",
                                 style="my.TButton",
                                 command=self.btn_click_get_devices_info)
        self.ping_alive_button = ttk.Button(base_frame,
                                 text=f"Ping({self.ping_counter})",
                                 style="my.TButton",
                                 command=lambda: self.btn_click_toggle_ping())

        def popup_scp_setting_window():
            popupWin = popupWindow_SCP_Setting(self, self.scp_config)
            self.wait_window(popupWin.popup)
            if popupWin.exit_result:
                self.scp_config = popupWin.scp_config
            # print(self.scp_config)
            return popupWin.exit_result

        self.scp_option_button = ttk.Button(base_frame,
                                 text="SCP Setting",
                                 style="my.TButton",
                                 command=lambda: popup_scp_setting_window())
                                 
        self.upload_button = ttk.Button(base_frame,
                                 text="SCP Upload",
                                 style="my.TButton",
                                 command=lambda: self.btn_click_scp("upload"))
        self.download_button = ttk.Button(base_frame,
                                 text="SCP Download",
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
                                   font=("微軟正黑體", 12))
        scrollbar = ttk.Scrollbar(output_result_tab_frame, command=self.output_text.yview)
        self.output_text.config(yscrollcommand=scrollbar.set)
        ## set_word_boundaries
        # this first statement triggers tcl to autoload the library
        # that defines the variables we want to override.  
        self.output_text.tk.call('tcl_wordBreakAfter', '', 0) 
        # this defines what tcl considers to be a "word". For more
        # information see http://www.tcl.tk/man/tcl8.5/TclCmd/library.htm#M19
        self.output_text.tk.call('set', 'tcl_wordchars', '[\w:\-.:]')
        self.output_text.tk.call('set', 'tcl_nonwordchars', '[^\w:\-.:]')

        clear_output_button = ttk.Button(output_result_tab_frame,
                                         text="Clear Output",
                                         style="my.TButton",
                                         command=lambda: self.output_text.delete("1.0", "end"))

        ## Arrange Output and Result Tab
        clear_output_button.pack(side="bottom", padx=10, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.output_text.pack(fill="both", expand=True)

        tab_control.add(output_result_tab_frame, text="Output and Result")

        self.output_text.tag_configure("red", foreground="red", font=("微軟正黑體", 12, "italic"))
        self.output_text.tag_configure("history", foreground="#224581", font=("微軟正黑體", 12, "italic"))
        self.output_text.tag_configure("title", foreground="black", font=("微軟正黑體", 12, "bold"))
        self.output_text.tag_configure("progress", foreground="#fc7a18", font=("微軟正黑體", 12, "underline"))

        ## Input Cmd Tab
        input_cmd_tab_frame = ttk.Frame(tab_control)

        self.os_cmd_treeview = ttk.Treeview(input_cmd_tab_frame, columns=("operation"), style='my.Treeview')

        self.os_cmd_treeview["show"] = "headings"
        self.os_cmd_treeview.heading("operation", text="Operation Label")

        def os_cmds_validate_input(input_field, input_text):
            def validate_os_cmds(text):
                if not text:
                    return False, f"Unable to find any OS commands.!"

                return True, ""

            if input_field == "text":
                return validate_os_cmds(input_text)

            return True, ""

        os_cmds_callback_dict = {"<Double-1>": lambda event: self.edit_cmd_treeview_item(self.os_cmd_treeview, os_cmds_validate_input)}
        os_cmds_menu_callback_dict = {"Copy": lambda: self.copy_selected_items(self.os_cmd_treeview)}
        myTreeviewBindSetter(self.os_cmd_treeview, os_cmds_callback_dict, os_cmds_menu_callback_dict).binding()

        add_os_operation_button = ttk.Button(input_cmd_tab_frame,
                                        text="Add",
                                        style="my.TButton",
                                        command=lambda :self.btn_click_cmd_operation_add_item(self.os_cmd_treeview, os_cmds_validate_input))

        send_button = ttk.Button(input_cmd_tab_frame,
                                 text="Send OS Cmd",
                                 style="my.TButton",
                                 command=self.btn_click_send_OS_command)

        timeout_label = ttk.Label(input_cmd_tab_frame, text="Timeout (sec):")
        self.os_cmd_timeout_entry = ttk.Entry(input_cmd_tab_frame, width=10)
        self.os_cmd_timeout_entry.insert(0, str(self.default_OS_cmd_timeout_sec))

        ## Arrange Input Cmd Tab
        self.os_cmd_treeview.pack(expand=1, fill="both", padx=10, pady=5)
        add_os_operation_button.pack(side="right", padx=10, pady=5)
        send_button.pack(side="right", padx=10, pady=5)
        self.os_cmd_timeout_entry.pack(side="right", padx=10, pady=5)
        timeout_label.pack(side="right", padx=10, pady=5)

        tab_control.add(input_cmd_tab_frame, text="OS Cmd")

        ## lgw Cmd Tab
        lgw_cmd_tab_frame = ttk.Frame(tab_control)
        self.lgw_cmd_treeview = ttk.Treeview(lgw_cmd_tab_frame, columns=("operation"), style='my.Treeview')

        self.lgw_cmd_treeview["show"] = "headings"
        self.lgw_cmd_treeview.heading("operation", text="Operation Lable")


        def lgw_cmds_validate_input(input_field, input_text):
            def validate_lgw_cmds(text):
                if not text:
                    return False, f"Unable to find any LGW commands.!"

                error_cmds = [cmd for cmd in str(text).splitlines() if not cyl_util.is_lgw_cmd_format(cmd)]
                if error_cmds:
                    error_cmds_msg = "\n".join(error_cmds)
                    return False, f"Invalid LGW Commands:\n{error_cmds_msg}"
                return True, ""

            if input_field == "text":
                return validate_lgw_cmds(input_text)

            return True, ""

        lgw_cmds_callback_dict = {"<Double-1>": lambda event: self.edit_cmd_treeview_item(self.lgw_cmd_treeview, lgw_cmds_validate_input)}
        lgw_cmds_menu_callback_dict = {"Copy": lambda: self.copy_selected_items(self.lgw_cmd_treeview)}
        myTreeviewBindSetter(self.lgw_cmd_treeview, lgw_cmds_callback_dict, lgw_cmds_menu_callback_dict).binding()

        add_button = ttk.Button(lgw_cmd_tab_frame,
                                text="Add",
                                style="my.TButton",
                                command=lambda :self.btn_click_cmd_operation_add_item(self.lgw_cmd_treeview, lgw_cmds_validate_input))
        
        send_button = ttk.Button(lgw_cmd_tab_frame,
                                 text="Send LGW Cmd",
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

    def copy_selected_items(self, treeview):
        selected_items = treeview.selection()
        for item in selected_items:
            item_data = treeview.item(item)
            treeview.insert("", "end", **item_data) 

    def edit_cmd_treeview_item(self, treeview, validate_callback=None):
        selected_item = treeview.selection()
        if selected_item:
            label = treeview.set(selected_item)["operation"]
            old_text = treeview.item(selected_item,"text")
            popupWin = popupWindow_Cmd_Operation(self, "Edit", config_value={"label": label, "text": old_text}, validate_callback=validate_callback)
            self.wait_window(popupWin.popup)
            if popupWin.exit_result:
                config_value = popupWin.config_value
                treeview.item(selected_item, values=(config_value['label'],), text=config_value['text'])

    def btn_click_cmd_operation_add_item(self, treeview, validate_callback=None):
        popupWin = popupWindow_Cmd_Operation(self, validate_callback=validate_callback)
        self.wait_window(popupWin.popup)
        if popupWin.exit_result:
            config_value = popupWin.config_value
            treeview.insert("", "end", values=(config_value["label"],), text=config_value["text"])

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
            cmd_list = []
            for item in selected_cmd_items:
                input_command = self.lgw_cmd_treeview.item(item, "text")
                cmd_list += input_command.splitlines()

            print(cmd_list)
            hosts = [self.scan_treeview.set(item) for item in selected_items]
            res = asyncio.run(cyl_async_telnet.send_telnet_9528cmds(hosts,
                                                                    cmd_template_list=cmd_list,
                                                                    channel_list=channel_list,
                                                                    timeout=timeout_sec))
            self.output_text_insert(f"Send LGW Cmds finish!!!\n", "progress")
            # print(res)
            ## show
            self.output_text_insert(f"\nSend LGW Cmd:", "title")
            for item in selected_items:
                device = self.scan_treeview.set(item)
                ip = device["ip"]
                cmd_result_list = [cmd_return["result"] for cmd_return in res[ip]]
                title = f"{device['model-id']}\t{device['mac']}\t({device['ip']})"
                self.output_text_insert(f"\n{title}", "title")

                res_text = ""
                for cmd_res in cmd_result_list:
                    text_tag = "red" if not cmd_res[0] else None

                    lgw_response_list = []
                    cmd_res_txt = f"{cmd_res[0]}\t{cmd_res[1]}"
                    if cmd_res[1].get("cmd"):
                        other_list = []
                        if others := cmd_res[1].pop("other"):
                            for oth in others:
                                other_list.append(cyl_util.make_cmd(oth.pop("cmd"), **oth))
                        
                        lgw_response_list.append(cyl_util.make_cmd(cmd_res[1].pop("cmd"), **cmd_res[1]))
                        lgw_response_list += other_list
                        lgw_response = ''.join(lgw_response_list)
                        cmd_res_txt = f"{cmd_res[0]}\t{lgw_response}"
                    self.output_text_insert(cmd_res_txt, text_tag)
                    res_text += f"{cmd_res_txt}\n"

                item_text = f"LGW Response:\n{res_text}"
                ## update item history
                self.update_history_text(item, item_text)


        self.output_text_insert(f"\nSend LGW Cmds start...", "progress")
        self.process_threads["Send LGW Cmd"] = threading.Thread(target=send_lgw_commands)
        self.process_threads["Send LGW Cmd"].daemon = True
        self.process_threads["Send LGW Cmd"].start()

    def btn_click_send_OS_command(self):
        selected_items = self.scan_treeview.selection()
        if not selected_items:
            messagebox.showerror("Error", "No devices have been selected.", parent=self)
            return

        selected_cmd_items = self.os_cmd_treeview.selection()
        if not selected_cmd_items:
            messagebox.showerror("Error", "No commands have been selected.", parent=self)
            return

        timeout_sec = self.os_cmd_timeout_entry.get()
        if timeout_sec and not cyl_util.is_float(timeout_sec):
            messagebox.showerror("Error", "timeout value must be float or keep it empty for waiting forever.", parent=self)
            return

        timeout_sec = None if timeout_sec == "" else float(timeout_sec)

        def send_OS_commands():
            cmd_list = []
            for item in selected_cmd_items:
                input_command = self.os_cmd_treeview.item(item, "text")
                cmd_list += input_command.splitlines()

            print(cmd_list)
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
            self.output_text_insert(f"Send OS Cmds finish!!!\n", "progress")
            txt_bar = '----------------------'
            ## show
            self.output_text_insert(f"\nSend OS Cmd:", "title")
            for item in selected_items:
                device = self.scan_treeview.set(item)
                ip = device["ip"]
                cmd_result_list = [cmd_return["result"] for cmd_return in res[ip]]
                title = f"{device['model-id']}\t{device['mac']}\t({device['ip']})"
                self.output_text_insert(f"\n{title}", "title")

                res_text = ""
                for cmd_res in cmd_result_list:
                    text_tag = "red" if not cmd_res[0] else None
                    cmd_res_txt = f"{txt_bar}{cmd_res[0]}{txt_bar}\n{cmd_res[1]}"
                    self.output_text_insert(cmd_res_txt, text_tag)
                    res_text += f"{cmd_res_txt}\n"

                item_text = f"OS Response:\n{res_text}"
                ## update item history
                self.update_history_text(item, item_text)

        self.output_text_insert(f"\nSend OS Cmds start...", "progress")
        self.process_threads["Send OS Cmd"] = threading.Thread(target=send_OS_commands)
        self.process_threads["Send OS Cmd"].daemon = True
        self.process_threads["Send OS Cmd"].start()


    def btn_click_scan(self):

        alive_process_list = [process for process, thread in self.process_threads.items() if thread.is_alive()]
        if alive_process_list:
            messagebox.showerror("Warning", f"The processes in\n{alive_process_list}\nare running.\nPlease either stop them or wait for them to complete.", parent=self)
            return

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
        self.output_text_insert(f"\nScan devices start...", "progress")
        self.disableChildren(self.ip_scan_frame)
        self.scan_treeview_lock.acquire()
        ## clear treeview
        for item in self.scan_treeview.get_children():
            self.scan_treeview.delete(item)
        self.scan_treeview_lock.release()
        self.refresh_window_status()

        ## Scan by thread
        self.process_threads["scan_devices"] = threading.Thread(target=self.scan_devices, args=(target_networks,))
        self.process_threads["scan_devices"].daemon = True
        self.process_threads["scan_devices"].start()

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

    def get_devices_info(self, hosts):
        ## OS, RS, RN, OTA
        cmd_dict = {"os": "cat /etc/os_version",
                    "restart server": "cat /root/restart_server.sh|grep -Eom 1 'v[0-9]+\.[0-9]+\.[0-9]+'",
                    "restart network": "cat /root/restart_network.sh|grep -Eom 1 'v[0-9]+\.[0-9]+\.[0-9]+'",
                    "ota": "cat /root/ota.sh|grep -Eom 1 'v[0-9]+\.[0-9]+\.[0-9]+'",
                    "mac": "flash get HW_NIC1_ADDR | cut -d '=' -f 2"}
        
        self.output_text_insert(f"\nGet devices info start...", "progress")
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

        device_info_dict={}
        for host in hosts:
            ip = host['ip']
            device_info = {}
            for i, cmd_return in enumerate(res[ip]):
                key = list(cmd_dict.keys())[i]
                device_info[key] = MyApp.OS_out_version_result_filter(cmd_return["result"])
                if key == "mac" and not cyl_util.is_valid_MAC(host['mac']):
                    host["mac"] = device_info[key]
            device_info_dict[ip] = device_info

        cmd_template_list = []
        tid = cyl_util.make_target_id("", 0)
        cmd_template_list.append(cyl_util.make_cmd("read-attr", target_id=tid, attr="model-id"))
        cmd_template_list.append(cyl_util.make_cmd("read-attr", target_id=tid, attr="commit-id"))
        cmd_template_list.append(cyl_util.make_cmd("configure"))
        cmd_template_list.append(cyl_util.make_cmd("read-attr", target_id=tid, attr="product-id"))
        res = asyncio.run(cyl_async_telnet.send_telnet_9528cmds(hosts, cmd_template_list=cmd_template_list))

        for host in hosts:
            ip = host['ip']
            result = res[ip]
            device_info_dict[ip]["model-id"] = MyApp.telnet9528_out_result_filter(result[0]["result"], "value")
            device_info_dict[ip]["commit-id"] = MyApp.telnet9528_out_result_filter(result[1]["result"], "value")
            device_info_dict[ip]["os"] = MyApp.telnet9528_out_result_filter(result[2]["result"], "os-version")
            device_info_dict[ip]["light gateway"] = MyApp.telnet9528_out_result_filter(result[2]["result"], "server-version")
            device_info_dict[ip]["product-id(json)"] = MyApp.telnet9528_out_result_filter(result[2]["result"], "product-id")
            device_info_dict[ip]["product-id"] = MyApp.telnet9528_out_result_filter(result[3]["result"], "value")

        self.output_text_insert(f"Get devices info finish!!!\n", "progress")
        return device_info_dict

    def scan_devices(self, networks):

        hosts = asyncio.run(scanner.async_scan_networks(networks))

        device_info_dict = self.get_devices_info(hosts)
        # print(res)
        # print(hosts)
        ## Update treeview
        for host in hosts:
            ip = host['ip']
            mac = cyl_util.format_MAC(device_info_dict[ip]['mac'])
            if cyl_util.is_valid_MAC(mac):
                mac = cyl_util.format_MAC(device_info_dict[ip]['mac']).upper()
            if not cyl_util.is_valid_MAC(host['mac']):
                host['mac'] = mac
            item_values = (host['ip'], host['mac'],
                            device_info_dict[ip]["model-id"],
                            0,
                            device_info_dict[ip]["os"],
                            device_info_dict[ip]["restart server"],
                            device_info_dict[ip]["restart network"],
                            device_info_dict[ip]["ota"],
                            device_info_dict[ip]["commit-id"],
                            device_info_dict[ip]["light gateway"],
                            device_info_dict[ip]["product-id(json)"],
                            device_info_dict[ip]["product-id"])
            self.scan_treeview_lock.acquire()
            self.scan_treeview.insert("", "end", values=item_values)
            self.scan_treeview_lock.release()

        ## Enable ip scan frame
        self.enableChildren(self.ip_scan_frame)
        self.refresh_window_status()
        self.output_text_insert(f"Find {len(hosts)} devices.")
        self.output_text_insert(f"Scan devices finish!!!\n", "progress")

    @cyl_wrapper.setVar("reverse", False)
    def scan_treeview_db_click(self, event):
        region = self.scan_treeview.identify_region(event.x,event.y)

        if region == "nothing":
            self.scan_treeview_lock.acquire()
            self.scan_treeview.selection_remove(self.scan_treeview.selection())
            self.scan_treeview_lock.release()
        ## Sort
        elif region == "heading":
            col_id = self.scan_treeview.identify('column', event.x, event.y)

            rows = [(str(self.scan_treeview.set(item, col_id)).lower(), item)
                        for item in self.scan_treeview.get_children('')]

            rows.sort(reverse=self.scan_treeview_db_click.reverse)
            self.scan_treeview_db_click.__dict__["reverse"] ^= True

            for index, (values, item) in enumerate(rows):
                self.scan_treeview_lock.acquire()
                self.scan_treeview.move(item, '', index)
                self.scan_treeview_lock.release()

        ## Show history
        elif region == "cell":
            item = self.scan_treeview.identify('item', event.x, event.y)
            device = self.scan_treeview.set(item)
            text = self.scan_treeview.item(item,"text")

            title = f"{device['model-id']}\t{device['mac']}\t({device['ip']})"
            self.output_text_insert(f"\nHistory:\n{title}", "title")
            if text:
                self.output_text_insert(f"{text}", "history")

    
    def btn_click_get_devices_info(self):
        selected_items = self.scan_treeview.selection()
        if not selected_items:
            messagebox.showerror("Error", "No devices have been selected.", parent=self)
            return

        def get_devices_info():

            hosts = [self.scan_treeview.set(item) for item in selected_items]
            device_info_dict = self.get_devices_info(hosts)

            ## Update treeview
            for item in selected_items:
                host = self.scan_treeview.set(item)
                ip = host['ip']
                mac = cyl_util.format_MAC(device_info_dict[ip]['mac'])
                if cyl_util.is_valid_MAC(mac):
                    mac = cyl_util.format_MAC(device_info_dict[ip]['mac']).upper()
                if not cyl_util.is_valid_MAC(host['mac']):
                    host['mac'] = mac
                item_values = (host['ip'], host['mac'],
                                device_info_dict[ip]["model-id"],
                                host['ping'],
                                device_info_dict[ip]["os"],
                                device_info_dict[ip]["restart server"],
                                device_info_dict[ip]["restart network"],
                                device_info_dict[ip]["ota"],
                                device_info_dict[ip]["commit-id"],
                                device_info_dict[ip]["light gateway"],
                                device_info_dict[ip]["product-id(json)"],
                                device_info_dict[ip]["product-id"])
                self.scan_treeview_lock.acquire()
                self.scan_treeview.item(item, values=item_values)
                self.scan_treeview_lock.release()

            ## show
            self.output_text_insert(f"\nGet device info:", "title")
            for item in selected_items:
                device = self.scan_treeview.set(item)
                ip = device['ip']
                res_text = [f"{self.scan_treeview.heading(k, option='text')}\t{v}" for k, v in device_info_dict[ip].items()]
                res_text = '\n'.join(res_text)
                item_text = f"Device info:\n{res_text}"
                title = f"{device['model-id']}\t{device['mac']}\t({device['ip']})"
                self.output_text_insert(f"\n{title}", "title")
                self.output_text_insert(item_text)

                ## update item history
                self.update_history_text(item, item_text)


        self.process_threads["get_device_info"] = threading.Thread(target=get_devices_info)
        self.process_threads["get_device_info"].daemon = True
        self.process_threads["get_device_info"].start()


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
            if not self.is_thread_alive("Ping"):
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

                self.output_text_insert("\nPing start...", "progress")
                self.output_text_insert(f'Sends ({count}) packet(s) per ({interval}) sec, timeout:({timeout}) sec, schedule every ({schedule_sec}) sec.')
                self.process_threads["Ping"] = threading.Thread(target=ping_loop, args=(schedule_sec, count, interval, timeout))
                self.process_threads["Ping"].daemon = True
                self.is_pinging = True
                self.process_threads["Ping"].start()


        def stop_ping():
            if self.is_thread_alive("Ping"):
                self.is_pinging = False
                self.output_text_insert(f"Ping stop!!!\n", "progress")

                self.ping_btn_lock.acquire()
                self.ping_items = []
                self.ping_alive_button.config(text=f"Ping({self.ping_counter})")
                self.ping_btn_lock.release()

        if not self.is_thread_alive("Ping"):
            start_ping()
        else:
            stop_ping()

    def btn_click_scp(self, action):
        selected_items = self.scan_treeview.selection()
        if not selected_items:
            messagebox.showerror("Error", "No devices have been selected.", parent=self)
            return

        def popup_scp_setting_window(action):
            popupWin = popupWindow_SCP(self, action, self.scp_config.get("storage_folder", "storage"))
            self.wait_window(popupWin.popup)
            if popupWin.exit_result:
                self.scp_config["config_name"] = popupWin.target_config
            return popupWin.exit_result

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

        if not popup_scp_setting_window(action):
            return

        def do_scp(action, storage, config_name):
            remote_hosts = [self.scan_treeview.set(item) for item in selected_items]
            username = "root"
            password = self.ssh_password

            hosts_config_variables = {k: v["value"] for k, v in self.scp_config["variables"].items()}

            self.output_text_insert(f"\nSCP {action} start...", "progress")
            res = asyncio.run(cyl_async_ssh.scp_process(username, 
                                                        password,
                                                        remote_hosts,
                                                        action,
                                                        storage,
                                                        config_name,
                                                        hosts_config_variables))
            self.output_text_insert(f"SCP {action} finish!!!\n", "progress")
            # print(res)
            ## show
            self.output_text_insert(f"SCP {action}:", "title")
            for item in selected_items:
                device = self.scan_treeview.set(item)
                result = res[device["ip"]]
                item_text = f'SCP {action} result: {result}'
                title = f"{device['model-id']}\t{device['mac']}\t({device['ip']})"
                self.output_text_insert(f"\n{title}", "title")
                text_tag = "red" if not result[0] else None
                self.output_text_insert(f"{item_text}", text_tag)

                ## update item history
                self.update_history_text(item, item_text)

        storage = self.scp_config.get("storage_folder", "storage")
        config_name = self.scp_config.get("config_name", "")

        self.process_threads[f"SCP {action}"] = threading.Thread(target=do_scp, args=(action, storage, config_name))
        self.process_threads[f"SCP {action}"].daemon = True
        self.process_threads[f"SCP {action}"].start()
    
    def refresh_window_status(self):
        if not self.scan_treeview.get_children(''):
            self.scp_option_button.configure(state='normal')
            self.configure_button.configure(state='normal')
            self.upload_button.configure(state='disabled')
            self.download_button.configure(state='disabled')
            self.ping_alive_button.configure(state='disabled')
            self.device_info_button.configure(state='disabled')
        else:
            self.ping_alive_button.configure(state='normal')
            self.device_info_button.configure(state='normal')
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