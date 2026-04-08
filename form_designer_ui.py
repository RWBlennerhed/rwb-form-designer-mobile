import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog
from tkinter import ttk
import json

# ------------------------------------------------------------
# RWB Form Designer v1.7.4
# A mobile-friendly form designer for Tkinter
#
# Created by Robert William Blennerhed
# Developed in close collaboration with ChatGPT
#
# This project is part of RWB Tech Lab and reflects a
# creative collaboration between Robert William Blennerhed
# and ChatGPT.
#
# Robert contributes the original vision, practical ideas,
# usability thinking, testing, and design direction.
# ChatGPT contributes structure, implementation support,
# refinement, logic, translations, and code development.
#
# Together, this project represents a unique human + AI
# teamwork process focused on practical Python tools,
# simplicity, creativity, and real-world usability.
# ------------------------------------------------------------

WINDOW_W = 420
WINDOW_H = 760

next_x = 20
next_y = 20
STEP = 0

MIN_W = 100
MAX_W = 800
MIN_H = 25
MAX_H = 240
RESIZE_STEP = 20

MAX_COMPONENTS = 30

SNAP_TO_GRID = False
GRID_SIZE = 10

placed_components = []
selected_comp = None
selection_box = None
resize_handle = None

# Simple undo: only the last action
last_action = None

drag_data = {
    "widget": None,
    "start_x": 0,
    "start_y": 0,
    "orig_x": 0,
    "orig_y": 0,
    "moved": False
}

resize_data = {
    "active": False,
    "start_x": 0,
    "start_y": 0,
    "orig_w": 0,
    "orig_h": 0,
    "resized": False
}


# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------

def snap_value(value):
    if SNAP_TO_GRID:
        return round(value / GRID_SIZE) * GRID_SIZE
    return value


def toggle_snap_to_grid():
    global SNAP_TO_GRID
    SNAP_TO_GRID = not SNAP_TO_GRID
    update_status()


def overlaps(x1, y1, w1, h1, x2, y2, w2, h2):
    return not (
        x1 + w1 <= x2 or
        x1 >= x2 + w2 or
        y1 + h1 <= y2 or
        y1 >= y2 + h2
    )


def find_comp_for_widget(widget):
    for comp in placed_components:
        if comp["widget"] == widget:
            return comp
    return None


def update_status():
    if selected_comp is None:
        status_info.config(
            text=f"Selected: None   X: -   Y: -   Snap: {'On' if SNAP_TO_GRID else 'Off'}"
        )
    else:
        comp_type = selected_comp["type"]
        x = selected_comp["x"]
        y = selected_comp["y"]
        status_info.config(
            text=f"Selected: {comp_type}   X: {x}   Y: {y}   Snap: {'On' if SNAP_TO_GRID else 'Off'}"
        )


def clear_status():
    status_info.config(
        text=f"Selected: None   X: -   Y: -   Snap: {'On' if SNAP_TO_GRID else 'Off'}"
    )


def update_selection_box():
    global selection_box, selected_comp, resize_handle

    if selection_box is None:
        return

    if selected_comp is None:
        selection_box.place_forget()
        if resize_handle is not None:
            resize_handle.place_forget()
        return

    x = selected_comp["x"] - 2
    y = selected_comp["y"] - 2
    w = selected_comp["w"] + 4
    h = selected_comp["h"] + 4

    selection_box.place(x=x, y=y, width=w, height=h)

    # Keep selection frame behind the widget so it does not block clicks
    selection_box.lower()

    if resize_handle is not None:
        hx = selected_comp["x"] + selected_comp["w"] - 8
        hy = selected_comp["y"] + selected_comp["h"] - 8
        resize_handle.place(x=hx, y=hy, width=16, height=16)
        resize_handle.lift()


def select_component(comp):
    global selected_comp
    selected_comp = comp
    update_selection_box()
    update_status()


def free_space_for_drag(test_x, test_y, current_comp):
    w = current_comp["w"]
    h = current_comp["h"]

    if test_x < 0 or test_y < 0:
        return False

    if test_x + w > canvas.winfo_width():
        return False

    if test_y + h > canvas.winfo_height():
        return False

    for comp in placed_components:
        if comp is current_comp:
            continue

        if overlaps(test_x, test_y, w, h, comp["x"], comp["y"], comp["w"], comp["h"]):
            return False

    return True


def size_ok(comp, new_w, new_h):
    if new_w < MIN_W or new_w > MAX_W:
        return False

    if new_h < MIN_H or new_h > MAX_H:
        return False

    if comp["x"] + new_w > canvas.winfo_width():
        return False

    if comp["y"] + new_h > canvas.winfo_height():
        return False

    for other in placed_components:
        if other is comp:
            continue

        if overlaps(comp["x"], comp["y"], new_w, new_h,
                   other["x"], other["y"], other["w"], other["h"]):
            return False

    return True


def esc_text(s):
    if s is None:
        return ""
    return str(s).replace("\\", "\\\\").replace('"', '\\"')


def create_event_name(comp_type, index):
    name = comp_type.lower()
    return f"{name}{index}_event"


def safe_items_to_text(items):
    return "|".join(str(x) for x in items)


def component_to_dict(comp):
    return {
        "type": comp["type"],
        "x": comp["x"],
        "y": comp["y"],
        "w": comp["w"],
        "h": comp["h"],
        "text": get_component_text(comp)
    }


def find_next_free_position(default_w=140, default_h=40):
    margin = 20
    step_x = 20
    step_y = 20

    canvas.update_idletasks()
    max_w = canvas.winfo_width()
    max_h = canvas.winfo_height()

    y = margin
    while y + default_h <= max_h:
        x = margin
        while x + default_w <= max_w:
            occupied = False

            for comp in placed_components:
                if overlaps(x, y, default_w, default_h,
                            comp["x"], comp["y"], comp["w"], comp["h"]):
                    occupied = True
                    break

            if not occupied:
                return x, y

            x += step_x
        y += step_y

    return margin, margin


def restore_component_from_dict(item):
    widget, _, _, extra = create_widget(canvas, item["type"])
    if widget is None:
        return None

    comp_type = item["type"]
    x = item["x"]
    y = item["y"]
    w = item["w"]
    h = item["h"]
    text = item.get("text", "")

    widget.place(x=x, y=y, width=w, height=h)
    connect_widget(widget, comp_type)

    if comp_type == "Panel" and extra.get("label_widget") is not None:
        connect_panel_label(extra["label_widget"], widget)

    comp = {
        "type": comp_type,
        "x": x,
        "y": y,
        "w": w,
        "h": h,
        "widget": widget,
        "text": text,
        "values": extra.get("values", None),
        "value": extra.get("value", None),
        "label_widget": extra.get("label_widget", None)
    }

    set_component_text(comp, text)
    return comp


def save_undo(action_type, data):
    global last_action
    last_action = {
        "type": action_type,
        "data": data
    }


def connect_panel_label(label_widget, parent_widget):
    label_widget.bind("<Button-1>", lambda e: parent_widget.event_generate("<Button-1>", x=e.x, y=e.y))
    label_widget.bind("<B1-Motion>", lambda e: parent_widget.event_generate("<B1-Motion>", x=e.x, y=e.y))
    label_widget.bind("<ButtonRelease-1>", lambda e: parent_widget.event_generate("<ButtonRelease-1>", x=e.x, y=e.y))


# ------------------------------------------------------------
# Get / set text
# ------------------------------------------------------------

def get_component_text(comp):
    widget = comp["widget"]
    comp_type = comp["type"]

    try:
        if comp_type in ["Label", "Button", "CheckBox", "RadioButton", "LabelFrame"]:
            return widget.cget("text")

        elif comp_type == "TextBox":
            return widget.get()

        elif comp_type == "TextArea":
            return widget.get("1.0", tk.END).rstrip("\n")

        elif comp_type == "ListBox":
            items = widget.get(0, tk.END)
            return safe_items_to_text(items)

        elif comp_type == "ComboBox":
            values = comp.get("values", ["One", "Two", "Three"])
            return safe_items_to_text(values)

        elif comp_type == "Scale":
            return str(widget.get())

        elif comp_type == "SpinBox":
            return widget.get()

        elif comp_type == "Panel":
            return comp.get("text", "Panel")

        elif comp_type == "ProgressBar":
            return str(comp.get("value", 40))

        elif comp_type == "Frame":
            return ""

        elif comp_type == "Canvas":
            return ""

    except Exception:
        pass

    return comp.get("text", "")


def set_component_text(comp, new_text):
    widget = comp["widget"]
    comp_type = comp["type"]

    try:
        if comp_type in ["Label", "Button", "CheckBox", "RadioButton", "LabelFrame"]:
            widget.config(text=new_text)
            comp["text"] = new_text

        elif comp_type == "TextBox":
            widget.delete(0, tk.END)
            widget.insert(0, new_text)
            comp["text"] = new_text

        elif comp_type == "TextArea":
            widget.delete("1.0", tk.END)
            widget.insert("1.0", new_text)
            comp["text"] = new_text

        elif comp_type == "ListBox":
            widget.delete(0, tk.END)
            parts = [p.strip() for p in new_text.split("|")]
            for item in parts:
                if item:
                    widget.insert(tk.END, item)
            comp["text"] = new_text

        elif comp_type == "ComboBox":
            parts = [p.strip() for p in new_text.split("|")]
            values = [p for p in parts if p]
            if not values:
                values = ["One", "Two", "Three"]
            widget["values"] = values
            widget.set(values[0])
            comp["values"] = values
            comp["text"] = safe_items_to_text(values)

        elif comp_type == "Scale":
            try:
                value = int(float(new_text))
            except Exception:
                value = 50
            widget.set(value)
            comp["text"] = str(value)

        elif comp_type == "SpinBox":
            widget.delete(0, tk.END)
            widget.insert(0, new_text)
            comp["text"] = new_text

        elif comp_type == "Panel":
            comp["text"] = new_text
            if comp["label_widget"] is not None:
                comp["label_widget"].config(text=new_text)

        elif comp_type == "ProgressBar":
            try:
                value = int(float(new_text))
            except Exception:
                value = 40
            value = max(0, min(100, value))
            widget["value"] = value
            comp["value"] = value
            comp["text"] = str(value)

    except Exception:
        pass


# ------------------------------------------------------------
# Selection / drag
# ------------------------------------------------------------

def on_widget_press(event):
    widget = event.widget
    comp = find_comp_for_widget(widget)
    if comp is None:
        return

    select_component(comp)

    drag_data["widget"] = widget
    drag_data["start_x"] = event.x_root
    drag_data["start_y"] = event.y_root
    drag_data["orig_x"] = comp["x"]
    drag_data["orig_y"] = comp["y"]
    drag_data["moved"] = False


def on_widget_drag(event):
    widget = drag_data["widget"]
    if widget is None:
        return

    comp = find_comp_for_widget(widget)
    if comp is None:
        return

    dx = event.x_root - drag_data["start_x"]
    dy = event.y_root - drag_data["start_y"]

    new_x = drag_data["orig_x"] + dx
    new_y = drag_data["orig_y"] + dy

    new_x = snap_value(new_x)
    new_y = snap_value(new_y)

    if free_space_for_drag(new_x, new_y, comp):
        widget.place(x=new_x, y=new_y, width=comp["w"], height=comp["h"])
        comp["x"] = new_x
        comp["y"] = new_y
        drag_data["moved"] = True
        update_selection_box()
        update_status()


def on_widget_release(event):
    widget = drag_data["widget"]
    if widget is None:
        return

    comp = find_comp_for_widget(widget)
    if comp is not None and drag_data["moved"]:
        old_x = drag_data["orig_x"]
        old_y = drag_data["orig_y"]
        new_x = comp["x"]
        new_y = comp["y"]

        if old_x != new_x or old_y != new_y:
            save_undo("move", {
                "comp": comp,
                "old_x": old_x,
                "old_y": old_y,
                "new_x": new_x,
                "new_y": new_y
            })

    drag_data["widget"] = None
    drag_data["moved"] = False


# ------------------------------------------------------------
# Resize handle
# ------------------------------------------------------------

def on_resize_press(event):
    if selected_comp is None:
        return "break"

    resize_data["active"] = True
    resize_data["start_x"] = event.x_root
    resize_data["start_y"] = event.y_root
    resize_data["orig_w"] = selected_comp["w"]
    resize_data["orig_h"] = selected_comp["h"]
    resize_data["resized"] = False

    root.bind_all("<B1-Motion>", on_resize_drag)
    root.bind_all("<ButtonRelease-1>", on_resize_release)

    return "break"


def on_resize_drag(event):
    if selected_comp is None:
        return "break"

    if not resize_data["active"]:
        return "break"

    dx = event.x_root - resize_data["start_x"]
    dy = event.y_root - resize_data["start_y"]

    new_w = resize_data["orig_w"] + dx
    new_h = resize_data["orig_h"] + dy

    new_w = snap_value(new_w)
    new_h = snap_value(new_h)

    if not size_ok(selected_comp, new_w, new_h):
        return "break"

    selected_comp["w"] = new_w
    selected_comp["h"] = new_h
    resize_data["resized"] = True

    selected_comp["widget"].place(
        x=selected_comp["x"],
        y=selected_comp["y"],
        width=selected_comp["w"],
        height=selected_comp["h"]
    )

    update_selection_box()
    update_status()

    return "break"


def on_resize_release(event):
    if selected_comp is not None and resize_data["active"] and resize_data["resized"]:
        old_w = resize_data["orig_w"]
        old_h = resize_data["orig_h"]
        new_w = selected_comp["w"]
        new_h = selected_comp["h"]

        if old_w != new_w or old_h != new_h:
            save_undo("resize", {
                "comp": selected_comp,
                "old_w": old_w,
                "old_h": old_h,
                "new_w": new_w,
                "new_h": new_h
            })

    resize_data["active"] = False
    resize_data["resized"] = False

    root.unbind_all("<B1-Motion>")
    root.unbind_all("<ButtonRelease-1>")

    return "break"


# ------------------------------------------------------------
# TextBox special
# ------------------------------------------------------------

def on_textbox_press(event):
    on_widget_press(event)
    return "break"


def textbox_double_click(event):
    widget = event.widget
    comp = find_comp_for_widget(widget)
    if comp is not None:
        select_component(comp)

    widget.focus_set()

    try:
        if isinstance(widget, tk.Entry):
            widget.icursor(tk.END)
    except Exception:
        pass

    return "break"


def connect_widget(widget, comp_type):
    if comp_type in ["TextBox", "TextArea"]:
        widget.bind("<Button-1>", on_textbox_press)
        widget.bind("<B1-Motion>", on_widget_drag)
        widget.bind("<ButtonRelease-1>", on_widget_release)
        widget.bind("<Double-Button-1>", textbox_double_click)
    else:
        widget.bind("<Button-1>", on_widget_press)
        widget.bind("<B1-Motion>", on_widget_drag)
        widget.bind("<ButtonRelease-1>", on_widget_release)


# ------------------------------------------------------------
# Create components
# ------------------------------------------------------------

def create_widget(parent, comp_type):
    if comp_type == "Label":
        widget = tk.Label(parent, text="Label", bg="white", relief="solid", bd=1)
        w, h = 100, 30
        extra = {"text": "Label", "label_widget": None}

    elif comp_type == "Button":
        widget = tk.Button(parent, text="Button")
        w, h = 110, 35
        extra = {"text": "Button", "label_widget": None}

    elif comp_type == "TextBox":
        widget = tk.Entry(parent)
        widget.insert(0, "TextBox")
        w, h = 140, 30
        extra = {"text": "TextBox", "label_widget": None}

    elif comp_type == "TextArea":
        widget = tk.Text(parent)
        widget.insert("1.0", "TextArea")
        w, h = 180, 80
        extra = {"text": "TextArea", "label_widget": None}

    elif comp_type == "CheckBox":
        widget = tk.Checkbutton(parent, text="Check", bg="white")
        w, h = 120, 30
        extra = {"text": "Check", "label_widget": None}

    elif comp_type == "RadioButton":
        widget = tk.Radiobutton(parent, text="Radio", value=1, bg="white")
        w, h = 120, 30
        extra = {"text": "Radio", "label_widget": None}

    elif comp_type == "ListBox":
        widget = tk.Listbox(parent)
        widget.insert(tk.END, "Item 1")
        widget.insert(tk.END, "Item 2")
        widget.insert(tk.END, "Item 3")
        w, h = 140, 90
        extra = {"text": "Item 1|Item 2|Item 3", "label_widget": None}

    elif comp_type == "ComboBox":
        widget = ttk.Combobox(parent, values=["One", "Two", "Three"])
        widget.set("One")
        w, h = 150, 30
        extra = {"text": "One|Two|Three", "values": ["One", "Two", "Three"], "label_widget": None}

    elif comp_type == "Scale":
        widget = tk.Scale(parent, from_=0, to=100, orient="horizontal")
        widget.set(50)
        w, h = 180, 50
        extra = {"text": "50", "label_widget": None}

    elif comp_type == "SpinBox":
        widget = tk.Spinbox(parent, from_=0, to=100)
        widget.delete(0, tk.END)
        widget.insert(0, "5")
        w, h = 100, 30
        extra = {"text": "5", "label_widget": None}

    elif comp_type == "Frame":
        widget = tk.Frame(parent, bg="#d9d9d9", relief="ridge", bd=2)
        w, h = 160, 100
        extra = {"text": "", "label_widget": None}

    elif comp_type == "LabelFrame":
        widget = tk.LabelFrame(parent, text="Group", bg="#f0f0f0")
        w, h = 180, 110
        extra = {"text": "Group", "label_widget": None}

    elif comp_type == "Canvas":
        widget = tk.Canvas(parent, bg="white", bd=1, relief="solid")
        widget.create_rectangle(10, 10, 60, 40)
        w, h = 180, 100
        extra = {"text": "", "label_widget": None}

    elif comp_type == "ProgressBar":
        widget = ttk.Progressbar(parent, orient="horizontal", mode="determinate", maximum=100)
        widget["value"] = 40
        w, h = 180, 24
        extra = {"text": "40", "value": 40, "label_widget": None}

    elif comp_type == "Panel":
        widget = tk.Frame(parent, bg="#d9d9d9", relief="ridge", bd=2)
        lbl = tk.Label(widget, text="Panel", bg="#d9d9d9")
        lbl.place(x=8, y=8)
        w, h = 160, 100
        extra = {"text": "Panel", "label_widget": lbl}

    else:
        return None, 0, 0, {}

    return widget, w, h, extra


def add_component(comp_type):
    global next_x, next_y

    if len(placed_components) >= MAX_COMPONENTS:
        messagebox.showwarning(
            "Limit reached",
            f"Maximum number of components ({MAX_COMPONENTS}) has been reached."
        )
        return

    widget, w, h, extra = create_widget(canvas, comp_type)
    if widget is None:
        return

    canvas.update_idletasks()

    x = next_x
    y = next_y

    occupied_here = False
    for comp in placed_components:
        if overlaps(x, y, w, h, comp["x"], comp["y"], comp["w"], comp["h"]):
            occupied_here = True
            break

    if occupied_here:
        x, y = find_next_free_position(w, h)

    if x + w > canvas.winfo_width():
        x = 20

    if y + h > canvas.winfo_height():
        messagebox.showwarning("Full", "No more space is available on the layout area.")
        return

    for comp in placed_components:
        if overlaps(x, y, w, h, comp["x"], comp["y"], comp["w"], comp["h"]):
            messagebox.showwarning(
                "Occupied",
                "The start position is occupied. Move other components or clear the layout."
            )
            return

    widget.place(x=x, y=y, width=w, height=h)
    connect_widget(widget, comp_type)

    if comp_type == "Panel" and extra.get("label_widget") is not None:
        connect_panel_label(extra["label_widget"], widget)

    comp = {
        "type": comp_type,
        "x": x,
        "y": y,
        "w": w,
        "h": h,
        "widget": widget,
        "text": extra.get("text", ""),
        "values": extra.get("values", None),
        "value": extra.get("value", None),
        "label_widget": extra.get("label_widget", None)
    }

    placed_components.append(comp)
    select_component(comp)

    save_undo("add", {
        "comp": comp
    })

    next_x, next_y = find_next_free_position()


# ------------------------------------------------------------
# Edit selected component
# ------------------------------------------------------------

def change_width(delta):
    if selected_comp is None:
        return

    old_w = selected_comp["w"]
    old_h = selected_comp["h"]

    new_w = selected_comp["w"] + delta
    new_h = selected_comp["h"]

    if not size_ok(selected_comp, new_w, new_h):
        return

    selected_comp["w"] = new_w
    selected_comp["widget"].place(
        x=selected_comp["x"],
        y=selected_comp["y"],
        width=selected_comp["w"],
        height=selected_comp["h"]
    )
    update_selection_box()
    update_status()

    if old_w != new_w:
        save_undo("resize", {
            "comp": selected_comp,
            "old_w": old_w,
            "old_h": old_h,
            "new_w": new_w,
            "new_h": new_h
        })


def change_height(delta):
    if selected_comp is None:
        return

    old_w = selected_comp["w"]
    old_h = selected_comp["h"]

    new_w = selected_comp["w"]
    new_h = selected_comp["h"] + delta

    if not size_ok(selected_comp, new_w, new_h):
        return

    selected_comp["h"] = new_h
    selected_comp["widget"].place(
        x=selected_comp["x"],
        y=selected_comp["y"],
        width=selected_comp["w"],
        height=selected_comp["h"]
    )
    update_selection_box()
    update_status()

    if old_h != new_h:
        save_undo("resize", {
            "comp": selected_comp,
            "old_w": old_w,
            "old_h": old_h,
            "new_w": new_w,
            "new_h": new_h
        })


def wider():
    change_width(RESIZE_STEP)


def narrower():
    change_width(-RESIZE_STEP)


def taller():
    change_height(RESIZE_STEP)


def shorter():
    change_height(-RESIZE_STEP)


def delete_selected():
    global selected_comp, next_x, next_y

    if selected_comp is None:
        return

    comp_data = component_to_dict(selected_comp)
    widget_to_destroy = selected_comp["widget"]

    save_undo("delete", {
        "comp_data": comp_data
    })

    placed_components.remove(selected_comp)
    widget_to_destroy.destroy()

    selected_comp = None
    update_selection_box()
    clear_status()

    next_x, next_y = find_next_free_position()


def change_text():
    if selected_comp is None:
        messagebox.showinfo("Info", "No component is selected.")
        return

    comp_type = selected_comp["type"]

    if comp_type in ["Frame", "Canvas"]:
        messagebox.showinfo("Info", f"{comp_type} has no text to edit.")
        return

    prompt = "New text for selected component:"
    if comp_type in ["ListBox", "ComboBox"]:
        prompt = "New text/values (separate with | ):"
    elif comp_type == "ProgressBar":
        prompt = "New value 0-100:"
    elif comp_type == "Scale":
        prompt = "New value 0-100:"
    elif comp_type == "SpinBox":
        prompt = "New start value:"

    old_text = get_component_text(selected_comp)

    new_text = simpledialog.askstring(
        "Change text",
        prompt,
        initialvalue=old_text
    )

    if new_text is None:
        return

    if new_text == old_text:
        return

    set_component_text(selected_comp, new_text)
    select_component(selected_comp)

    save_undo("text", {
        "comp": selected_comp,
        "old_text": old_text,
        "new_text": new_text
    })


def undo_last():
    global last_action, selected_comp, next_x, next_y

    if last_action is None:
        messagebox.showinfo("Undo", "There is no action to undo.")
        return

    action_type = last_action["type"]
    data = last_action["data"]

    if action_type == "add":
        comp = data["comp"]
        if comp in placed_components:
            placed_components.remove(comp)
            comp["widget"].destroy()
            if selected_comp is comp:
                selected_comp = None

    elif action_type == "delete":
        comp = restore_component_from_dict(data["comp_data"])
        if comp is not None:
            placed_components.append(comp)
            select_component(comp)

    elif action_type == "move":
        comp = data["comp"]
        if comp in placed_components:
            comp["x"] = data["old_x"]
            comp["y"] = data["old_y"]
            comp["widget"].place(
                x=comp["x"],
                y=comp["y"],
                width=comp["w"],
                height=comp["h"]
            )
            select_component(comp)

    elif action_type == "resize":
        comp = data["comp"]
        if comp in placed_components:
            comp["w"] = data["old_w"]
            comp["h"] = data["old_h"]
            comp["widget"].place(
                x=comp["x"],
                y=comp["y"],
                width=comp["w"],
                height=comp["h"]
            )
            select_component(comp)

    elif action_type == "text":
        comp = data["comp"]
        if comp in placed_components:
            set_component_text(comp, data["old_text"])
            select_component(comp)

    update_selection_box()
    update_status()

    last_action = None
    next_x, next_y = find_next_free_position()


# ------------------------------------------------------------
# Save / load layout
# ------------------------------------------------------------

def save_layout():
    if not placed_components:
        messagebox.showinfo("Save", "There are no components to save.")
        return

    file_path = filedialog.asksaveasfilename(
        defaultextension=".json",
        filetypes=[("JSON files", "*.json")],
        title="Save layout"
    )

    if not file_path:
        return

    data = [component_to_dict(comp) for comp in placed_components]

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        messagebox.showinfo("Save", "Layout saved.")
    except Exception as e:
        messagebox.showerror("Error", f"Could not save the file.\n\n{e}")


def load_layout():
    global selected_comp, next_x, next_y, last_action

    file_path = filedialog.askopenfilename(
        filetypes=[("JSON files", "*.json")],
        title="Load layout"
    )

    if not file_path:
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        messagebox.showerror("Error", f"Could not read the file.\n\n{e}")
        return

    new_form(confirm=False)

    canvas.update_idletasks()

    try:
        for item in data:
            if len(placed_components) >= MAX_COMPONENTS:
                break

            comp = restore_component_from_dict(item)
            if comp is not None:
                placed_components.append(comp)

        if placed_components:
            select_component(placed_components[-1])
        else:
            selected_comp = None
            update_selection_box()
            clear_status()

        last_action = None
        next_x, next_y = find_next_free_position()
        messagebox.showinfo("Load", "Layout loaded.")
    except Exception as e:
        messagebox.showerror("Error", f"Could not create the layout.\n\n{e}")


# ------------------------------------------------------------
# Export Python
# ------------------------------------------------------------

def export_python():
    if not placed_components:
        messagebox.showinfo("Export", "There are no components to export.")
        return

    file_path = filedialog.asksaveasfilename(
        defaultextension=".py",
        filetypes=[("Python files", "*.py")],
        title="Export Python"
    )

    if not file_path:
        return

    try:
        root.update_idletasks()
        canvas.update_idletasks()

        window_w = root.winfo_width()
        window_h = root.winfo_height()

        code_lines = []
        code_lines.append("import tkinter as tk")
        code_lines.append("from tkinter import ttk")
        code_lines.append("")
        code_lines.append("# ------------------------------------------------------------")
        code_lines.append("# Exported from RWB Form Designer v1.7.4")
        code_lines.append("# Generated for Tkinter / Pydroid 3")
        code_lines.append("# Collaboration project by Robert William Blennerhed & ChatGPT")
        code_lines.append("# ------------------------------------------------------------")
        code_lines.append("")

        type_counts = {
            "Label": 0,
            "Button": 0,
            "TextBox": 0,
            "TextArea": 0,
            "CheckBox": 0,
            "RadioButton": 0,
            "ListBox": 0,
            "ComboBox": 0,
            "Scale": 0,
            "SpinBox": 0,
            "Frame": 0,
            "LabelFrame": 0,
            "Canvas": 0,
            "ProgressBar": 0,
            "Panel": 0
        }

        exported_components = []

        for comp in placed_components:
            comp_type = comp["type"]
            type_counts[comp_type] += 1

            name_map = {
                "Label": "label",
                "Button": "button",
                "TextBox": "textbox",
                "TextArea": "textarea",
                "CheckBox": "checkbox",
                "RadioButton": "radiobutton",
                "ListBox": "listbox",
                "ComboBox": "combobox",
                "Scale": "scale",
                "SpinBox": "spinbox",
                "Frame": "frame",
                "LabelFrame": "labelframe",
                "Canvas": "canvas_widget",
                "ProgressBar": "progressbar",
                "Panel": "panel"
            }

            prefix = name_map.get(comp_type, "widget")
            var_name = f"{prefix}{type_counts[comp_type]}"
            event_name = create_event_name(comp_type, type_counts[comp_type])

            exported_components.append({
                "var_name": var_name,
                "event_name": event_name,
                "type": comp_type,
                "x": comp["x"],
                "y": comp["y"],
                "w": comp["w"],
                "h": comp["h"],
                "text": get_component_text(comp)
            })

        code_lines.append("def form_startup():")
        code_lines.append("    # TODO: add startup code here")
        code_lines.append("    pass")
        code_lines.append("")

        for item in exported_components:
            code_lines.append(f"def {item['event_name']}():")
            code_lines.append("    # TODO: add code here")
            code_lines.append("    pass")
            code_lines.append("")

        code_lines.append("# --- GUI STARTS HERE ---")
        code_lines.append("")
        code_lines.append("root = tk.Tk()")
        code_lines.append('root.title("RWB Exported Form")')
        code_lines.append(f'root.geometry("{window_w}x{window_h}")')
        code_lines.append("")
        code_lines.append('top_status_bar = tk.Frame(root, bg="#d9d9d9", height=24)')
        code_lines.append('top_status_bar.pack(fill="x")')
        code_lines.append('top_status_bar.pack_propagate(False)')
        code_lines.append("")
        code_lines.append('canvas = tk.Frame(root, bg="white", bd=1, relief="solid")')
        code_lines.append('canvas.pack(fill="both", expand=True)')
        code_lines.append("")

        for item in exported_components:
            comp_type = item["type"]
            name = item["var_name"]
            x = item["x"]
            y = item["y"]
            w = item["w"]
            h = item["h"]
            text = esc_text(item["text"])
            event_name = item["event_name"]

            if comp_type == "Label":
                code_lines.append(f'{name} = tk.Label(canvas, text="{text}", bg="white", relief="solid", bd=1)')
                code_lines.append(f'{name}.place(x={x}, y={y}, width={w}, height={h})')
                code_lines.append("")

            elif comp_type == "Button":
                code_lines.append(f'{name} = tk.Button(canvas, text="{text}", command={event_name})')
                code_lines.append(f'{name}.place(x={x}, y={y}, width={w}, height={h})')
                code_lines.append("")

            elif comp_type == "TextBox":
                code_lines.append(f"{name} = tk.Entry(canvas)")
                code_lines.append(f'{name}.insert(0, "{text}")')
                code_lines.append(f'{name}.place(x={x}, y={y}, width={w}, height={h})')
                code_lines.append("")

            elif comp_type == "TextArea":
                code_lines.append(f"{name} = tk.Text(canvas)")
                code_lines.append(f'{name}.insert("1.0", "{text}")')
                code_lines.append(f'{name}.place(x={x}, y={y}, width={w}, height={h})')
                code_lines.append("")

            elif comp_type == "CheckBox":
                var_name = f"{name}_var"
                code_lines.append(f"{var_name} = tk.IntVar()")
                code_lines.append(f'{name} = tk.Checkbutton(canvas, text="{text}", variable={var_name}, bg="white")')
                code_lines.append(f'{name}.place(x={x}, y={y}, width={w}, height={h})')
                code_lines.append("")

            elif comp_type == "RadioButton":
                var_name = f"{name}_var"
                code_lines.append(f"{var_name} = tk.IntVar()")
                code_lines.append(f'{name} = tk.Radiobutton(canvas, text="{text}", variable={var_name}, value=1, bg="white")')
                code_lines.append(f'{name}.place(x={x}, y={y}, width={w}, height={h})')
                code_lines.append("")

            elif comp_type == "ListBox":
                code_lines.append(f"{name} = tk.Listbox(canvas)")
                for list_item in item["text"].split("|"):
                    list_item = esc_text(list_item.strip())
                    if list_item:
                        code_lines.append(f'{name}.insert(tk.END, "{list_item}")')
                code_lines.append(f'{name}.place(x={x}, y={y}, width={w}, height={h})')
                code_lines.append("")

            elif comp_type == "ComboBox":
                values = [esc_text(v.strip()) for v in item["text"].split("|") if v.strip()]
                if not values:
                    values = ["One", "Two", "Three"]
                values_str = ", ".join(f'"{v}"' for v in values)
                code_lines.append(f"{name} = ttk.Combobox(canvas, values=[{values_str}])")
                code_lines.append(f'{name}.set("{values[0]}")')
                code_lines.append(f'{name}.place(x={x}, y={y}, width={w}, height={h})')
                code_lines.append("")

            elif comp_type == "Scale":
                code_lines.append(f'{name} = tk.Scale(canvas, from_=0, to=100, orient="horizontal")')
                try:
                    scale_value = int(float(item["text"]))
                except Exception:
                    scale_value = 50
                code_lines.append(f"{name}.set({scale_value})")
                code_lines.append(f'{name}.place(x={x}, y={y}, width={w}, height={h})')
                code_lines.append("")

            elif comp_type == "SpinBox":
                code_lines.append(f'{name} = tk.Spinbox(canvas, from_=0, to=100)')
                code_lines.append(f'{name}.delete(0, tk.END)')
                code_lines.append(f'{name}.insert(0, "{text}")')
                code_lines.append(f'{name}.place(x={x}, y={y}, width={w}, height={h})')
                code_lines.append("")

            elif comp_type == "Frame":
                code_lines.append(f'{name} = tk.Frame(canvas, bg="#d9d9d9", relief="ridge", bd=2)')
                code_lines.append(f'{name}.place(x={x}, y={y}, width={w}, height={h})')
                code_lines.append("")

            elif comp_type == "LabelFrame":
                code_lines.append(f'{name} = tk.LabelFrame(canvas, text="{text}", bg="#f0f0f0")')
                code_lines.append(f'{name}.place(x={x}, y={y}, width={w}, height={h})')
                code_lines.append("")

            elif comp_type == "Canvas":
                code_lines.append(f'{name} = tk.Canvas(canvas, bg="white", bd=1, relief="solid")')
                code_lines.append(f'{name}.place(x={x}, y={y}, width={w}, height={h})')
                code_lines.append(f"{name}.create_rectangle(10, 10, 60, 40)")
                code_lines.append("")

            elif comp_type == "ProgressBar":
                try:
                    pb_value = int(float(item["text"]))
                except Exception:
                    pb_value = 40
                pb_value = max(0, min(100, pb_value))
                code_lines.append(f'{name} = ttk.Progressbar(canvas, orient="horizontal", mode="determinate", maximum=100)')
                code_lines.append(f'{name}["value"] = {pb_value}')
                code_lines.append(f'{name}.place(x={x}, y={y}, width={w}, height={h})')
                code_lines.append("")

            elif comp_type == "Panel":
                label_name = f"{name}_label"
                code_lines.append(f'{name} = tk.Frame(canvas, bg="#d9d9d9", relief="ridge", bd=2)')
                code_lines.append(f'{name}.place(x={x}, y={y}, width={w}, height={h})')
                code_lines.append(f'{label_name} = tk.Label({name}, text="{text}", bg="#d9d9d9")')
                code_lines.append(f"{label_name}.place(x=8, y=8)")
                code_lines.append("")

        code_lines.append("form_startup()")
        code_lines.append("")
        code_lines.append("root.mainloop()")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(code_lines))

        messagebox.showinfo("Export", "Python file exported.")
    except Exception as e:
        messagebox.showerror("Error", f"Could not export Python file.\n\n{e}")


# ------------------------------------------------------------
# New form
# ------------------------------------------------------------

def new_form(confirm=True):
    global next_x, next_y, selected_comp, last_action

    if confirm and placed_components:
        answer = messagebox.askyesno(
            "New Form",
            "Do you really want to clear the form and start over?"
        )
        if not answer:
            return

    for comp in placed_components:
        comp["widget"].destroy()

    placed_components.clear()
    selected_comp = None
    last_action = None

    update_selection_box()
    clear_status()

    next_x, next_y = 20, 20


# ------------------------------------------------------------
# Main window
# ------------------------------------------------------------

root = tk.Tk()
root.title("RWB Form Designer")
root.geometry(f"{WINDOW_W}x{WINDOW_H}")

menubar = tk.Menu(root)

# File
file_menu = tk.Menu(menubar, tearoff=0)
file_menu.add_command(label="New Form", command=new_form)
file_menu.add_command(label="Save Layout", command=save_layout)
file_menu.add_command(label="Load Layout", command=load_layout)
file_menu.add_command(label="Export Python", command=export_python)
file_menu.add_separator()
file_menu.add_command(label="Exit", command=root.destroy)
menubar.add_cascade(label="File", menu=file_menu)

# Components
components_menu = tk.Menu(menubar, tearoff=0)
components_menu.add_command(label="Label", command=lambda: add_component("Label"))
components_menu.add_command(label="Button", command=lambda: add_component("Button"))
components_menu.add_command(label="TextBox", command=lambda: add_component("TextBox"))
components_menu.add_command(label="TextArea", command=lambda: add_component("TextArea"))
components_menu.add_separator()
components_menu.add_command(label="CheckBox", command=lambda: add_component("CheckBox"))
components_menu.add_command(label="RadioButton", command=lambda: add_component("RadioButton"))
components_menu.add_separator()
components_menu.add_command(label="ListBox", command=lambda: add_component("ListBox"))
components_menu.add_command(label="ComboBox", command=lambda: add_component("ComboBox"))
components_menu.add_command(label="Scale", command=lambda: add_component("Scale"))
components_menu.add_command(label="SpinBox", command=lambda: add_component("SpinBox"))
components_menu.add_separator()
components_menu.add_command(label="Frame", command=lambda: add_component("Frame"))
components_menu.add_command(label="LabelFrame", command=lambda: add_component("LabelFrame"))
components_menu.add_command(label="Canvas", command=lambda: add_component("Canvas"))
components_menu.add_command(label="ProgressBar", command=lambda: add_component("ProgressBar"))
components_menu.add_command(label="Panel", command=lambda: add_component("Panel"))
menubar.add_cascade(label="Components", menu=components_menu)

# Edit
edit_menu = tk.Menu(menubar, tearoff=0)
edit_menu.add_command(label="Undo Last", command=undo_last)
edit_menu.add_separator()
edit_menu.add_command(label="Change Text", command=change_text)
edit_menu.add_separator()
edit_menu.add_command(label="Wider", command=wider)
edit_menu.add_command(label="Narrower", command=narrower)
edit_menu.add_command(label="Taller", command=taller)
edit_menu.add_command(label="Shorter", command=shorter)
edit_menu.add_separator()
edit_menu.add_command(label="Delete Selected", command=delete_selected)
menubar.add_cascade(label="Edit", menu=edit_menu)

# Options
options_menu = tk.Menu(menubar, tearoff=0)
options_menu.add_command(label="Snap to Grid On/Off", command=toggle_snap_to_grid)
menubar.add_cascade(label="Options", menu=options_menu)

root.config(menu=menubar)

# Status bar
top_status_bar = tk.Frame(root, bg="#d9d9d9", height=40)
top_status_bar.pack(fill="x")
top_status_bar.pack_propagate(False)

status_info = tk.Label(
    top_status_bar,
    text=f"Selected: None   X: -   Y: -   Snap: {'On' if SNAP_TO_GRID else 'Off'}",
    bg="#d9d9d9",
    anchor="e"
)
status_info.pack(side="right", padx=8)

# Layout area
canvas = tk.Frame(root, bg="white", bd=1, relief="solid")
canvas.pack(fill="both", expand=True)

# Selection box
selection_box = tk.Frame(
    canvas,
    highlightbackground="red",
    highlightthickness=2,
    bd=0,
    bg="#d9d9d9"
)

# Resize handle
resize_handle = tk.Frame(
    canvas,
    bg="black",
    width=16,
    height=16
)

resize_handle.bind("<Button-1>", on_resize_press)
resize_handle.bind("<B1-Motion>", on_resize_drag)
resize_handle.bind("<ButtonRelease-1>", on_resize_release)

root.mainloop()
