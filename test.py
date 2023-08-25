import os
import tkinter as tk
from tkinter import ttk


def load_files():
    file_pattern = ".json"
    files = [file for file in os.listdir('storage') if file.endswith(file_pattern)]
    combobox['values'] = files

# 创建主窗口
root = tk.Tk()
root.title("Combobox Example")

# 创建Combobox
combobox = ttk.Combobox(root, state="readonly")
combobox.pack()

# 创建按钮，点击按钮加载文件列表
load_button = tk.Button(root, text="Load Files", command=load_files)
load_button.pack()

# 启动Tkinter主循环
root.mainloop()
