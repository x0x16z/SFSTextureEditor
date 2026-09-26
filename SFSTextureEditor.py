# -*- coding: utf-8 -*-
import os
import re
import json
import shutil
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


# ======================================================================
# 配色
# ======================================================================
BG              = "#EEF1F7"
CARD_BG         = "#FFFFFF"
CARD_HOVER      = "#F8FAFF"
BORDER          = "#E3E8F0"
BORDER_HOVER    = "#CBD8F0"
PRIMARY         = "#4F7BF7"
PRIMARY_HOV     = "#3D68E8"
PRIMARY_SOFT    = "#EAF0FE"
PRIMARY_SOFT_H  = "#D9E5FD"
FIELD_BG        = "#F4F7FC"
NEUTRAL_BTN     = "#E4E9F2"
NEUTRAL_BTN_H   = "#D6DDE9"
DANGER_SOFT     = "#FCE7E7"
TEXT            = "#1F2933"
TEXT_SUB        = "#5A6B85"
TEXT_MUTED      = "#9AA7BC"

FONT = "Microsoft YaHei UI"
THUMB = 54
ICON_SIZE = 40


# ======================================================================
# 通用工具
# ======================================================================
def hex_to_rgb(c):
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def rgb_to_hex(r, g, b):
    return "#%02x%02x%02x" % (max(0, min(255, int(round(r)))),
                              max(0, min(255, int(round(g)))),
                              max(0, min(255, int(round(b)))))


def lerp_color(c1, c2, t):
    r1, g1, b1 = hex_to_rgb(c1)
    r2, g2, b2 = hex_to_rgb(c2)
    return rgb_to_hex(r1 + (r2 - r1) * t,
                      g1 + (g2 - g1) * t,
                      b1 + (b2 - b1) * t)


def ease_out(t):
    return 1 - (1 - t) ** 3


def round_rect_pts(x1, y1, x2, y2, r):
    """生成圆角矩形多边形的控制点（返回元组）"""
    return (x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r, x1, y1 + r, x1, y1)


# ======================================================================
# 圆角按钮
# ======================================================================
class RoundedButton(tk.Canvas):
    def __init__(self, master, text="", command=None,
                 width=100, height=34, radius=10,
                 bg=CARD_BG, fill=PRIMARY, fill_hover=None,
                 text_color="#FFFFFF", font_size=10, bold=False):
        super().__init__(master, width=width, height=height, bg=bg,
                         highlightthickness=0, bd=0, cursor="hand2")

        self.command = command
        # 注意：不要用 self._w / self._h（Tkinter 内部占用）
        self._btn_w, self._btn_h = width, height
        self._fill = fill
        self._fill_hover = fill_hover or lerp_color(fill, "#000000", 0.10)
        self._t = 0.0
        self._target = 0.0
        self._anim_id = None

        pts = round_rect_pts(1, 1, width - 1, height - 1, radius)
        self._shape = self.create_polygon(*pts, smooth=True, splinesteps=24,
                                          fill=fill, outline="")

        self._text_id = None
        if text:
            fnt = (FONT, font_size, "bold") if bold else (FONT, font_size)
            self._text_id = self.create_text(width / 2, height / 2,
                                             text=text, fill=text_color,
                                             font=fnt)

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def _on_enter(self, _e):
        self._animate_to(1.0)

    def _on_leave(self, _e):
        self._animate_to(0.0)

    def _animate_to(self, target):
        self._target = target
        if self._anim_id is None:
            self._step()

    def _step(self):
        diff = self._target - self._t
        if abs(diff) < 0.015:
            self._t = self._target
            self._apply()
            self._anim_id = None
            return
        self._t += diff * 0.28
        self._apply()
        self._anim_id = self.after(12, self._step)

    def _apply(self):
        self.itemconfig(self._shape,
                        fill=lerp_color(self._fill, self._fill_hover, self._t))

    def _on_press(self, _e):
        self.itemconfig(self._shape,
                        fill=lerp_color(self._fill, "#000000", 0.10))

    def _on_release(self, e):
        self._apply()
        if 0 <= e.x <= self._btn_w and 0 <= e.y <= self._btn_h and self.command:
            self.command()


# ======================================================================
# 纹理卡片
# ======================================================================
class TextureCard(tk.Canvas):
    H = 88

    def __init__(self, master, app):
        super().__init__(master, height=self.H, bg=BG,
                         highlightthickness=0, bd=0)
        self.app = app
        self.image_path = None
        self._thumb_photo = None
        self._removing = False
        self._entering = False

        self._hover_t = 0.0
        self._hover_target = 0.0
        self._hover_anim = None

        pts = round_rect_pts(0, 0, 800, self.H, 14)
        self._bg_item = self.create_polygon(*pts, smooth=True, splinesteps=32,
                                            fill=BG, outline=BG, width=1)

        # 名称输入
        self.name_var = tk.StringVar()
        self.name_entry = tk.Entry(
            self, textvariable=self.name_var,
            relief="flat", bd=0,
            bg=FIELD_BG, fg=TEXT,
            insertbackground=PRIMARY,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=PRIMARY,
            font=(FONT, 10))
        self._name_win = self.create_window(18, 27, window=self.name_entry,
                                            anchor="nw", width=260, height=34)

        # 导入按钮
        self.import_btn = RoundedButton(
            self, text="导入图片", command=self.choose_image,
            width=94, height=34, radius=10, bg=CARD_BG,
            fill=PRIMARY_SOFT, fill_hover=PRIMARY_SOFT_H,
            text_color=PRIMARY, font_size=10)
        self._import_win = self.create_window(0, 27, window=self.import_btn,
                                              anchor="nw")

        # 预览
        self.preview = tk.Label(self, image=app.placeholder, bg=FIELD_BG,
                                bd=0, highlightthickness=1,
                                highlightbackground=BORDER,
                                cursor="hand2")
        self.preview.bind("<Button-1>", self.show_large)
        self._preview_win = self.create_window(0, 16, window=self.preview,
                                               anchor="nw", width=56, height=56)

        # 删除
        self.del_btn = RoundedButton(
            self, text="✕", command=self.remove,
            width=32, height=32, radius=9, bg=CARD_BG,
            fill=FIELD_BG, fill_hover=DANGER_SOFT,
            text_color=TEXT_MUTED, font_size=11)
        self._del_win = self.create_window(0, 28, window=self.del_btn,
                                           anchor="nw")

        self.bind("<Configure>", self._on_resize)
        for w in (self, self.name_entry, self.import_btn,
                  self.preview, self.del_btn):
            w.bind("<Enter>", self._on_enter, add="+")
            w.bind("<Leave>", self._on_leave, add="+")

    def _on_resize(self, e):
        if e.width > 60:
            self._layout(e.width)

    def _layout(self, w):
        h = self.H
        self.coords(self._bg_item, *round_rect_pts(0.5, 0.5, w - 0.5, h - 0.5, 14))

        del_x = w - 16 - 32
        prev_x = del_x - 12 - 56
        imp_x = prev_x - 14 - 94
        name_x = 18
        name_w = max(90, imp_x - 14 - name_x)

        mid = h // 2
        self.coords(self._name_win, name_x, mid - 17)
        self.itemconfigure(self._name_win, width=name_w)
        self.coords(self._import_win, imp_x, mid - 17)
        self.coords(self._preview_win, prev_x, mid - 28)
        self.coords(self._del_win, del_x, mid - 16)

    # ---------- 入场 ----------
    def play_enter(self):
        self._entering = True
        self._enter_t = 0.0
        self._enter_step()

    def _enter_step(self):
        self._enter_t = min(1.0, self._enter_t + 0.13)
        t = ease_out(self._enter_t)
        self.itemconfig(self._bg_item,
                        fill=lerp_color(BG, CARD_BG, t),
                        outline=lerp_color(BG, BORDER, t))
        if self._enter_t < 1.0:
            self.after(14, self._enter_step)
        else:
            self._entering = False
            if self._hover_target > 0:
                self._apply_hover()

    # ---------- 悬停 ----------
    def _pointer_inside(self):
        try:
            x, y = self.winfo_pointerxy()
            w = self.winfo_containing(x, y)
        except Exception:
            return False
        while w is not None:
            if w is self:
                return True
            w = getattr(w, "master", None)
        return False

    def _on_enter(self, _e):
        self._animate_hover(1.0)

    def _on_leave(self, _e):
        self.after(30, self._maybe_leave)

    def _maybe_leave(self):
        if not self._pointer_inside():
            self._animate_hover(0.0)

    def _animate_hover(self, target):
        if self._entering:
            return
        self._hover_target = target
        if self._hover_anim is None:
            self._hover_step()

    def _hover_step(self):
        diff = self._hover_target - self._hover_t
        if abs(diff) < 0.015:
            self._hover_t = self._hover_target
            self._apply_hover()
            self._hover_anim = None
            return
        self._hover_t += diff * 0.25
        self._apply_hover()
        self._hover_anim = self.after(14, self._hover_step)

    def _apply_hover(self):
        self.itemconfig(self._bg_item,
                        fill=lerp_color(CARD_BG, CARD_HOVER, self._hover_t),
                        outline=lerp_color(BORDER, BORDER_HOVER, self._hover_t))

    # ---------- 导入图片 ----------
    def choose_image(self):
        path = filedialog.askopenfilename(
            title="选择纹理图片",
            filetypes=[("图片文件", "*.png *.jpg *.jpeg *.bmp *.gif *.tga *.webp"),
                       ("所有文件", "*.*")])
        if path:
            self.load_image(path)

    def load_image(self, path):
        try:
            thumb = self._make_thumb(path)
        except Exception as ex:
            messagebox.showerror("错误",
                                 "无法打开图片：\n%s\n\n%s" % (path, ex),
                                 parent=self.app)
            return

        self.image_path = path
        self._thumb_photo = thumb
        self.preview.configure(image=thumb)

        # ★ 如果名称为空，自动同步为文件名（去掉扩展名）
        if not self.name_var.get().strip():
            base = os.path.splitext(os.path.basename(path))[0]
            self.name_var.set(base)

    def _make_thumb(self, path):
        if HAS_PIL:
            img = Image.open(path).convert("RGBA")
            img.thumbnail((THUMB, THUMB), Image.LANCZOS)
            canvas = Image.new("RGBA", (THUMB, THUMB), FIELD_BG)
            ox = (THUMB - img.width) // 2
            oy = (THUMB - img.height) // 2
            canvas.paste(img, (ox, oy), img)
            return ImageTk.PhotoImage(canvas)
        else:
            img = tk.PhotoImage(file=path)
            w, h = img.width(), img.height()
            f = max(1, -(-max(w, h) // THUMB))
            if f > 1:
                img = img.subsample(f, f)
            return img

    # ---------- 放大预览 ----------
    def show_large(self, _e=None):
        if not self.image_path:
            messagebox.showinfo("提示", "这一项还没有导入图片。", parent=self.app)
            return
        name = self.name_var.get().strip() or os.path.basename(self.image_path)
        self.app.show_image_window(self.image_path, "预览 · %s" % name)

    # ---------- 删除 ----------
    def remove(self):
        if self._removing:
            return
        self._removing = True
        for item in (self._name_win, self._import_win,
                     self._preview_win, self._del_win, self._bg_item):
            self.itemconfigure(item, state="hidden")
        self._collapse()

    def _collapse(self):
        h = self.winfo_height()
        if h <= 8:
            if self in self.app.items:
                self.app.items.remove(self)
            self.app._refresh_count()
            self.destroy()
            return
        self.configure(height=max(8, int(h * 0.68)))
        self.after(10, self._collapse)


# ======================================================================
# 主窗口
# ======================================================================
class App(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("SpaceFlightSimulator纹理制作")
        self.geometry("920x800")
        self.minsize(820, 700)
        self.configure(bg=BG)

        global FONT
        try:
            fams = set(tkfont.families(self))
            for f in ("Microsoft YaHei UI", "PingFang SC", "Noto Sans CJK SC",
                      "Source Han Sans SC", "WenQuanYi Micro Hei",
                      "Segoe UI", "Helvetica"):
                if f in fams:
                    FONT = f
                    break
        except Exception:
            pass

        self.items = []
        self._scroll_target = 0.0
        self._scroll_anim_id = None

        # ---- 包信息变量 ----
        self.pack_name_var = tk.StringVar()
        self.version_var = tk.StringVar(value="1.0.0")
        self.desc_var = tk.StringVar()
        self.author_var = tk.StringVar()
        self.icon_enabled_var = tk.BooleanVar(value=False)
        self.zip_var = tk.BooleanVar(value=False)          # ★ 打包为 zip

        self.icon_path = None
        self._icon_thumb = None

        # ---- 占位图 ----
        self.placeholder = self._make_placeholder(THUMB)
        self.icon_placeholder = self._make_placeholder(ICON_SIZE)

        self._setup_style()
        self._build()

        self.bind_all("<MouseWheel>", self._on_wheel)
        self.bind_all("<Button-4>", self._on_wheel)
        self.bind_all("<Button-5>", self._on_wheel)

        self.add_item()
        self._refresh_count()
        self._on_icon_toggle()

        if not HAS_PIL:
            self.after(500, lambda: messagebox.showwarning(
                "提示",
                "未检测到 Pillow 库（pip install pillow），\n"
                "预览图缩放会比较粗糙，且非 PNG 图片将无法导出。",
                parent=self))

    def _make_placeholder(self, size):
        img = tk.PhotoImage(width=size, height=size)
        img.put(FIELD_BG, to=(0, 0, size, size))
        c = "#C3CFDF"
        cx, cy = size // 2, size // 2
        arm = max(6, size // 6)
        img.put(c, to=(cx - arm, cy - 1, cx + arm + 1, cy + 2))
        img.put(c, to=(cx - 1, cy - arm, cx + 2, cy + arm + 1))
        return img

    def _setup_style(self):
        st = ttk.Style(self)
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        st.configure("Slim.Vertical.TScrollbar",
                     troughcolor=BG, background="#C8D4E6",
                     darkcolor="#C8D4E6", lightcolor="#C8D4E6",
                     bordercolor=BG, arrowcolor=BG,
                     borderwidth=0, arrowsize=1, width=8)
        st.map("Slim.Vertical.TScrollbar",
               background=[("active", "#A9BAD4")])

    # ------------------------------------------------------------------
    def _build(self):
        # ===== 标题 =====
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=28, pady=(22, 0))

        tk.Label(header, text="SpaceFlightSimulator 纹理制作",
                 bg=BG, fg=TEXT,
                 font=(FONT, 17, "bold")).pack(anchor="w")
        tk.Label(header, text="为纹理包添加纹理 · 支持导入图片与实时预览",
                 bg=BG, fg=TEXT_MUTED,
                 font=(FONT, 9)).pack(anchor="w", pady=(4, 0))

        # ===== 工具栏 =====
        toolbar = tk.Frame(self, bg=BG)
        toolbar.pack(fill="x", padx=28, pady=(18, 0))

        self.add_btn = RoundedButton(
            toolbar, text="＋  添加纹理", command=self.add_item,
            width=122, height=36, radius=11, bg=BG,
            fill=PRIMARY, fill_hover=PRIMARY_HOV,
            text_color="#FFFFFF", font_size=10, bold=True)
        self.add_btn.pack(side="left")

        self.clear_btn = RoundedButton(
            toolbar, text="清空列表", command=self.clear_items,
            width=90, height=36, radius=11, bg=BG,
            fill=NEUTRAL_BTN, fill_hover=NEUTRAL_BTN_H,
            text_color=TEXT_SUB, font_size=10)
        self.clear_btn.pack(side="left", padx=10)

        self.count_lbl = tk.Label(toolbar, text="", bg=BG, fg=TEXT_MUTED,
                                  font=(FONT, 9))
        self.count_lbl.pack(side="right")

        # =============================================================
        # 底部（自下而上 pack）
        # =============================================================

        # ---- 1. 最底部：状态 + ZIP 勾选 + 制作按钮 ----
        action_row = tk.Frame(self, bg=BG)
        action_row.pack(side="bottom", fill="x", padx=28, pady=(0, 20))

        self.status_lbl = tk.Label(action_row, text="", bg=BG, fg=TEXT_MUTED,
                                   font=(FONT, 9))
        self.status_lbl.pack(side="left")

        self.make_btn = RoundedButton(
            action_row, text="制  作", command=self.on_make,
            width=140, height=42, radius=12, bg=BG,
            fill=PRIMARY, fill_hover=PRIMARY_HOV,
            text_color="#FFFFFF", font_size=11, bold=True)
        self.make_btn.pack(side="right")

        # ★ 打包为 zip 勾选框（在制作按钮左侧）
        self.zip_check = tk.Checkbutton(
            action_row, text="打包为 .zip",
            variable=self.zip_var,
            bg=BG, fg=TEXT_SUB,
            activebackground=BG, activeforeground=TEXT,
            selectcolor=CARD_BG,
            font=(FONT, 10), bd=0, highlightthickness=0,
            cursor="hand2")
        self.zip_check.pack(side="right", padx=(0, 16))

        # ---- 2. 包信息卡片 ----
        info_wrap = tk.Frame(self, bg=BG)
        info_wrap.pack(side="bottom", fill="x", padx=28, pady=(10, 0))

        info_card = tk.Frame(info_wrap, bg=CARD_BG,
                             highlightthickness=1,
                             highlightbackground=BORDER)
        info_card.pack(fill="x")
        info_card.columnconfigure(1, weight=3)
        info_card.columnconfigure(3, weight=2)
        info_card.columnconfigure(5, weight=2)

        def make_entry(parent, var):
            return tk.Entry(parent, textvariable=var, width=1,
                            relief="flat", bd=0,
                            bg=FIELD_BG, fg=TEXT,
                            insertbackground=PRIMARY,
                            highlightthickness=1,
                            highlightbackground=BORDER,
                            highlightcolor=PRIMARY,
                            font=(FONT, 10))

        lbl_kw = dict(bg=CARD_BG, fg=TEXT_SUB, font=(FONT, 10))

        # Row 0: 名称 | 版本 | 作者
        tk.Label(info_card, text="纹理包名称", **lbl_kw).grid(
            row=0, column=0, sticky="w", padx=(16, 8), pady=(14, 6))

        self.pack_entry = make_entry(info_card, self.pack_name_var)
        self.pack_entry.grid(row=0, column=1, sticky="ew",
                             padx=(0, 16), pady=(14, 6), ipady=5)

        tk.Label(info_card, text="版本", **lbl_kw).grid(
            row=0, column=2, sticky="w", padx=(0, 8), pady=(14, 6))

        self.version_entry = make_entry(info_card, self.version_var)
        self.version_entry.grid(row=0, column=3, sticky="ew",
                                padx=(0, 16), pady=(14, 6), ipady=5)

        tk.Label(info_card, text="作者", **lbl_kw).grid(
            row=0, column=4, sticky="w", padx=(0, 8), pady=(14, 6))

        self.author_entry = make_entry(info_card, self.author_var)
        self.author_entry.grid(row=0, column=5, sticky="ew",
                               padx=(0, 16), pady=(14, 6), ipady=5)

        # Row 1: 描述
        tk.Label(info_card, text="描述", **lbl_kw).grid(
            row=1, column=0, sticky="w", padx=(16, 8), pady=(0, 6))

        self.desc_entry = make_entry(info_card, self.desc_var)
        self.desc_entry.grid(row=1, column=1, columnspan=5, sticky="ew",
                             padx=(0, 16), pady=(0, 6), ipady=5)

        # Row 2: ICON 区域
        icon_row = tk.Frame(info_card, bg=CARD_BG)
        icon_row.grid(row=2, column=0, columnspan=6, sticky="ew",
                      padx=16, pady=(6, 14))

        self.icon_check = tk.Checkbutton(
            icon_row, text="启用 ICON",
            variable=self.icon_enabled_var,
            command=self._on_icon_toggle,
            bg=CARD_BG, fg=TEXT_SUB,
            activebackground=CARD_BG, activeforeground=TEXT,
            selectcolor=CARD_BG,
            font=(FONT, 10), bd=0, highlightthickness=0,
            cursor="hand2")
        self.icon_check.pack(side="left")

        self.icon_import_btn = RoundedButton(
            icon_row, text="导入 ICON", command=self._choose_icon,
            width=104, height=32, radius=9, bg=CARD_BG,
            fill=PRIMARY_SOFT, fill_hover=PRIMARY_SOFT_H,
            text_color=PRIMARY, font_size=10)
        self.icon_import_btn.pack(side="left", padx=(16, 12))

        self.icon_preview = tk.Label(icon_row, image=self.icon_placeholder,
                                     bg=FIELD_BG, cursor="hand2",
                                     bd=0, highlightthickness=1,
                                     highlightbackground=BORDER)
        self.icon_preview.pack(side="left")
        self.icon_preview.bind("<Button-1>", self._show_icon_large)

        self.icon_status = tk.Label(icon_row, text="未导入 ICON",
                                    bg=CARD_BG, fg=TEXT_MUTED,
                                    font=(FONT, 9))
        self.icon_status.pack(side="left", padx=12)

        # ---- 3. 分隔线 ----
        tk.Frame(self, bg=BORDER, height=1).pack(
            side="bottom", fill="x", padx=28, pady=(0, 0))

        # ---- 4. 列表区域 ----
        list_wrap = tk.Frame(self, bg=BG)
        list_wrap.pack(fill="both", expand=True, padx=(28, 20), pady=(16, 8))

        self.canvas = tk.Canvas(list_wrap, bg=BG, highlightthickness=0, bd=0)
        self.canvas.pack(side="left", fill="both", expand=True)

        self.vbar = ttk.Scrollbar(list_wrap, orient="vertical",
                                  command=self.canvas.yview,
                                  style="Slim.Vertical.TScrollbar")
        self.vbar.pack(side="right", fill="y", padx=(8, 0))
        self.canvas.configure(yscrollcommand=self.vbar.set)

        self.list_frame = tk.Frame(self.canvas, bg=BG)
        self._list_win = self.canvas.create_window((0, 0), window=self.list_frame,
                                                   anchor="nw")

        self.list_frame.bind("<Configure>", self._on_list_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    def _on_list_configure(self, _e):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, e):
        self.canvas.itemconfigure(self._list_win, width=e.width)

    # ------------------------------------------------------------------
    # ICON 相关
    # ------------------------------------------------------------------
    def _choose_icon(self):
        path = filedialog.askopenfilename(
            title="选择 ICON 图片",
            filetypes=[("图片文件", "*.png *.jpg *.jpeg *.bmp *.gif *.tga *.webp"),
                       ("所有文件", "*.*")])
        if path:
            self._load_icon(path)

    def _load_icon(self, path):
        try:
            thumb = self._make_icon_thumb(path)
        except Exception as ex:
            messagebox.showerror("错误",
                                 "无法打开图片：\n%s\n\n%s" % (path, ex),
                                 parent=self)
            return
        self.icon_path = path
        self._icon_thumb = thumb
        self.icon_preview.configure(image=thumb)
        self.icon_status.configure(text=os.path.basename(path))

        if not self.icon_enabled_var.get():
            self.icon_enabled_var.set(True)
            self._on_icon_toggle()

    def _make_icon_thumb(self, path):
        size = ICON_SIZE
        if HAS_PIL:
            img = Image.open(path).convert("RGBA")
            img.thumbnail((size, size), Image.LANCZOS)
            canvas = Image.new("RGBA", (size, size), FIELD_BG)
            ox = (size - img.width) // 2
            oy = (size - img.height) // 2
            canvas.paste(img, (ox, oy), img)
            return ImageTk.PhotoImage(canvas)
        else:
            img = tk.PhotoImage(file=path)
            w, h = img.width(), img.height()
            f = max(1, -(-max(w, h) // size))
            if f > 1:
                img = img.subsample(f, f)
            return img

    def _on_icon_toggle(self):
        if self.icon_enabled_var.get():
            self.icon_preview.configure(highlightbackground=PRIMARY)
            if self.icon_path:
                self.icon_status.configure(fg=TEXT_SUB)
        else:
            self.icon_preview.configure(highlightbackground=BORDER)
            self.icon_status.configure(fg=TEXT_MUTED)

    def _show_icon_large(self, _e=None):
        if not self.icon_path:
            messagebox.showinfo("提示", "还没有导入 ICON。", parent=self)
            return
        self.show_image_window(self.icon_path, "ICON 预览")

    # ------------------------------------------------------------------
    # 放大预览窗口
    # ------------------------------------------------------------------
    def show_image_window(self, path, title_text):
        win = tk.Toplevel(self)
        win.title(title_text)
        win.configure(bg=CARD_BG)

        try:
            if HAS_PIL:
                img = Image.open(path)
                mw = win.winfo_screenwidth() - 180
                mh = win.winfo_screenheight() - 240
                if img.width > mw or img.height > mh:
                    img.thumbnail((mw, mh), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
            else:
                photo = tk.PhotoImage(file=path)
        except Exception as ex:
            win.destroy()
            messagebox.showerror("错误", "无法显示图片：\n%s" % ex, parent=self)
            return

        win.photo = photo
        tk.Label(win, image=photo, bg=CARD_BG).pack(padx=18, pady=(18, 8))
        tk.Label(win, text=path, bg=CARD_BG, fg=TEXT_MUTED,
                 font=(FONT, 9)).pack(pady=(0, 16))

        win.transient(self)
        win.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - win.winfo_width()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - win.winfo_height()) // 2
        win.geometry("+%d+%d" % (max(0, x), max(0, y)))

    # ------------------------------------------------------------------
    # 列表增删
    # ------------------------------------------------------------------
    def add_item(self, name="", path=None):
        card = TextureCard(self.list_frame, self)
        card.pack(fill="x", pady=(0, 10))
        self.items.append(card)

        if name:
            card.name_var.set(name)
        if path:
            card.load_image(path)

        self._refresh_count()
        card.after(20, card.play_enter)
        self.after(40, self._scroll_to_bottom)
        card.name_entry.focus_set()
        return card

    def clear_items(self):
        if not self.items:
            return
        if messagebox.askyesno("确认", "确定要清空整个列表吗？", parent=self):
            for card in list(self.items):
                card.remove()

    def _refresh_count(self):
        n = len(self.items)
        self.count_lbl.configure(text=("%d 个纹理" % n) if n else "还没有纹理")

    # ------------------------------------------------------------------
    # 平滑滚动
    # ------------------------------------------------------------------
    def _on_wheel(self, event):
        try:
            w = self.winfo_containing(event.x_root, event.y_root)
        except Exception:
            w = None
        inside = False
        t = w
        while t is not None:
            if t is self.canvas or t is self.list_frame:
                inside = True
                break
            t = getattr(t, "master", None)
        if not inside:
            return

        num = getattr(event, "num", 0)
        if num == 4:
            d = -1
        elif num == 5:
            d = 1
        else:
            delta = getattr(event, "delta", 0)
            if delta == 0:
                return
            d = -1 if delta > 0 else 1
            d *= max(1, abs(delta) // 120)

        self._scroll_by(d * 72)

    def _scroll_by(self, px):
        bbox = self.canvas.bbox("all")
        if not bbox:
            return
        H = bbox[3] - bbox[1]
        V = self.canvas.winfo_height()
        if H <= V:
            return

        max_off = H - V
        cur = self.canvas.yview()[0] * H
        self._scroll_target = max(0.0, min(float(max_off), cur + px))

        if self._scroll_anim_id is None:
            self._scroll_step()

    def _scroll_to_bottom(self):
        self.canvas.update_idletasks()
        bbox = self.canvas.bbox("all")
        if not bbox:
            return
        H = bbox[3] - bbox[1]
        V = self.canvas.winfo_height()
        if H <= V:
            return
        self._scroll_target = float(H - V)
        if self._scroll_anim_id is None:
            self._scroll_step()

    def _scroll_step(self):
        bbox = self.canvas.bbox("all")
        if not bbox:
            self._scroll_anim_id = None
            return

        H = bbox[3] - bbox[1]
        V = self.canvas.winfo_height()
        max_off = max(1.0, H - V)

        cur = self.canvas.yview()[0] * H
        diff = self._scroll_target - cur

        if abs(diff) < 0.8:
            self.canvas.yview_moveto(max(0.0, min(1.0, self._scroll_target / H)))
            self._scroll_anim_id = None
            return

        new = cur + diff * 0.30
        self.canvas.yview_moveto(max(0.0, min(1.0, new / H)))
        self._scroll_anim_id = self.after(10, self._scroll_step)

    # ------------------------------------------------------------------
    # 数据获取
    # ------------------------------------------------------------------
    def get_all_items(self):
        return [{"name": c.name_var.get().strip(), "path": c.image_path}
                for c in self.items]

    def get_pack_info(self):
        return {
            "name":      self.pack_name_var.get().strip(),
            "version":   self.version_var.get().strip(),
            "desc":      self.desc_var.get().strip(),
            "author":    self.author_var.get().strip(),
            "use_icon":  self.icon_enabled_var.get(),
            "icon_path": self.icon_path,
            "zip":       self.zip_var.get(),
        }

    # ==================================================================
    # 制作纹理包
    # ==================================================================
    def on_make(self):
        """选择目录 → 创建文件夹并写入内容 →（可选）压缩为 zip 并删除原文件夹"""

        # ---------- 1. 校验 ----------
        pack_name = self.pack_name_var.get().strip()
        if not pack_name:
            messagebox.showwarning("提示", "请先填写纹理包名称。", parent=self)
            return

        textures = []          # [(名称, 图片路径), ...]
        for card in self.items:
            n = card.name_var.get().strip()
            p = card.image_path
            if n and p:
                textures.append((n, p))

        if not textures:
            messagebox.showwarning(
                "提示", "请至少添加一项完整的纹理（名称 + 图片）。", parent=self)
            return

        # ---------- 2. 选择导出位置 ----------
        out_root = filedialog.askdirectory(title="选择导出位置", parent=self)
        if not out_root:
            return

        # ---------- 3. 开始导出 ----------
        self.status_lbl.configure(text="正在导出…", fg=TEXT_SUB)
        self.update_idletasks()

        try:
            folder_name = self._safe_filename(pack_name)
            pack_dir = os.path.join(out_root, folder_name)

            if os.path.exists(pack_dir):
                if not messagebox.askyesno(
                        "确认",
                        "目标文件夹已存在：\n%s\n\n继续将覆盖同名文件，是否继续？"
                        % pack_dir, parent=self):
                    self.status_lbl.configure(text="")
                    return
            os.makedirs(pack_dir, exist_ok=True)

            ct_dir = os.path.join(pack_dir, "Color Textures")
            tex_dir = os.path.join(pack_dir, "Textures")
            os.makedirs(ct_dir, exist_ok=True)
            os.makedirs(tex_dir, exist_ok=True)

            # ---------- 4. ICON：复制（必要时转 PNG） ----------
            icon_filename = ""
            if self.icon_path and os.path.exists(self.icon_path):
                icon_filename = self._copy_image_as_png(
                    self.icon_path, pack_dir, "icon")

            # ---------- 5. 写入 pack_info.txt ----------
            pack_info = {
                "DisplayName": pack_name,
                "Version":     self.version_var.get().strip(),
                "Description": self.desc_var.get().strip(),
                "Author":      self.author_var.get().strip(),
                "ShowIcon":    bool(self.icon_enabled_var.get()),
                "Icon":        icon_filename,
                "name":        "",
                "hideFlags":   0,
            }
            self._write_json(os.path.join(pack_dir, "pack_info.txt"), pack_info)

            # ---------- 6. 每个纹理：复制图片 + 写入 Color Textures/xxx.txt ----------
            for name, path in textures:
                png_name = self._copy_image_as_png(path, tex_dir, name)
                data = self._make_colortex_data(png_name)
                txt_name = self._safe_filename(name) + ".txt"
                self._write_json(os.path.join(ct_dir, txt_name), data)

            # ---------- 7.（可选）打包为 zip ----------
            final_path = pack_dir
            if self.zip_var.get():
                self.status_lbl.configure(text="正在压缩…", fg=TEXT_SUB)
                self.update_idletasks()

                zip_base = os.path.join(out_root, folder_name)   # 不带 .zip
                # 若已存在同名 zip 则先删除，避免 make_archive 追加
                old_zip = zip_base + ".zip"
                if os.path.exists(old_zip):
                    try:
                        os.remove(old_zip)
                    except OSError:
                        pass

                # 以 out_root 为根，pack_dir 作为压缩包内的顶层目录
                final_path = shutil.make_archive(
                    zip_base, "zip", root_dir=out_root, base_dir=folder_name)

                # 删除原文件夹
                shutil.rmtree(pack_dir, ignore_errors=True)

            # ---------- 8. 完成 ----------
            self.status_lbl.configure(text="已导出：%s" % final_path, fg=TEXT_SUB)
            messagebox.showinfo(
                "完成",
                "纹理包已成功导出到：\n%s\n\n共 %d 个纹理。"
                % (final_path, len(textures)),
                parent=self)

        except Exception as e:
            self.status_lbl.configure(text="")
            messagebox.showerror("导出失败", str(e), parent=self)

    # ------------------------------------------------------------------
    # 导出辅助
    # ------------------------------------------------------------------
    @staticmethod
    def _safe_filename(name):
        """把名称里不合法的文件名字符替换为下划线"""
        name = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", str(name)).strip()
        return name or "texture"

    @staticmethod
    def _write_json(path, data):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _copy_image_as_png(self, src, dst_dir, base_name):
        """把 src 图片复制 / 转换为 dst_dir/base_name.png，返回目标文件名"""
        out_name = self._safe_filename(base_name) + ".png"
        out_path = os.path.join(dst_dir, out_name)

        if HAS_PIL:
            img = Image.open(src).convert("RGBA")
            img.save(out_path, "PNG")
        else:
            ext = os.path.splitext(src)[1].lower()
            if ext != ".png":
                raise RuntimeError(
                    "需要安装 Pillow 才能把非 PNG 图片转换为 PNG：\n%s" % src)
            shutil.copy2(src, out_path)

        return out_name

    def _make_colortex_data(self, file_name):
        """生成 Color Textures/xxx.txt 的 JSON 内容"""
        return {
            "colorTex": {
                "textures": [
                    {
                        "texture": file_name,
                        "ideal": 0.0
                    }
                ],
                "border_Bottom": {
                    "uvSize": 0.0,
                    "sizeMode": 0,
                    "size": 0.5
                },
                "border_Top": {
                    "uvSize": 0.0,
                    "sizeMode": 0,
                    "size": 0.5
                },
                "center": {
                    "mode": 1,
                    "sizeMode": 0,
                    "size": 4.9,
                    "logoHeightPercent": 0.85,
                    "scaleLogoToFit": False
                },
                "fixedWidth": True,
                "fixedWidthValue": 3.75,
                "flipToLight_X": False,
                "flipToLight_Y": False,
                "metalTexture": False,
                "icon": None
            },
            "tags": [
                "tank",
                "cone",
                "fairing",
                "probe"
            ],
            "pack_Redstone_Atlas": True,
            "multiple": False,
            "segments": [],
            "name": file_name,
            "hideFlags": 0
        }


if __name__ == "__main__":
    App().mainloop()