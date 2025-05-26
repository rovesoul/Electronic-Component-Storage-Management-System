import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import os, shutil, time,sys
import platform
import subprocess
from PIL import Image, ImageTk
import webbrowser
import json
import dbapi



def load_json(path="config.json"):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data
    except Exception as e:
        messagebox.showerror("文件错误", f"无法读取配置文件\n{e}")

jsonFile=load_json()
if 'types' in jsonFile and isinstance(jsonFile['types'], dict):
    types = list(jsonFile['types'].keys())
    packages=jsonFile['package']
    # print(packages)
else:
    types = ['其他']
    packages=['其他']




# ----------- 带滚动条的主内容区实现 ------------
class ScrollableFrame(ttk.Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.scrollable_frame.bind("<Enter>", lambda e: self._bind_mousewheel(canvas))
        self.scrollable_frame.bind("<Leave>", lambda e: self._unbind_mousewheel(canvas))

    def _bind_mousewheel(self, canvas):
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))

    def _unbind_mousewheel(self, canvas):
        canvas.unbind_all("<MouseWheel>")
        canvas.unbind_all("<Button-4>")
        canvas.unbind_all("<Button-5>")

# ------- 图片放大缩放弹窗（核心功能） ---------
class ZoomImageViewer(tk.Toplevel):
    def __init__(self, parent, img_path):
        super().__init__(parent)
        self.title(os.path.basename(img_path))
        self.img_path = img_path
        self.original_img = Image.open(img_path)
        self.zoom_level = 1.0

        # 窗口居中初始化
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w = int(sw * 0.9)
        h = int(sh * 0.8)
        self.geometry(f"{w}x{h}+{int((sw-w)/2)}+{int((sh-h)/2)}")
        self.resizable(True, True)

        self.canvas = tk.Canvas(self, bg='black')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.h_scroll = tk.Scrollbar(self, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.v_scroll = tk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.config(xscrollcommand=self.h_scroll.set, yscrollcommand=self.v_scroll.set)

        # 鼠标事件绑定
        self.canvas.bind('<MouseWheel>', self._on_mousewheel)     # windows
        self.canvas.bind('<Button-4>', self._on_mousewheel)       # linux
        self.canvas.bind('<Button-5>', self._on_mousewheel)       # linux
        self.canvas.bind('<ButtonPress-1>', self._on_press)
        self.canvas.bind('<B1-Motion>', self._on_drag)

        self._zoom_job = None
        self._img_pos = (0, 0)   # 记录当前图像位置，便于精确缩放

        self.bind("<Configure>", lambda e: self.reset_image_fit())
        self.fit_once = False
        self.after(15, self.reset_image_fit)

    def reset_image_fit(self):
        if self.fit_once: return
        win_w = self.winfo_width()
        win_h = self.winfo_height()
        img_w, img_h = self.original_img.size
        factor = min(win_w / img_w, win_h / img_h, 1.0)
        self.zoom_level = factor
        self.show_image(center=True)
        self.fit_once = True

    def _on_mousewheel(self, event):
        if event.num == 5 or getattr(event, "delta", 0) < 0:
            factor = 1 / 1.1
        elif event.num == 4 or getattr(event, "delta", 0) > 0:
            factor = 1.1
        else:
            return
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        img_x = x / self.zoom_level
        img_y = y / self.zoom_level

        # 记住canvas上的本地像素
        self._last_canvas_xy = (event.x, event.y)
        
        new_zoom = self.zoom_level * factor
        new_zoom = max(0.1, min(new_zoom, 10))
        if self._zoom_job is not None:
            self.after_cancel(self._zoom_job)
        self._zoom_job = self.after(
            1,
            lambda: self._zoom_to(img_x, img_y, new_zoom, (event.x, event.y))  # 新增canvas像素位置
        )

    def _zoom_to(self, img_x, img_y, new_zoom, last_canvas_xy):
        self.zoom_level = new_zoom
        self._last_canvas_xy = last_canvas_xy  # 传到show_image用
        self.show_image(zoom_at=(img_x, img_y))

    def _on_press(self, event):
        self.canvas.scan_mark(event.x, event.y)

    def _on_drag(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def show_image(self, center=False, center_coord=None, zoom_at=None):
        '''
        :param center: 是否居中
        :param center_coord: 兼容保留
        :param zoom_at: (img_x, img_y) 以原图的某点（如鼠标落点）为缩放参考
        '''
        img = self.original_img.resize(
            (max(1, int(self.original_img.width * self.zoom_level)),
             max(1, int(self.original_img.height * self.zoom_level))),
            Image.LANCZOS)
        self.tkimg = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.img_on_canvas = self.canvas.create_image(0, 0, anchor='nw', image=self.tkimg)
        self.canvas.config(scrollregion=(0, 0, img.width, img.height))

        c_w = self.canvas.winfo_width()
        c_h = self.canvas.winfo_height()

        if zoom_at is not None:
                # 保证鼠标下的点缩放后仍停留在光标处
            img_x, img_y = zoom_at           # 鼠标对应原图坐标
            c_w = self.canvas.winfo_width()
            c_h = self.canvas.winfo_height()
            
            # 1. 缩放后该点的画布坐标:
            x_canvas_new = img_x * self.zoom_level
            y_canvas_new = img_y * self.zoom_level
            
            # 2. 缩放前该点在画布上的像素
            # 注意，这里的 canvas_x,canvas_y 就是 `event.x,event.y` 传进来的! 
            # 但 show_image 里没传，要在 _zoom_to 方法里一并传进去
            
            # 3. 当前scroll范围
            img_w, img_h = img.width, img.height

            # 4. 设置view，使鼠标点矫正后和画布位置重合
            # 目标: 缩放后的img_x * zoom_level必须和缩放前鼠标所在canvas像素对齐
            # 但show_image里拿不到event.x, event.y，怎么办？让_zoom_to多传入这个信息
            if hasattr(self, "_last_canvas_xy"):
                canvas_x, canvas_y = self._last_canvas_xy
                # 这两个的范围都是canvas视区内像素
                # xview_moveto/yview_moveto参数是fraction，不是像素
                self.canvas.xview_moveto( (x_canvas_new - canvas_x) / max(1, img_w) )
                self.canvas.yview_moveto( (y_canvas_new - canvas_y) / max(1, img_h) )
        elif center_coord is not None:
            # 老参数，兼容
            cx, cy = center_coord
            img_w, img_h = img.width, img.height
            new_x = cx / img_w if img_w else 0
            new_y = cy / img_h if img_h else 0
            self.canvas.xview_moveto(max(0, new_x - c_w/(2*img_w)))
            self.canvas.yview_moveto(max(0, new_y - c_h/(2*img_h)))
        elif center:
            # 首次居中
            self.canvas.xview_moveto(max(0, (img.width - c_w) / 2 / img.width))
            self.canvas.yview_moveto(max(0, (img.height - c_h) / 2 / img.height))



root = tk.Tk()
root.title('电子元器件管理Electronic Component Storage Management System')

try:
    logo_img = Image.open(os.path.join('src', 'sysimg', 'logo.png'))
    logo_tk = ImageTk.PhotoImage(logo_img)
    root.iconphoto(True, logo_tk)
except Exception as e:
    print("Logo加载失败:", e, file=sys.stderr)


dbapi.init_db()

# 屏幕80%尺寸
sw = root.winfo_screenwidth()
sh = root.winfo_screenheight()
w = int(sw * 0.8)
h = int(sh * 0.8)
x = int((sw - w) / 2)
y = int((sh - h) / 3)
root.geometry(f"{w}x{h}+{x}+{y}")

scrollable = ScrollableFrame(root)
scrollable.pack(fill='both', expand=True)

frame_parent = scrollable.scrollable_frame

# ------ 入库区 ------
data_frame = tk.LabelFrame(frame_parent, text="物料信息", padx=8, pady=2)
data_frame.pack(fill='x', padx=8, pady=6)

left_frame_input = tk.Frame(data_frame)
left_frame_input.pack(side='left', fill='x', expand=True)


right_frame_input= tk.Frame(data_frame)
right_frame_input.pack(side='left', fill='x', expand=True)

# 第一行表
tk.Label(left_frame_input, text='器件类型').grid(row=0, column=0, sticky='e', padx=2, pady=0)
name_var = tk.StringVar()
name_box = ttk.Combobox(left_frame_input, textvariable=name_var, width=10)
name_box['values'] = types
name_box.grid(row=0, column=1, sticky='w', padx=2)
other_name_var = tk.StringVar()
other_name_entry = tk.Entry(left_frame_input, textvariable=other_name_var, width=10)
other_name_entry.grid(row=0, column=2, sticky='e', padx=2)
other_name_entry.grid_remove()

def on_type_selected(event):
    if name_var.get() == '其他':
        other_name_entry.grid()
    else:
        other_name_var.set('')
        other_name_entry.grid_remove()
name_box.bind("<<ComboboxSelected>>", on_type_selected)

tk.Label(left_frame_input, text='型号/名称').grid(row=0, column=3, sticky='e', padx=2)
model_var = tk.StringVar()
tk.Entry(left_frame_input, textvariable=model_var, width=12).grid(row=0, column=4, sticky='w', padx=2)



tk.Label(left_frame_input, text='封装').grid(row=0, column=5, sticky='e', padx=2, pady=2)
package_var = tk.StringVar()
package_box = ttk.Combobox(left_frame_input, textvariable=package_var, width=10)
package_box['values'] = packages
package_box.grid(row=0, column=6, sticky='w', padx=2)
other_package_var = tk.StringVar()
other_package_entry = tk.Entry(left_frame_input, textvariable=other_name_var, width=10)
other_package_entry.grid(row=0, column=7, sticky='w', padx=2)
other_package_entry.grid_remove()

def on_package_selected(event):
    if package_var.get() == '其他':
        other_package_entry.grid()
    else:
        other_package_var.set('')
        other_package_entry.grid_remove()
package_box.bind("<<ComboboxSelected>>", on_package_selected)


tk.Label(left_frame_input, text='数量').grid(row=0, column=8, sticky='e', padx=2)
qty_var = tk.StringVar()
tk.Entry(left_frame_input, textvariable=qty_var, width=8).grid(row=0, column=9, sticky='w', padx=2)
tk.Label(left_frame_input, text='总金额(元)').grid(row=0, column=10, sticky='e', padx=2)
price_var = tk.StringVar()
tk.Entry(left_frame_input, textvariable=price_var, width=10).grid(row=0, column=11, sticky='w', padx=2)


# 第二行表
tk.Label(left_frame_input, text='备注').grid(row=1, column=0, sticky='e', padx=2, pady=2)
note_var = tk.StringVar()
tk.Entry(left_frame_input, textvariable=note_var, width=52).grid(row=1, column=1, columnspan=12, sticky='w', padx=2)

img_path_var = tk.StringVar()
tk.Label(left_frame_input, text='图片').grid(row=2, column=0, sticky='e', padx=2, pady=2)
img_entry = tk.Entry(left_frame_input, textvariable=img_path_var, state='readonly', width=30, relief='sunken')
img_entry.grid(row=2, column=1, columnspan=2, sticky='w', padx=2)
def choose_img():
    img_path = filedialog.askopenfilename(filetypes=[("图片文件", "*.jpg *.jpeg *.png *.gif")])
    if img_path:
        ext = os.path.splitext(img_path)[-1]
        now = time.strftime('%Y%m%d%H%M%S')
        c_name = name_var.get() if name_var.get() != "其他" else other_name_var.get()
        folder = os.path.join('src', 'img', c_name)
        os.makedirs(folder, exist_ok=True)
        basename = f"{c_name}-{model_var.get()}-{now}{ext}"
        dst_path = os.path.join(folder, basename)
        shutil.copy(img_path, dst_path)
        img_path_var.set(dst_path)
tk.Button(left_frame_input, text='选择图片', command=choose_img).grid(row=2, column=3, padx=2)

doc_path_var = tk.StringVar()
tk.Label(left_frame_input, text='文档').grid(row=2, column=4, sticky='e', padx=2)
doc_entry = tk.Entry(left_frame_input, textvariable=doc_path_var, state='readonly', width=30, relief='sunken')
doc_entry.grid(row=2, column=5, columnspan=2, sticky='w', padx=2)
def choose_doc():
    doc_path = filedialog.askopenfilename(filetypes=[("文档", "*.pdf *.docx *.txt *.xlsx")])
    if doc_path:
        ext = os.path.splitext(doc_path)[-1]
        now = time.strftime('%Y%m%d%H%M%S')
        c_name = name_var.get() if name_var.get() != "其他" else other_name_var.get()
        folder = os.path.join('src', 'document', c_name)
        os.makedirs(folder, exist_ok=True)
        basename = f"{c_name}-{model_var.get()}-{now}{ext}"
        dst_path = os.path.join(folder, basename)
        shutil.copy(doc_path, dst_path)
        doc_path_var.set(dst_path)
tk.Button(left_frame_input, text='选择文档', command=choose_doc).grid(row=2, column=7, padx=2)

cloud_link_var = tk.StringVar()
tk.Label(left_frame_input, text='云端文档链接').grid(row=3, column=0, sticky='e', padx=2, pady=2)
tk.Entry(left_frame_input, textvariable=cloud_link_var, width=63).grid(row=3, column=1, columnspan=8, sticky='w', padx=2)

def clear_entry_area():
    name_var.set("")
    other_name_var.set("")
    other_name_entry.grid_remove()
    model_var.set("")
    package_var.set("")
    qty_var.set("")
    price_var.set("")
    note_var.set("")
    img_path_var.set("")
    doc_path_var.set("")
    cloud_link_var.set("")

def on_add():
    c_name = name_var.get()
    if c_name == "其他":
        c_name = other_name_var.get().strip()
        if not c_name:
            messagebox.showerror("输入有误", "请填写自定义分类")
            other_name_entry.focus_set()
            return
    model = model_var.get().strip()
    package=package_var.get().strip()
    note = note_var.get().strip()
    img_path = img_path_var.get().strip()
    doc_path = doc_path_var.get().strip()
    cloud_link = cloud_link_var.get().strip()
    try:
        qty = int(qty_var.get())
        if qty <= 0:
            raise ValueError
    except:
        messagebox.showerror("输入有误", "数量必须是正整数")
        return
    try:
        total_price = float(price_var.get())
        if total_price < 0:
            raise ValueError
    except:
        total_price = 0.0

    if not c_name or not model:
        messagebox.showerror("输入有误", "请填写类型和型号")
        return

    row = dbapi.get_component_by_name_model(c_name, model,package)
    if row:
        if not messagebox.askyesno("补仓确认", "该器件已存在\n是否追加数量并合并金额？\n图片、文档与云链都会被替换。"):
            return
    dbapi.add_or_update_component(c_name, model,package, qty, total_price, note, img_path, doc_path, cloud_link)
    refresh_tree(tree)
    messagebox.showinfo("提示", "入库成功")
    clear_entry_area()

tk.Button(right_frame_input, text='入库', command=on_add, bg='lightgreen', width=10).grid(row=4, column=0, columnspan=2, padx=2, pady=6, ipady=2)

# ------ 搜索区 ------
search_frame = tk.Frame(frame_parent)
search_frame.pack(fill='x', padx=w*0.2, pady=12)
search_var = tk.StringVar()
tk.Entry(search_frame, textvariable=search_var, width=40).pack(side='left', padx=5)
tk.Button(search_frame, text='搜索',background='lightblue', command=lambda: refresh_tree(tree, dbapi.search_components(search_var.get().strip()))).pack(side='left', padx=5)
tk.Button(search_frame, text='全部',background='lightblue',  command=lambda: refresh_tree(tree)).pack(side='left', padx=5)

out_var = tk.StringVar()
tk.Label(search_frame, text='出库数量').pack(side='left', padx=15)
tk.Entry(search_frame, textvariable=out_var, width=8).pack(side='left')
def on_out():
    selected = tree.selection()
    if not selected:
        messagebox.showinfo("提示", "请选择一条记录")
        return
    cid = tree.item(selected[0], 'values')[0]
    try:
        out_num = int(out_var.get())
    except ValueError:
        messagebox.showerror("输入有误", "出库数量必须是整数")
        return
    if out_num <= 0:
        messagebox.showerror("输入有误", "出库数量必须大于0")
        return
    all_rows = dbapi.get_all_components()
    for row in all_rows:
        if str(row[0]) == str(cid):
            if row[4] < out_num:
                messagebox.showerror("库存不足", "库存不足！")
                return
            break
    dbapi.update_quantity_by_id(cid, -out_num)
    refresh_tree(tree)
    messagebox.showinfo("提示", "已完成出库")
tk.Button(search_frame, text='出库', command=on_out, bg='lightgreen').pack(side='left', padx=7)




# ------ 数据列表 ------
# ------ 数据列表 ------
columns = ['ID', '名称', '型号','封装', '数量', '总金额', '单价', '备注', '图片', '文档', '云端链接']

# 外部Frame包裹，避免和其他区域干扰
tree_frame = tk.Frame(frame_parent)
tree_frame.pack(fill='both', expand=True, padx=8, pady=3)

# 创建Scrollbars
vscroll = tk.Scrollbar(tree_frame, orient='vertical')
hscroll = tk.Scrollbar(tree_frame, orient='horizontal')

tree = ttk.Treeview(
    tree_frame,
    columns=columns,
    show='headings',
    selectmode='browse',
    yscrollcommand=vscroll.set,
    xscrollcommand=hscroll.set
)
for col in columns:
    tree.heading(col, text=col)
    tree.column(col, width=107, anchor='center')  # 也可以指定每列宽度，看你实际需求

# 布局
tree.grid(row=0, column=0, sticky='nsew')
vscroll.grid(row=0, column=1, sticky='ns')
hscroll.grid(row=1, column=0, sticky='ew')

tree_frame.rowconfigure(0, weight=1)
tree_frame.columnconfigure(0, weight=1)

# 关联滚动条
vscroll.config(command=tree.yview)
hscroll.config(command=tree.xview)


def on_right_click(event):
    iid = tree.identify_row(event.y)
    print('right click: iid:', iid)
    if iid:
        tree.selection_set(iid)
        menu = tk.Menu(root, tearoff=0)
        menu.add_command(label="删除", command=on_delete_record)
        menu.post(event.x_root, event.y_root)
tree.bind("<Button-3>", on_right_click)              # 右键菜单主流
tree.bind("<Button-2>", on_right_click)              # 某些X11环境鼠标右键
tree.bind("<Control-Button-1>", on_right_click)      # Mac下的“Ctrl+单击”当作右键

def on_delete_record():
    selected = tree.selection()
    if not selected:
        return
    cid = tree.item(selected[0], 'values')[0]
    if messagebox.askyesno("确认删除", "该操作会彻底删除此条目，及其关联图片/文档。确定吗？"):
        dbapi.delete_by_id(cid)
        refresh_tree(tree)
        # messagebox.showinfo("提示", "已从库中删除")




note_text = tk.Text(frame_parent, width=40,height=3,wrap='word',state='normal',)
note_text.config(bg="#f0f0f0",borderwidth=0.5,highlightthickness=0,)
note_text.pack(fill='x', padx=8, pady=6)


tool_frame = tk.Frame(frame_parent)
tool_frame.pack(fill='x', padx=8, pady=4)

left_frame = tk.Frame(tool_frame)
left_frame.pack(side='left', fill='x', expand=True)



def replace_img():
    selected = tree.selection()
    if not selected:
        messagebox.showinfo("提示", "请选择记录")
        return
    iid = tree.item(selected[0], 'values')
    cid = iid[0]
    name = iid[1]
    model = iid[2]
    img_path = filedialog.askopenfilename(filetypes=[("图片文件", "*.jpg *.jpeg *.png *.gif")])
    if img_path:
        ext = os.path.splitext(img_path)[-1]
        now = time.strftime('%Y%m%d%H%M%S')
        folder = os.path.join('src', 'img', name)
        os.makedirs(folder, exist_ok=True)
        basename = f"{name}-{model}-{now}{ext}"
        dst_path = os.path.join(folder, basename)
        shutil.copy(img_path, dst_path)
        dbapi.update_img_doc_by_id(cid, dst_path, None)
        refresh_tree(tree)
def replace_doc():
    selected = tree.selection()
    if not selected:
        messagebox.showinfo("提示", "请选择记录")
        return
    iid = tree.item(selected[0], 'values')
    cid = iid[0]
    name = iid[1]
    model = iid[2]
    doc_path = filedialog.askopenfilename(filetypes=[("文档", "*.pdf *.docx *.txt *.xlsx")])
    if doc_path:
        ext = os.path.splitext(doc_path)[-1]
        now = time.strftime('%Y%m%d%H%M%S')
        folder = os.path.join('src', 'document', name)
        os.makedirs(folder, exist_ok=True)
        basename = f"{name}-{model}-{now}{ext}"
        dst_path = os.path.join(folder, basename)
        shutil.copy(doc_path, dst_path)
        dbapi.update_img_doc_by_id(cid, None, dst_path)
        refresh_tree(tree)
def replace_cloud():
    selected = tree.selection()
    if not selected:
        messagebox.showinfo("提示", "请选择记录")
        return
    iid = tree.item(selected[0], 'values')
    cid = iid[0]
    win = tk.Toplevel(root)
    win.title("修改云端链接")
    tk.Label(win, text="新的云端链接：").pack(side='left')
    new_var = tk.StringVar()
    tk.Entry(win, textvariable=new_var, width=40).pack(side='left')
    def ok():
        dbapi.update_cloud_link_by_id(cid, new_var.get().strip())
        refresh_tree(tree)
        win.destroy()
    tk.Button(win, text="确定", command=ok).pack(side='left')
    win.transient(root)
    win.grab_set()
    win.wait_window(win)


mid_frame = tk.Frame(tool_frame)
mid_frame.pack(side='left', fill='x', expand=True)
right_frame = tk.Frame(tool_frame)
right_frame.pack(side='left', fill='x', expand=True)

tk.Button(right_frame, text="替换图片", command=replace_img).pack(side='left', padx=2)
tk.Button(right_frame, text="替换文档", command=replace_doc).pack(side='left', padx=2)
tk.Button(right_frame, text="修改云链", command=replace_cloud).pack(side='left', padx=2)



# ------ 预览及操作区 ------
preview_frame = tk.Frame(left_frame)
preview_frame.pack(fill='x', padx=5, pady=2)
img_preview_label = tk.Label(preview_frame, relief='flat', width=32, height=16)
img_preview_label.pack(side='left', padx=5, pady=5)
img_preview_label.config(image='', text='待展示图片', width=32, height=16, cursor="")
open_doc_button = tk.Button(preview_frame, text="打开文档", command=lambda: None)
open_doc_button.pack(side='left', padx=5)
open_doc_button.config(state='disabled')
open_cloud_button = tk.Button(preview_frame, text='打开云端文档', command=lambda: None)
open_cloud_button.pack(side='left', padx=5)
open_cloud_button.config(state='disabled')

def show_full_image(img_path):
    if img_path and os.path.isfile(img_path):
        ZoomImageViewer(root, img_path)

def get_selected_img_path():
    selected = tree.selection()
    if not selected:
        return None
    item = tree.item(selected[0], 'values')
    cid = item[0]
    conn = sqlite3.connect('components.db')
    c = conn.cursor()
    c.execute('SELECT img_path FROM components WHERE id=?', (cid,))
    row = c.fetchone()
    conn.close()
    if row and row[0] and os.path.isfile(row[0]):
        return row[0]
    return None

img_preview_label.bind("<Button-1>", lambda e: show_full_image(get_selected_img_path()))

# ------ 出库、替换、云链修改 ------



def brief_path(f):
    if not f:
        return ""
    return os.path.basename(f)

def open_document_file(path):
    try:
        if platform.system() == 'Windows':
            os.startfile(path)
        elif platform.system() == 'Darwin':
            subprocess.run(['open', path])
        else:
            subprocess.run(['xdg-open', path])
    except Exception as e:
        messagebox.showerror("打开文档失败", str(e))

def open_cloud_link(link):
    if link:
        webbrowser.open(link)

def refresh_tree(tree, rows=None):
    for i in tree.get_children():
        tree.delete(i)
    if rows is None:
        rows = dbapi.get_all_components()
    for row in rows:
        id_, name, model,package, qty, total_price, unit_price, note, img, doc, cloud = row
        tree.insert('', 'end', values=(id_, name, model,package, qty, total_price, unit_price, note, brief_path(img), brief_path(doc), cloud if cloud else ""))

def on_tree_select(event=None):
    img_preview_label.config(image='', text='', width=32, height=16, cursor="")
    open_doc_button.config(state='disabled', text="打开文档", command=lambda: None)
    open_cloud_button.config(state='disabled', text="打开云端文档", command=lambda: None)
    selected = tree.selection()
    if not selected:
        return
    item = tree.item(selected[0], 'values')
    cid = item[0]
    conn = sqlite3.connect('components.db')
    c = conn.cursor()
    c.execute('SELECT img_path, doc_path, cloud_link,note FROM components WHERE id=?', (cid,))
    row = c.fetchone()
    conn.close()
    img_path, doc_path, cloud_link ,note= row

    if img_path and os.path.isfile(img_path):
        try:
            target_w, target_h = 256, 256
            img = Image.open(img_path)
            # 填充并居中裁剪
            iw, ih = img.size
            rate_w = target_w / iw
            rate_h = target_h / ih
            rate = max(rate_w, rate_h)
            nsize = (int(iw * rate), int(ih * rate))
            img = img.resize(nsize, Image.LANCZOS)

            x1 = (img.width - target_w) // 2
            y1 = (img.height - target_h) // 2
            img = img.crop((x1, y1, x1 + target_w, y1 + target_h))

            tkimg = ImageTk.PhotoImage(img)
            img_preview_label.image = tkimg
            img_preview_label.config(image=tkimg, text='(点击放大)', width=target_w, height=target_h, cursor="hand2")
        except Exception as e:
            img_preview_label.config(image='', text='图片读取失败', width=32, height=16, cursor="")
    else:
        img_preview_label.config(image='', text='无图片', width=32, height=16, cursor="")
    if doc_path and os.path.isfile(doc_path):
        open_doc_button.config(
            state='normal',
            text="打开文档：" + os.path.basename(doc_path),
            command=lambda path=doc_path: open_document_file(path)
        )
    else:
        open_doc_button.config(state='disabled', text="打开文档", command=lambda: None)
    if cloud_link and cloud_link.lower().startswith("http"):
        open_cloud_button.config(
            state='normal',
            text="打开云端文档",
            command=lambda link=cloud_link: open_cloud_link(link)
        )
    else:
        open_cloud_button.config(state='disabled', text="打开云端文档", command=lambda: None)

    def show_remark(content):
        note_text.config(state='normal')      # 允许编辑
        note_text.delete('1.0', tk.END)       # 先清空原内容
        note_text.insert('1.0', content)      # 插入新内容
        note_text.config(state='disabled')  
    def clear_remark():
        note_text.config(state='normal')
        note_text.delete('1.0', tk.END)
        note_text.config(state='disabled')
    if note and len(note) > 0:
      # Assuming there's a Label or Text widget named note_label in mid_frame
        show_remark("备注:"+note)
    else:
        clear_remark()
        

tree.bind('<<TreeviewSelect>>', on_tree_select)
refresh_tree(tree)

root.mainloop()
