import os
import pandas as pd
import re
import json
import shutil

from src import fetcher as ft
from src import analyzer as at
from src import visualizer as vt
from src import discoverer as dt

# ================= 配置区 =================
TARGET_DISEASE = "Colorectal cancer"
TOP_K_BACTERIA = 10
BASE_OUTPUT_DIR = "Bacteria_Analysis_Reports" 
# ==========================================

def run_per_bacterium_pipeline():
    if not os.path.exists(BASE_OUTPUT_DIR):
        os.makedirs(BASE_OUTPUT_DIR)

    print(f"🚀 启动动态发现机制，目标疾病: {TARGET_DISEASE}")
    
    # 0. 动态发现菌株
    candidate_bacteria = dt.discover_top_bacteria(TARGET_DISEASE, top_k=TOP_K_BACTERIA)
    
    if not candidate_bacteria:
        print("❌ 未发现候选菌株，程序终止。")
        return    

    all_bact_data_frames = [] # 用于最后汇总
    extractor = at.BiomedicalPolarityExtractor()

    # 1. 核心循环：处理每个细菌
    for i, bact in enumerate(candidate_bacteria):
        print(f"\n{'='*60}\n进程 [{i+1}/{TOP_K_BACTERIA}]: {bact}\n{'='*60}")

        # A. 文件夹准备
        folder_name = bact.replace(" ", "_").replace(".", "") 
        bact_dir = os.path.join(BASE_OUTPUT_DIR, folder_name)
        os.makedirs(bact_dir, exist_ok=True)

        # B. 重定向路径
        current_csv = os.path.join(bact_dir, f"{folder_name}_polarity.csv")
        current_json = os.path.join(bact_dir, f"{folder_name}_metadata.json")
        vt.CSV_PATH = current_csv
        vt.JSON_PATH = current_json

        # C. 抓取 (fetch)
        query = f'("{bact}"[Title/Abstract]) AND ("{TARGET_DISEASE}"[Title/Abstract])'
        articles = ft.fetch_pubmed_data(query, retmax=100, existing_pmids=set())
        
        if not articles:
            print(f"⚠️ {bact} 未找到文献，跳过。")
            continue

        # D. 分析 (analysis)
        extractor.FN_PATTERN = re.compile(re.escape(bact), re.IGNORECASE)
        extractor.CRC_PATTERN = re.compile(re.escape(TARGET_DISEASE), re.IGNORECASE)
        
        bact_extracted_results = []
        bact_metadata = []

        for art in articles:
            bact_metadata.append({'pmid': art['pmid'], 'year': art['year']})
            findings = extractor.extract_polarity(art['abstract'])
            for f in findings:
                f['PMID'] = art['pmid']
                f['Bacteria'] = bact # 标记细菌名以便汇总分析
                bact_extracted_results.append(f)

        # E. 保存与可视化 (visual)
        if bact_extracted_results:
            with open(current_json, 'w', encoding='utf-8') as f:
                json.dump(bact_metadata, f, ensure_ascii=False, indent=4)
            
            df_bact = pd.DataFrame(bact_extracted_results)
            df_bact.to_csv(current_csv, index=False, encoding='utf-8-sig')
            all_bact_data_frames.append(df_bact) # 加入汇总列表

            print(f" 生成 {bact} 的独立图表...")
            vt.plot_donut_chart(df_bact)
            vt.plot_positive_wordcloud(df_bact)
            vt.plot_sankey_diagram(df_bact)
            vt.plot_research_trend(df_bact)
        else:
            print(f"💡 {bact} 未挖掘到有效结论。")

    # ================= 2. 汇总分析阶段 =================
    if all_bact_data_frames:
        print("\n" + "#" * 50 + "\n🔍 正在启动跨菌株综合比对分析...\n" + "#" * 50)
        
        final_combined_df = pd.concat(all_bact_data_frames, ignore_index=True)
        summary_dir = os.path.join(BASE_OUTPUT_DIR, "Global_Summary_Analysis")
        os.makedirs(summary_dir, exist_ok=True)
        
        # 保存总表
        total_csv = os.path.join(summary_dir, "all_bacteria_combined.csv")
        vt.CSV_PATH = total_csv # 重定向到汇总目录
        final_combined_df.to_csv(total_csv, index=False, encoding='utf-8-sig')
        
        # 调用汇总图表
        vt.plot_comparison_bar(final_combined_df)      
        vt.generate_global_wordcloud(final_combined_df) 
        vt.plot_mechanism_heatmap(final_combined_df)    
        
        print(f"\n✨ 任务全部完成！汇总报告见: {summary_dir}")
    else:
        print("❌ 未能收集到任何有效数据。")

if __name__ == "__main__":
    if not os.path.exists("ncbi_taxonomy.sqlite"):
        dt.init_taxonomy_db("names.dmp") 
    run_per_bacterium_pipeline()