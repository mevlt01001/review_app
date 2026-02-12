import os
import sys
import json
import shutil
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font as tkfont
from clang import cindex

# --- LLVM / CLANG AYARI ---
# conda_lib = os.path.join(sys.prefix, 'lib', 'libclang.so')
# if os.path.exists(conda_lib):
#     cindex.Config.set_library_file(conda_lib)
# else:
# cindex.Config.set_library_path("/usr/lib/llvm-*/lib")

import collections.abc
if sys.version_info >= (3, 10):
    import collections
    collections.Iterable = collections.abc.Iterable

from spiral import ronin

DEFAULT_INCLUDE_PATHS = [
    "/usr/include/c++/11", 
    "/usr/include/x86_64-linux-gnu/c++/11",
    "/usr/include",
    "/usr/local/cuda/include",
    "/opt/nvidia/deepstream/deepstream-7.1/sources/includes",
]

CASE_OPTIONS = [
    "lower_case", "UPPER_CASE", "camelBack", "CamelCase",
    "camel_Snake_Back", "Camel_Snake_Case", "aNy_CasE", "Leading_upper_snake_case"
]

OPTIONS_MAP = {
    'var': ['readability-identifier-naming.VariableCase', cindex.CursorKind.VAR_DECL],
    'func': ['readability-identifier-naming.FunctionCase', cindex.CursorKind.FUNCTION_DECL],
    'cls': ['readability-identifier-naming.ClassCase', cindex.CursorKind.CLASS_DECL]
}

def to_format(words:str, target_format):
    if not words: return ""
    if target_format == "lower_case":
        return "_".join(w.lower() for w in words)
    elif target_format == "UPPER_CASE":
        return "_".join(w.upper() for w in words)
    elif target_format == "camelBack":
        return "".join(w.lower() if i==0 else w.capitalize() for i, w in enumerate(words))
    elif target_format == "CamelCase":
        return "".join(w.capitalize() for w in words)
    elif target_format == "camel_Snake_Back":
        return "_".join(w.lower() if i==0 else w.capitalize() for i, w in enumerate(words))
    elif target_format == "Camel_Snake_Case":
        return "_".join(w.capitalize() for w in words)
    elif target_format == "Leading_upper_snake_case":
        return "_".join(w.capitalize() if i ==0 else w.lower() for i, w in enumerate(words))
    elif target_format == "aNy_CasE":
        return "_".join(w.lower() for w in words)

class NLPLinterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AKSS Refactor Tool")
        self.root.geometry("1150x850")
        
        self.found_symbols = {}
        self.all_project_files = []
        self.backup_dir = ".linter_backups"
        
        # --- FONT VE STİL AYARLARI ---
        self._apply_style()
        self._setup_ui()

    def _apply_style(self):
        # Modern bir font ailesi seçelim (Linux'ta genelde DejaVu Sans veya Ubuntu bulunur)
        self.main_font = ("Helvetica", 10)
        self.bold_font = ("Helvetica", 10, "bold")
        self.mono_font = ("DejaVu Sans Mono", 9) # Kod önizlemesi için
        
        style = ttk.Style()
        style.theme_use('clam') # Linux için en stabil ve özelleştirilebilir tema
        
        # Genel font ayarları
        style.configure(".", font=self.main_font, background="#f5f5f5")
        style.configure("TLabel", foreground="#333333")
        style.configure("TLabelframe", background="#f5f5f5", relief="groove")
        style.configure("TLabelframe.Label", font=self.bold_font, foreground="#0056b3")
        
        # Buton Stilleri
        style.configure("TButton", padding=5, font=self.bold_font)
        style.map("TButton",
                  background=[('active', '#e1e1e1'), ('pressed', '#cccccc')],
                  foreground=[('active', '#000000')])
        
        # Treeview (Liste) Stili
        style.configure("Treeview", 
                        font=self.main_font, 
                        rowheight=25,
                        fieldbackground="white")
        style.configure("Treeview.Heading", font=self.bold_font)

    def _setup_ui(self):
        # Ana Konteynır
        main_container = ttk.Frame(self.root, padding=15)
        main_container.pack(fill="both", expand=True)

        # Dizin ve Include Ayarları
        path_frame = ttk.LabelFrame(main_container, text="Project ve Builder Configuration", padding=15)
        path_frame.pack(fill="x", pady=10)

        # Src Path [cite: 32]
        ttk.Label(path_frame, text="Source:").grid(row=0, column=0, sticky="w", pady=5)
        self.src_path = tk.StringVar(value=os.getcwd())
        ttk.Entry(path_frame, textvariable=self.src_path, font=self.main_font).grid(row=0, column=1, sticky="ew", padx=10)
        ttk.Button(path_frame, text="Browse", command=lambda: self._browse_dir(self.src_path)).grid(row=0, column=2)

        # Include Path [cite: 33]
        ttk.Label(path_frame, text="Include:").grid(row=1, column=0, sticky="w", pady=5)
        self.inc_path = tk.StringVar(value=os.getcwd())
        ttk.Entry(path_frame, textvariable=self.inc_path, font=self.main_font).grid(row=1, column=1, sticky="ew", padx=10)
        ttk.Button(path_frame, text="Browse", command=lambda: self._browse_dir(self.inc_path)).grid(row=1, column=2)

        # Extra Include Paths 
        ttk.Label(path_frame, text="Additioanly Include Paths:").grid(row=2, column=0, sticky="w", pady=5)
        self.extra_inc_paths = tk.StringVar()
        ttk.Entry(path_frame, textvariable=self.extra_inc_paths, font=self.main_font).grid(row=2, column=1, sticky="ew", padx=10)
        ttk.Label(path_frame, text="e.g: /usr/include/c++/12 /usr/local/cuda/include", font=("Helvetica", 8, "italic"), foreground="gray").grid(row=3, column=1, sticky="w", padx=10)

        path_frame.columnconfigure(1, weight=1)

        # Format Ayarları [cite: 1, 2, 19]
        config_frame = ttk.LabelFrame(main_container, text="Format Standarts", padding=15)
        config_frame.pack(fill="x", pady=10)

        self.var_case = tk.StringVar(value="UPPER_CASE")
        self.func_case = tk.StringVar(value="camelBack")
        self.cls_case = tk.StringVar(value="CamelCase")

        confs = [("Variabeles:", self.var_case), ("Funcitons:", self.func_case), ("Classes:", self.cls_case)]
        for i, (txt, var) in enumerate(confs):
            ttk.Label(config_frame, text=txt).grid(row=0, column=i*2, padx=10)
            cb = ttk.Combobox(config_frame, textvariable=var, values=CASE_OPTIONS, state="readonly", width=20)
            cb.grid(row=0, column=i*2+1)

        # Önizleme Alanı
        preview_frame = ttk.LabelFrame(main_container, text="Review (NLP + Clang AST)", padding=10)
        preview_frame.pack(fill="both", expand=True, pady=10)

        # "File" sütununu ekledik
        self.tree = ttk.Treeview(preview_frame, columns=("File", "Type", "Old", "New"), show='headings')
        
        # Sütun Başlıkları ve Sıralama Eventleri
        for col in ("File", "Type", "Old", "New"):
            self.tree.heading(col, text=col, command=lambda _col=col: self.treeview_sort_column(self.tree, _col, False))
        
        self.tree.column("File", width=200, anchor="w")
        self.tree.column("Type", width=100, anchor="center")
        self.tree.column("Old", width=300, anchor="w")
        self.tree.column("New", width=300, anchor="w")
        
        self.tree.pack(side="left", fill="both", expand=True)
        
        scb = ttk.Scrollbar(preview_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scb.set)
        scb.pack(side="right", fill="y")

        # Buton Paneli
        btn_frame = ttk.Frame(main_container, padding=5)
        btn_frame.pack(fill="x", pady=10)

        ttk.Button(btn_frame, text="Start", command=self.scan_files).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Apply", command=self.apply_changes).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Roll back", command=self.restore_backup).pack(side="right", padx=5)

    def _browse_dir(self, var):
        d = filedialog.askdirectory()
        if d: var.set(d)

    def get_full_include_args(self):
        paths = DEFAULT_INCLUDE_PATHS.copy()
        paths.append(self.inc_path.get())
        extra = self.extra_inc_paths.get().strip()
        if extra:
            paths.extend(extra.split())
        return [f'-I{p}' for p in paths]

    def scan_files(self):
        try:
            self.tree.delete(*self.tree.get_children())
            self.found_symbols = {}
            src = self.src_path.get()
            inc = self.inc_path.get()
            
            self.all_project_files = []
            for d in [src, inc]:
                if os.path.exists(d):
                    for f in os.listdir(d):
                        if f.endswith((".cpp", ".h", ".hpp", ".c")):
                            self.all_project_files.append(os.path.join(d, f))

            index = cindex.Index.create()
            args = self.get_full_include_args()

            for path in self.all_project_files:
                tu = index.parse(path, args=args)
                for node in tu.cursor.walk_preorder():
                    if node.location.file and not str(node.location.file).startswith("/usr"):
                        for key, opt in OPTIONS_MAP.items():
                            if node.kind == opt[1]:
                                old = node.spelling
                                if old and old not in self.found_symbols:
                                    words = ronin.split(old)
                                    self.found_symbols[(old, key)] = (words, path)
                                    target_fmt = getattr(self, f"{key}_case").get()
                                    new_name = to_format(words, target_fmt)
                                    self.tree.insert("", "end", values=(os.path.basename(path), key.upper(), old, new_name))
            
            if not self.found_symbols:
                messagebox.showinfo("Bilgi", "Standarda uymayan isimlendirme bulunamadı.")
        except Exception as e:
            messagebox.showerror("Tarama Hatası", f"Clang AST ayrıştırılamadı: {str(e)}")

    def treeview_sort_column(self, tv, col, reverse):
        # Treeview'daki tüm elemanları al (değer, index) şeklinde
        l = [(tv.set(k, col), k) for k in tv.get_children('')]
        
        # Sırala (Küçük-büyük duyarlılığı için lower() kullanabilirsin)
        l.sort(key=lambda x: x[0].lower(), reverse=reverse)

        # Elemanları yeni sırayla yerleştir
        for index, (val, k) in enumerate(l):
            tv.move(k, '', index)

        # Bir sonraki tıklamada tersine sıralaması için komutu güncelle
        tv.heading(col, command=lambda: self.treeview_sort_column(tv, col, not reverse))

    def apply_changes(self):
        if not self.found_symbols: return
        
        if not messagebox.askyesno("Onay", "Tüm proje dosyaları güncellenecek. Devam edilsin mi?"):
            return

        src = self.src_path.get()
        bk_path = os.path.join(src, self.backup_dir)
        os.makedirs(bk_path, exist_ok=True)
        
        for f in self.all_project_files:
            shutil.copy2(f, os.path.join(bk_path, os.path.basename(f)))

        for path in self.all_project_files:
            with open(path, 'r') as file: content = file.read()

            for (old, key), (words, origin_path) in self.found_symbols.items():
                target_fmt = getattr(self, f"{key}_case").get()
                new_name = to_format(words, target_fmt)
                # 1. (?<!::) -> Önünde '::' olanları es geç (Namespace/Type koruması)
                # 2. (?!\s+\w) -> Peşinden başka bir kelime gelenleri es geç (Type Declaration koruması)
                pattern = r'(?<!::)\b' + re.escape(old) + r'\b(?!\s+\w)'
                content = re.sub(pattern, new_name, content)
            with open(path, 'w') as file: file.write(content)

        self.run_tidy()
        messagebox.showinfo("Başarılı", "Proje NLP ile refaktör edildi ve formatlandı.")

    def run_tidy(self):
        config = {
            "Checks": "readability-identifier-naming",
            "CheckOptions": [
                {'key': OPTIONS_MAP['var'][0], 'value': self.var_case.get()},
                {'key': OPTIONS_MAP['func'][0], 'value': self.func_case.get()},
                {'key': OPTIONS_MAP['cls'][0], 'value': self.cls_case.get()}
            ]
        }
        inc_flags = " ".join(self.get_full_include_args())
        src_files = os.path.join(self.src_path.get(), '*.cpp')
        cmd = f"clang-tidy -config='{json.dumps(config)}' {src_files} -fix-errors -- {inc_flags}"
        os.system(cmd)
        print(cmd)

    def restore_backup(self):
        src = self.src_path.get()
        inc = self.inc_path.get()
        bk_path = os.path.join(src, self.backup_dir)
        if not os.path.exists(bk_path):
            messagebox.showwarning("Hata", "Geri yüklenecek yedek bulunamadı.")
            return
        
        for f in os.listdir(bk_path):
            s_targ = os.path.join(src, f)
            i_targ = os.path.join(inc, f)
            if os.path.exists(s_targ): shutil.copy2(os.path.join(bk_path, f), s_targ)
            elif os.path.exists(i_targ): shutil.copy2(os.path.join(bk_path, f), i_targ)
        messagebox.showinfo("Başarılı", "Yedekler başarıyla geri yüklendi.")

if __name__ == "__main__":
    root = tk.Tk()

    default_font = tkfont.nametofont("TkDefaultFont")
    default_font.configure(family="Helvetica", size=10)
    
    app = NLPLinterGUI(root)
    root.mainloop()