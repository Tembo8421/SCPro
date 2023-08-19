import tkinter as tk
from tkinter import ttk


class CustomTreeview(ttk.Treeview):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Configure the style for selected items
        style = ttk.Style()
        style.configure("Custom.Treeview", background="blue", foreground="white")
        self.tag_configure("custom_selected", style="Custom.Treeview")

        self.bind("<ButtonRelease-1>", self.on_click)
        self.selected_item = None

    def on_click(self, event):
        item = self.identify_row(event.y)
        if item:
            if self.selected_item:
                self.item(self.selected_item, tags=("noeffect",))
            self.item(item, tags=("custom_selected",))
            self.selected_item = item

root = tk.Tk()
root.title("Custom Treeview")

tree = CustomTreeview(root, columns=("Column1", "Column2"), show="headings")
tree.heading("Column1", text="Column 1")
tree.heading("Column2", text="Column 2")

data = [
    ("Data 1", "Data 2"),
    ("Data 3", "Data 4"),
    ("Data 5", "Data 6"),
    ("Data 7", "Data 8"),
]

for item in data:
    tree.insert("", "end", values=item)

tree.pack()

root.mainloop()
