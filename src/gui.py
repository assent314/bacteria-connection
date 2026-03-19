import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import sys
import os
import re
import pandas as pd
import json
# 确保运行此文件时能找到项目根（使双击 .pyw 也能正常导入模块）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 假设 gui.pyw 和 src 文件夹在同一级目录
from src import fetcher as ft
from src import analyzer as at
from src import visualizer as vt
from src import discoverer as dt
from config.settings import Config

BASE_OUTPUT_DIR = Config.OUTPUT_DIR


class RedirectText:
    def __init__(self, text_widget):
        self.text_widget = text_widget
    def write(self, string):
        self.text_widget.insert(tk.END, string)
        self.text_widget.see(tk.END)
    def flush(self):
        pass

class BioAnalysisGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Biomedical Literature Miner & Visualizer")
        self.root.geometry("800x600")
        
        input_frame = ttk.LabelFrame(root, text="Configuration")
        input_frame.pack(padx=10, pady=10, fill="x")

        ttk.Label(input_frame, text="目标疾病:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.ent_disease = ttk.Entry(input_frame, width=30)
        self.ent_disease.insert(0, "Colorectal cancer")
        self.ent_disease.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(input_frame, text="NCBI Email:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.ent_email = ttk.Entry(input_frame, width=30)
        self.ent_email.insert(0, "601576219@qq.com") 
        self.ent_email.grid(row=2, column=1, padx=5, pady=5, sticky="w")
       
        ttk.Label(input_frame, text="筛选菌株数量:").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.ent_top_k = ttk.Spinbox(input_frame, from_=1, to=50, width=5)
        self.ent_top_k.set(10)
        self.ent_top_k.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(input_frame, text="Retmax (每菌抓取量):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.ent_retmax = ttk.Entry(input_frame, width=10)
        self.ent_retmax.insert(0, "50")
        self.ent_retmax.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        self.btn_run = ttk.Button(input_frame, text="Run Analysis", command=self.start_thread)
        self.btn_run.grid(row=1, column=3, padx=5, pady=10)

        output_frame = ttk.LabelFrame(root, text="Running Logs")
        output_frame.pack(padx=10, pady=5, fill="both", expand=True)

        self.log_area = scrolledtext.ScrolledText(output_frame, height=20, state='normal', background="#f0f0f0")
        self.log_area.pack(padx=5, pady=5, fill="both", expand=True)

        sys.stdout = RedirectText(self.log_area)

        self.status_var = tk.StringVar(value="Ready")
        self.status_bar = ttk.Label(root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def start_thread(self):
        disease = self.ent_disease.get()
        email = self.ent_email.get().strip() # 获取邮箱
        try:
            top_k = int(self.ent_top_k.get())
            retmax = int(self.ent_retmax.get())
        except ValueError:
            messagebox.showerror("Error", "Top K and Retmax must be integers!")
            return

        if not email:
            messagebox.showerror("Error", "Please enter a valid NCBI Email!")
            return

        self.btn_run.config(state="disabled")
        self.status_var.set("Running...")
        
        # 将 email 作为参数传给后台线程
        threading.Thread(target=self.main_pipeline, args=(disease, top_k, retmax, email), daemon=True).start()

    def main_pipeline(self, disease, top_k, retmax, email):
        base_dir = BASE_OUTPUT_DIR
        if not os.path.exists(base_dir): os.makedirs(base_dir)

        ft.Entrez.email = email
        dt.Entrez.email = email

        try:
            if not os.path.exists("data"): os.makedirs("data")
            db_path = os.path.join("data", "ncbi_taxonomy.sqlite")
            dt.DB_PATH = db_path # 更新数据库路径

            if not os.path.exists(db_path):
                print(">>> Initializing Taxonomy Database (First time only)...")
                # 确保当前目录有 names.dmp
                if os.path.exists("names.dmp"):
                    dt.init_taxonomy_db("names.dmp")
                else:
                    print("⚠️ 未找到 names.dmp，跳过数据库严格校验。")

            print(f">>> Finding top {top_k} bacteria for {disease}...")
            candidates = dt.discover_top_bacteria(disease, top_k=top_k)
            
            if not candidates:
                print("❌ No bacteria found.")
                return

            extractor = at.BiomedicalPolarityExtractor()
            all_dfs = []

            for i, bact in enumerate(candidates):
                print(f"\nProcessing [{i+1}/{top_k}]: {bact}")
                
                folder_name = bact.replace(" ", "_").replace(".", "")
                bact_dir = os.path.join(base_dir, folder_name)
                os.makedirs(bact_dir, exist_ok=True)
                
                vt.CSV_PATH = os.path.join(bact_dir, f"{folder_name}_polarity.csv")
                vt.JSON_PATH = os.path.join(bact_dir, f"{folder_name}_metadata.json")

                query = f'("{bact}"[Title/Abstract]) AND ("{disease}"[Title/Abstract])'
                articles = ft.fetch_pubmed_data(query, retmax=retmax, existing_pmids=set())
                
                if not articles: continue

                extractor.FN_PATTERN = re.compile(re.escape(bact), re.IGNORECASE)
                extractor.CRC_PATTERN = re.compile(re.escape(disease), re.IGNORECASE)
                
                results, meta = [], []
                for art in articles:
                    meta.append({'pmid': art['pmid'], 'year': art['year']})
                    findings = extractor.extract_polarity(art['abstract'])
                    for f in findings:
                        f['PMID'], f['Bacteria'] = art['pmid'], bact
                        results.append(f)

                if results:
                    with open(vt.JSON_PATH, 'w', encoding='utf-8') as f:
                        json.dump(meta, f, ensure_ascii=False)
                    
                    df = pd.DataFrame(results)
                    df.to_csv(vt.CSV_PATH, index=False, encoding='utf-8-sig')
                    all_dfs.append(df)
                    
                    vt.plot_donut_chart(df)
                    vt.plot_positive_wordcloud(df)
                    vt.plot_sankey_diagram(df)
                    vt.plot_research_trend(df)

            if all_dfs:
                print("\n>>> Generating Global Comparison Summary...")
                summary_dir = os.path.join(base_dir, "Global_Summary_Analysis")
                os.makedirs(summary_dir, exist_ok=True)
                
                final_df = pd.concat(all_dfs, ignore_index=True)
                vt.CSV_PATH = os.path.join(summary_dir, "combined.csv")
                
                vt.plot_comparison_bar(final_df)
                vt.generate_global_wordcloud(final_df)
                vt.plot_mechanism_heatmap(final_df)
                
                print(f"\n✨ ALL DONE! Check: {base_dir}")
                messagebox.showinfo("Success", f"Analysis completed for {len(all_dfs)} bacteria!")
            
        except Exception as e:
            print(f"\n❌ CRITICAL ERROR: {str(e)}")
            messagebox.showerror("Runtime Error", str(e))
        finally:
            self.btn_run.config(state="normal")
            self.status_var.set("Ready")

if __name__ == "__main__":
    root = tk.Tk()
    app = BioAnalysisGUI(root)
    root.mainloop()