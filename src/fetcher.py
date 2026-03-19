import ssl
ssl._create_default_https_context = ssl._create_unverified_context

from Bio import Entrez
import pandas as pd
import json
import time
import socket
import os
import re  # 修复错误：导入 re 模块
from typing import List, Dict, Any, Set, cast
from urllib.error import URLError
from config.settings import Config


# =================配置区域=================
Entrez.email = Config.ENTREZ_EMAIL
SEARCH_QUERY = Config.SEARCH_QUERY_TEMPLATE
RETMAX = Config.RETMAX
OUTPUT_FILE = Config.OUTPUT_DIR + "\\pubmed_results.json"
# ==========================================

def fetch_with_retry(func, *args, max_retries=3, **kwargs):
    for i in range(max_retries):
        try:
            res = func(*args, **kwargs)
            if res is not None:
                return res
        except (URLError, socket.timeout, Exception) as e:
            if i == max_retries - 1: raise e
            wait_time = (i + 1) * 2
            print(f"⚠️ 连接异常 ({e})，进行第 {i+1} 次重试...")
            time.sleep(wait_time)
    return None

def fetch_pubmed_data(query, retmax, existing_pmids, email=Config.ENTREZ_EMAIL):
    Entrez.email = email
    print(f"🚀 正在检索 PubMed: {query}...")
    
    # 修复：确保 search_handle 不为 None
    search_handle = fetch_with_retry(Entrez.esearch, db="pubmed", term=query, retmax=retmax, sort="relevance")
    if search_handle is None:
        print("❌ 无法获取搜索句柄")
        return []

    # 修复：显式转换类型以消除 Pylance 报警
    record = cast(Dict[str, Any], Entrez.read(search_handle))
    search_handle.close()
    
    all_ids = record.get("IdList", [])
    new_ids = [pid for pid in all_ids if str(pid) not in existing_pmids]
    
    print(f"✅ 检索到 {len(all_ids)} 篇文献，其中 {len(new_ids)} 篇为新文献。")
    
    if not new_ids:
        return []

    results = []
    batch_size = 10 
    for i in range(0, len(new_ids), batch_size):
        ids = ",".join(new_ids[i : i + batch_size])
        try:
            fetch_handle = fetch_with_retry(Entrez.efetch, db="pubmed", id=ids, retmode="xml")
            if fetch_handle is None: continue
            
            # 修复：显式转换类型
            records = cast(Dict[str, Any], Entrez.read(fetch_handle))
            fetch_handle.close()
            
            for article in records.get('PubmedArticle', []):
                try:
                    medline = article['MedlineCitation']
                    article_data = medline['Article']
                    pmid = str(medline['PMID'])
                    title = article_data.get('ArticleTitle', '')
                    
                    # 改进的年份提取逻辑
                    pub_date = article_data.get('Journal', {}).get('JournalIssue', {}).get('PubDate', {})
                    pub_year = pub_date.get('Year')
                    if not pub_year:
                        medline_date = pub_date.get('MedlineDate', '')
                        year_match = re.search(r'\d{4}', str(medline_date))
                        pub_year = year_match.group(0) if year_match else 'N/A'

                    abstract_list = article_data.get('Abstract', {}).get('AbstractText', [])
                    abstract = " ".join([str(part) for part in abstract_list]) if abstract_list else ""

                    if abstract:
                        results.append({
                            "pmid": pmid,
                            "title": title,
                            "year": str(pub_year),
                            "abstract": abstract,
                            "source": "PubMed"
                        })
                except (KeyError, IndexError):
                    continue
            
            print(f"进度: {min(i + batch_size, len(new_ids))}/{len(new_ids)} 已完成")
            time.sleep(0.5)
        except Exception as e:
            print(f"❌ 抓取批次 {i} 失败: {e}")
            continue
            
    return results

def load_existing_data(file_path: str):
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                pmids = {str(item['pmid']) for item in data}
                return data, pmids
        except Exception as e:
            print(f"⚠️ 读取旧文件失败 ({e})，将创建新文件。")
    return [], set()

def merge_and_save(new_data: List[Dict[str, Any]], old_data: List[Dict[str, Any]], file_path: str):
    combined_data = old_data + new_data
    df = pd.DataFrame(combined_data)
    df.drop_duplicates(subset=['pmid'], inplace=True)
    
    final_list = df.to_dict(orient='records')
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(final_list, f, ensure_ascii=False, indent=4)
    
    print(f"💾 数据库已更新！当前总记录数: {len(final_list)}")

if __name__ == "__main__":
    existing_data, existing_pmids = load_existing_data(OUTPUT_FILE)
    print(f"📂 本地已存储 {len(existing_data)} 篇文献。")
    new_raw_data = fetch_pubmed_data(SEARCH_QUERY, RETMAX, existing_pmids)
    if new_raw_data:
        merge_and_save(new_raw_data, existing_data, OUTPUT_FILE)
    else:
        print("☕ 没有发现新文献，无需更新文件。")