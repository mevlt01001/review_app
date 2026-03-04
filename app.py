import os
import sys
import json
import shutil
import re
import argparse
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font as tkfont
from clang import cindex
import yaml
from fpdf import FPDF
import datetime
import math

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

class NLPLinterGUI:
    def __init__(self, root, path=os.getcwd()):
        self.root = root
        self.root.title("AKSS Refactor Tool")
        self.root.geometry("1200x850")
        
        self.found_symbols = {}
        self.all_project_files = []
        self.backup_dir = ".linter_backups"
        
        self._apply_style()
        self._setup_ui(path)

    def _apply_style(self):
        self.main_font = ("Helvetica", 10)
        self.bold_font = ("Helvetica", 10, "bold")
        
        style = ttk.Style()
        style.theme_use('clam')
        
        style.configure(".", font=self.main_font, background="#f5f5f5")
        style.configure("TLabel", foreground="#333333")
        style.configure("TLabelframe", background="#f5f5f5", relief="groove")
        style.configure("TLabelframe.Label", font=self.bold_font, foreground="#0056b3")
        
        style.configure("TButton", padding=5, font=self.bold_font)
        style.map("TButton",
                  background=[('active', '#e1e1e1'), ('pressed', '#cccccc')],
                  foreground=[('active', '#000000')])
        
        style.configure("Treeview", font=self.main_font, rowheight=25, fieldbackground="white")
        style.configure("Treeview.Heading", font=self.bold_font)

    def _setup_ui(self, path):
        main_container = ttk.Frame(self.root, padding=15)
        main_container.pack(fill="both", expand=True)

        path_frame = ttk.LabelFrame(main_container, text="Project Configuration", padding=15)
        path_frame.pack(fill="x", pady=10)

        ttk.Label(path_frame, text="Source:").grid(row=0, column=0, sticky="w", pady=5)
        self.src_path = tk.StringVar(value=os.path.abspath(path))
        ttk.Entry(path_frame, textvariable=self.src_path, font=self.main_font).grid(row=0, column=1, sticky="ew", padx=10)
        ttk.Button(path_frame, text="Browse", command=lambda: self._browse_dir(self.src_path)).grid(row=0, column=2)

        ttk.Label(path_frame, text="Include:").grid(row=1, column=0, sticky="w", pady=5)
        self.inc_path = tk.StringVar(value=os.path.abspath(path))
        ttk.Entry(path_frame, textvariable=self.inc_path, font=self.main_font).grid(row=1, column=1, sticky="ew", padx=10)
        ttk.Button(path_frame, text="Browse", command=lambda: self._browse_dir(self.inc_path)).grid(row=1, column=2)

        ttk.Label(path_frame, text="Additional Includes:").grid(row=2, column=0, sticky="w", pady=5)
        self.extra_inc_paths = tk.StringVar()
        ttk.Entry(path_frame, textvariable=self.extra_inc_paths, font=self.main_font).grid(row=2, column=1, sticky="ew", padx=10)

        path_frame.columnconfigure(1, weight=1)

        config_frame = ttk.LabelFrame(main_container, text="Format Standards", padding=15)
        config_frame.pack(fill="x", pady=10)

        self.var_case = tk.StringVar(value="UPPER_CASE")
        self.func_case = tk.StringVar(value="camelBack")
        self.cls_case = tk.StringVar(value="CamelCase")

        confs = [("Variables:", self.var_case), ("Functions:", self.func_case), ("Classes:", self.cls_case)]
        for i, (txt, var) in enumerate(confs):
            ttk.Label(config_frame, text=txt).grid(row=0, column=i*2, padx=10)
            cb = ttk.Combobox(config_frame, textvariable=var, values=CASE_OPTIONS, state="readonly", width=20)
            cb.grid(row=0, column=i*2+1)

        preview_frame = ttk.LabelFrame(main_container, text="Diagnostics", padding=10)
        preview_frame.pack(fill="both", expand=True, pady=10)

        tree_frame = ttk.Frame(preview_frame)
        tree_frame.pack(side="left", fill="both", expand=True)

        details_frame = ttk.Frame(preview_frame)
        details_frame.pack(side="right", fill="both", expand=True, padx=(10, 0))

        # EXPRESSION KALDIRILDI
        columns = ("File", "Warn Level", "Category", "Description")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings', displaycolumns=("File", "Warn Level", "Category"))
        
        self.tree.heading("File", text="File", command=lambda: self.treeview_sort_column(self.tree, "File", False))
        self.tree.heading("Warn Level", text="Warn Level", command=lambda: self.treeview_sort_column(self.tree, "Warn Level", False))
        self.tree.heading("Category", text="Category", command=lambda: self.treeview_sort_column(self.tree, "Category", False))
        
        self.tree.column("File", width=150, anchor="w")
        self.tree.column("Warn Level", width=65, anchor="center")
        self.tree.column("Category", width=200, anchor="w")
        
        self.tree.pack(side="left", fill="both", expand=True)
        
        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=tree_scroll.set)
        tree_scroll.pack(side="right", fill="y")

        # TERMİNAL TASARIMI: Koyu arka plan ve açık gri yazı
        self.details_text = tk.Text(details_frame, wrap="none", font=("Courier", 12), bg="#1e1e1e", fg="#d4d4d4")
        self.details_text.pack(side="left", fill="both", expand=True)
        
        # TERMİNAL RENKLERİ (Tag Konfigürasyonları)
        self.details_text.tag_configure("bold_path", font=("Courier", 12, "bold"), foreground="#ffffff")
        self.details_text.tag_configure("warning_tag", foreground="#ff55ff", font=("Courier", 12, "bold")) # Pembe
        self.details_text.tag_configure("error_tag", foreground="#ff5555", font=("Courier", 12, "bold"))   # Kırmızı
        self.details_text.tag_configure("pointer_tag", foreground="#55ff55", font=("Courier", 12, "bold")) # Yeşil Oklar
        self.details_text.tag_configure("suggestion_tag", foreground="#55ff55", font=("Courier", 12))      # Yeşil Öneri

        self.details_text.insert("1.0", "Click on a row to see details...")
        self.details_text.config(state="disabled")

        text_scroll_y = ttk.Scrollbar(details_frame, orient="vertical", command=self.details_text.yview)
        self.details_text.configure(yscrollcommand=text_scroll_y.set)
        text_scroll_y.pack(side="right", fill="y")
        
        text_scroll_x = ttk.Scrollbar(details_frame, orient="horizontal", command=self.details_text.xview)
        self.details_text.configure(xscrollcommand=text_scroll_x.set)
        text_scroll_x.pack(side="bottom", fill="x")

        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        btn_frame = ttk.Frame(main_container, padding=5)
        btn_frame.pack(fill="x", pady=10)

        ttk.Button(btn_frame, text="Start Scan", command=self.scan_files).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Apply Changes", command=self.apply_changes).pack(side="left", padx=5)
        
        ttk.Button(btn_frame, text="Export PDF", command=self.export_pdf).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Roll Back", command=self.restore_backup).pack(side="right", padx=5)

    def _browse_dir(self, var):
        d = filedialog.askdirectory(initialdir=var.get())
        if d: var.set(d)

    def get_full_include_args(self):
        paths = DEFAULT_INCLUDE_PATHS.copy()
        paths.append(self.inc_path.get())
        extra = self.extra_inc_paths.get().strip()
        if extra:
            paths.extend(extra.split())
        return [f'-I{p}' for p in paths]

    def get_file_info_at_offset(self, filepath, offset):
        """ Offsete göre Satır No, Görsel Sütun No (Tabları hesaba katar) ve Tüm Satırı döndürür """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            up_to_offset = content[:offset]
            row = up_to_offset.count('\n') + 1
            last_newline = up_to_offset.rfind('\n')
            
            # Offsetten önceki asıl metin (aynı satırdaki)
            line_prefix = up_to_offset[last_newline + 1:]
            
            # HİZALAMA İÇİN KRİTİK NOKTA: Tab karakterini 4 boşluk saymalıyız
            visual_col = len(line_prefix.expandtabs(4)) + 1
            
            omin = last_newline + 1 if last_newline != -1 else 0
            omax = content.find('\n', offset)
            if omax == -1:
                omax = len(content)
                
            # Gösterilecek tam satır (Yine tabları boşluğa çeviriyoruz ki terminalde hizalansın)
            full_line = content[omin:omax].expandtabs(4)

            return row, visual_col, full_line
        except Exception:
            return 0, 0, "N/A"

    def scan_files(self):
        try:
            self.tree.delete(*self.tree.get_children())
            self.details_text.config(state="normal")
            self.details_text.delete("1.0", tk.END)
            self.details_text.config(state="disabled")
            
            self.run_tidy()
            
            if not os.path.exists("fixes.yaml"):
                messagebox.showwarning("Error", "fixes.yaml not found.")
                return

            with open("fixes.yaml", "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                
            if not data or "Diagnostics" not in data:
                messagebox.showinfo("Info", "No issues found.")
                return

            for Diagnostic in data.get("Diagnostics", []):
                DiagnosticName = Diagnostic.get("DiagnosticName", "Unknown")
                DiagnosticMessage = Diagnostic.get("DiagnosticMessage", {})
                Message = DiagnosticMessage.get("Message", "No description")
                Level = Diagnostic.get("Level", "Unknown").lower()
                
                FilePath = DiagnosticMessage.get("FilePath", "")
                FileOffset = DiagnosticMessage.get("FileOffset", 0)

                Replacements = DiagnosticMessage.get("Replacements", [])
                
                if not Replacements:
                    Notes = Diagnostic.get("Notes", [])
                    for note in Notes:
                        note_replacements = note.get("Replacements", [])
                        if note_replacements:
                            Replacements.extend(note_replacements)

                row, col, full_line = self.get_file_info_at_offset(FilePath, FileOffset)
                
                # Başlık Satırı (Terminal benzeri)
                header = f"{FilePath}:{row}:{col}: {Level}: {Message}"
                desc_lines = [header, full_line]

                if Replacements:
                    for Replacement in Replacements:
                        RepFilePath = Replacement.get("FilePath", FilePath)
                        RepOffset = Replacement.get("Offset", 0)
                        RepLength = Replacement.get("Length", 0)
                        RepText = Replacement.get("ReplacementText", "")
                        
                        r_row, r_col, r_full_line = self.get_file_info_at_offset(RepFilePath, RepOffset)
                        
                        # Eğer değişiklik başka satırdaysa onu da ekrana bas
                        if r_row != row:
                            desc_lines.append(f"{RepFilePath}:{r_row}:{r_col}: note: fix applied here")
                            desc_lines.append(r_full_line)
                        
                        # Terminal oklarını (^~~) oluştur
                        spaces = " " * (r_col - 1)
                        tildes = "~" * (RepLength - 1) if RepLength > 1 else ("~" if RepLength == 1 else "")
                        pointer_line = f"{spaces}^{tildes}"
                        
                        desc_lines.append(pointer_line)
                        if RepText:
                            # Çok satırlı önerileri düzgün hizala
                            formatted_rep = RepText.replace('\n', '\n' + spaces)
                            desc_lines.append(f"{spaces}{formatted_rep}")
                else:
                    # Replacement yoksa sadece hatanın yerini göster
                    spaces = " " * (col - 1)
                    desc_lines.append(f"{spaces}^")

                file_name = FilePath if FilePath else "Unknown"
                file_label = f"{os.path.basename(file_name)}"
                Description = "\n".join(desc_lines)

                # TREEVIEW'DA ARTIK EXPRESSION YOK (Sadece 4 argüman var)
                self.tree.insert("", "end", values=(file_label, Level.capitalize(), DiagnosticName, Description))
                
            messagebox.showinfo("Done", "Scan completed.")
            
        except Exception as e:
            messagebox.showerror("Scan Error", f"An error occurred:\n{str(e)}")

    def treeview_sort_column(self, tv, col, reverse):
        l = [(tv.set(k, col), k) for k in tv.get_children('')]
        l.sort(key=lambda x: x[0].lower(), reverse=reverse)
        for index, (val, k) in enumerate(l):
            tv.move(k, '', index)
        tv.heading(col, command=lambda: self.treeview_sort_column(tv, col, not reverse))

    def on_tree_select(self, event):
        selected_items = self.tree.selection()
        if not selected_items:
            return
            
        item = self.tree.item(selected_items[0])
        values = item['values']
        
        # Expression kalktığı için description artık 3. indexte (0,1,2,3)
        if len(values) >= 4:
            description = values[3]
            
            self.details_text.config(state="normal")
            self.details_text.delete("1.0", tk.END)
            
            lines = description.split('\n')
            is_suggestion = False
            
            for line in lines:
                # Başlık satırı kontrolü
                header_match = re.match(r"^([^:]+:\d+:\d+:)\s+(warning|error|note):\s+(.*)$", line)
                
                if header_match:
                    self.details_text.insert(tk.END, header_match.group(1) + " ", "bold_path")
                    level = header_match.group(2)
                    tag = "warning_tag" if level == "warning" else ("error_tag" if level == "error" else "bold_path")
                    self.details_text.insert(tk.END, level + ": ", tag)
                    self.details_text.insert(tk.END, header_match.group(3) + "\n", "bold_path")
                    is_suggestion = False
                
                # İşaretçi satırı (^ ve ~ karakterleri)
                elif re.match(r"^\s*[\^~]+\s*$", line):
                    self.details_text.insert(tk.END, line + "\n", "pointer_tag")
                    is_suggestion = True
                    
                # Öneri satırı (İşaretçinin hemen altı)
                elif is_suggestion:
                    self.details_text.insert(tk.END, line + "\n", "suggestion_tag")
                    is_suggestion = False 
                    
                else:
                    self.details_text.insert(tk.END, line + "\n")

            self.details_text.config(state="disabled")

    def apply_changes(self):
        messagebox.showinfo("Info", "Apply is disabled in this version. Use clang-tidy -fix to apply changes automatically.")

    def run_tidy(self):
        config = {
            "Checks": "*",
            "CheckOptions": [
                {'key': OPTIONS_MAP['var'][0], 'value': self.var_case.get()},
                {'key': OPTIONS_MAP['func'][0], 'value': self.func_case.get()},
                {'key': OPTIONS_MAP['cls'][0], 'value': self.cls_case.get()}
            ]
        }
        inc_flags = " ".join(self.get_full_include_args())
        src_files = os.path.join(self.src_path.get(), '*.cpp')

        cmd = (
            f"clang-tidy -config='{json.dumps(config)}' {src_files} "
            f"-header-filter='{self.inc_path.get()}.*\\.(h|hpp)' "
            f"--export-fixes=fixes.yaml "
            f"-- {inc_flags}"
        )
        print("Running command:", cmd)
        os.system(cmd)
    
    def restore_backup(self):
        messagebox.showinfo("Info", "Restore backup is disabled in this version.")
    
    def _calculate_pdf_lines(self, pdf, text, col_width):
        """FPDF için hassas satır kaydırma hesabı"""
        lines = 0
        for paragraph in str(text).split('\n'):
            if not paragraph.strip() and paragraph == "": # Tamamen boş satırlar için
                lines += 1
                continue
            words = paragraph.split(' ')
            current_line = ""
            for word in words:
                test_line = current_line + word + " " if current_line else word + " "
                if pdf.get_string_width(test_line) > (col_width - 4): 
                    lines += 1
                    current_line = word + " "
                else:
                    current_line = test_line
            if current_line:
                lines += 1
        return max(1, lines)

    def export_pdf(self):
        if not self.tree.get_children():
            messagebox.showwarning("Warning", "No data to export. Run scan first.")
            return
            
        pdf = FPDF(orientation='L', unit='mm', format='A4') 
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, "AKSS Refactor Tool - Static Code Analysis Report", ln=True, align='C')
        pdf.ln(5)
        
        pdf.set_font("Arial", '', 10)
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        pdf.cell(0, 6, f"Generated On: {current_time}", ln=True)
        pdf.cell(0, 6, f"Source Directory: {self.src_path.get()}", ln=True)
        pdf.cell(0, 6, f"Include Directory: {self.inc_path.get()}", ln=True)
        extra_inc = self.extra_inc_paths.get()
        if extra_inc:
            pdf.cell(0, 6, f"Additional Includes: {extra_inc}", ln=True)
        pdf.cell(0, 6, f"Format Standards -> Variable: {self.var_case.get()} | Function: {self.func_case.get()} | Class: {self.cls_case.get()}", ln=True)
        pdf.ln(8)
        
        # EXPRESSION SÜTUNU KALDIRILDI, GENİŞLİKLER GÜNCELLENDİ (Toplam 277mm)
        pdf.set_font("Arial", 'B', 9)
        cols = [
            ("File", 35), 
            ("Warn Level", 20), 
            ("Category", 55), 
            ("Details (Description & Recs)", 165) 
        ]
        
        for name, width in cols:
            pdf.cell(width, 10, name, border=1, align='C')
        pdf.ln()
        
        def safe_txt(txt):
            replacements = {'ı':'i', 'İ':'I', 'ğ':'g', 'Ğ':'G', 'ü':'u', 'Ü':'U', 'ş':'s', 'Ş':'S', 'ö':'o', 'Ö':'O', 'ç':'c', 'Ç':'C'}
            res = str(txt)
            for k, v in replacements.items(): 
                res = res.replace(k, v)
            return res.encode('latin-1', 'ignore').decode('latin-1')

        line_height = 4.5 # Monospace font biraz daha sıkı olduğu için satır boyunu hafif kısalttık

        for item in self.tree.get_children():
            values = self.tree.item(item, 'values')
            row_data = [safe_txt(v) for v in values]
            
            max_lines = 1
            for idx, text in enumerate(row_data):
                width = cols[idx][1]
                # YÜKSEKLİK HESABI İÇİN FONT SET EDİLMELİ
                if idx == 3: # Artık Description 3. Sütun!
                    pdf.set_font("Courier", '', 7)
                else:
                    pdf.set_font("Arial", '', 8)
                    
                lines = self._calculate_pdf_lines(pdf, text, width)
                if lines > max_lines:
                    max_lines = lines
                    
            row_height = max_lines * line_height

            if pdf.get_y() + row_height > pdf.page_break_trigger:
                pdf.add_page()

            x_start = pdf.get_x()
            y_start = pdf.get_y()

            for idx, text in enumerate(row_data):
                width = cols[idx][1]
                
                pdf.rect(x_start, y_start, width, row_height)
                
                if idx < 3: # İlk 3 sütun
                    pdf.set_font("Arial", '', 8)
                    text_w = pdf.get_string_width(text)
                    if text_w < width - 2 and '\n' not in text:
                        y_offset = (row_height - line_height) / 2
                        pdf.set_xy(x_start, y_start + y_offset)
                        pdf.cell(width, line_height, text, align='C')
                    else:
                        lines = max(1, math.ceil(text_w / (width - 2)))
                        text_height = lines * line_height
                        y_offset = (row_height - text_height) / 2
                        pdf.set_xy(x_start, y_start + y_offset)
                        pdf.multi_cell(width, line_height, text, align='C')
                else:
                    # DESCRIPTION SÜTUNU: Tam Terminal Hizalaması için Courier Font
                    pdf.set_font("Courier", '', 7)
                    pdf.set_xy(x_start + 2, y_start + 1)
                    pdf.multi_cell(width - 4, line_height, text, align='L')

                x_start += width

            pdf.set_y(y_start + row_height)
            
        try:
            save_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")], initialfile="report.pdf")
            if save_path:
                pdf.output(save_path)
                messagebox.showinfo("Success", f"Report successfully generated:\n{save_path}")
        except Exception as e:
            messagebox.showerror("PDF Error", f"Failed to generate PDF:\n{str(e)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AKSS Refactor Tool")
    parser.add_argument("--path", type=str, default="./", help="Working Directory")
    args = parser.parse_args()

    root = tk.Tk()
    app = NLPLinterGUI(root, args.path)
    root.mainloop()