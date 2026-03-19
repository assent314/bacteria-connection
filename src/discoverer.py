import os
import sqlite3
import re
from collections import Counter
from Bio import Entrez
import time
from config.settings import Config
# 配置
Entrez.email = Config.ENTREZ_EMAIL
DB_PATH = Config.DB_PATH
disease="Colorectal cancer"
# ================= 数据库构建部分 (方案一核心) =================

def init_taxonomy_db(dmp_path="names.dmp"):
    """将NCBI names.dmp 导入 SQLite，只需运行一次"""
    if os.path.exists(DB_PATH):
        print("--- Taxonomy 数据库已存在，跳过初始化 ---")
        return

    print("--- 正在构建本地 Taxonomy 数据库，请稍候... ---")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # name_txt: 原始名称, unique_variant: 唯一变体, name_class: 名称类型(scientific name, synonym等)
    cursor.execute('''CREATE TABLE IF NOT EXISTS names 
                     (tax_id INTEGER, name_txt TEXT, name_class TEXT)''')
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_name ON names(name_txt)")
    
    with open(dmp_path, "r", encoding="utf-8") as f:
        rows = []
        for line in f:
            # names.dmp 格式: tax_id | name_txt | unique_name | name_class |
            parts = line.split("|")
            tax_id = int(parts[0].strip())
            name_txt = parts[1].strip()
            name_class = parts[3].strip()
            rows.append((tax_id, name_txt, name_class))
            
            if len(rows) >= 100000: # 分批插入提高效率
                cursor.executemany("INSERT INTO names VALUES (?, ?, ?)", rows)
                rows = []
        cursor.executemany("INSERT INTO names VALUES (?, ?, ?)", rows)
    
    conn.commit()
    conn.close()
    print("--- 数据库构建完成！ ---")

def standardize_name(candidate_name):
    """核心校准逻辑：查询SQLite并返回标准科学名"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. 直接查询是否是科学名
    cursor.execute("SELECT tax_id FROM names WHERE name_txt=? AND name_class='scientific name' LIMIT 1", (candidate_name,))
    res = cursor.fetchone()
    if res:
        conn.close()
        return candidate_name

    # 2. 如果没找到，查询是否是别名/异名 (synonym)
    cursor.execute("SELECT tax_id FROM names WHERE name_txt=? LIMIT 1", (candidate_name,))
    res = cursor.fetchone()
    if res:
        tax_id = res[0]
        # 根据 tax_id 找回它的正式科学名
        cursor.execute("SELECT name_txt FROM names WHERE tax_id=? AND name_class='scientific name' LIMIT 1", (tax_id,))
        sci_res = cursor.fetchone()
        conn.close()
        return sci_res[0] if sci_res else candidate_name
    
    conn.close()
    return None # 数据库中未匹配到，说明可能不是真实的生物名称

# ================= 发现逻辑部分 =================

def discover_top_bacteria(disease, top_k=10):
    # 确保数据库已就绪
    if not os.path.exists(DB_PATH):
        print("错误: 请先放置 names.dmp 并运行初始化函数")
        return []

    print(f"🔎 正在从 PubMed 综述中挖掘与 {disease} 相关的菌株...")
    query = f'("{disease}"[Title/Abstract]) AND (bacteria[Title/Abstract]) AND Review[ptyp]'
    
    # 获取PMIDs (简化版逻辑)
    handle = Entrez.esearch(db="pubmed", term=query, retmax=150)
    record = Entrez.read(handle)
    id_list = record.get("IdList", [])
    
    if not id_list: return []

    # 抓取摘要
    fetch_handle = Entrez.efetch(db="pubmed", id=",".join(id_list), retmode="xml")
    records = Entrez.read(fetch_handle)
    
    # 提取双名法词汇: [A-Z]. xxx 或 Genus species
    # 增加了对 E. coli 这种缩写的支持
    pattern = re.compile(r'\b([A-Z][a-z]*\.?\s+[a-z]{3,})\b')
    
    raw_candidates = []
    for art in records.get('PubmedArticle', []):
        abstract = "".join(str(x) for x in art['MedlineCitation']['Article'].get('Abstract', {}).get('AbstractText', []))
        matches = pattern.findall(abstract)
        raw_candidates.extend(matches)

    # 映射与清洗
    bacteria_counter = Counter()
    processed_cache = {} # 缓存查询结果提高速度

    print("🧪 正在通过 NCBI Taxonomy 数据库校验实体...")
    for name in raw_candidates:
        if name in processed_cache:
            std = processed_cache[name]
        else:
            # 预处理：如果是 "E. coli"，尝试先根据上下文还原或标记
            # 这里简单处理：数据库其实存有大量常见缩写，直接查或模糊查
            std = standardize_name(name)
            processed_cache[name] = std
        
        if std:
            bacteria_counter[std] += 1

    top_list = [name for name, count in bacteria_counter.most_common(top_k)]
    
    print("-" * 30)
    for i, (name, count) in enumerate(bacteria_counter.most_common(top_k)):
        print(f"{i+1}. {name} (提及频次: {count})")
    print("-" * 30)
    
    return top_list

if __name__ == "__main__":
    init_taxonomy_db("names.dmp") 
    discover_top_bacteria(disease)