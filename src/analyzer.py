import spacy
import pandas as pd
import re
import json
import os 
from typing import List, Dict, Any, Set
from config.settings import Config 
import spacy
import pandas as pd
import re
import json
import os
from typing import List, Dict, Any, Set

class BiomedicalPolarityExtractor:
    def __init__(self):
        print("Loading SciSpacy model...")
        try:
            self.nlp = spacy.load("en_core_sci_sm")
        except OSError:
            raise ValueError("SciSpacy模型未安装，请先运行: pip install scispacy en_core_sci_sm")
        
        # [原有极性词典保持不变...]
        self.POSITIVE_VERBS = {'promote', 'induce', 'increase', 'contribute', 'drive', 'correlate', 'associate', 'enhance', 'stimulate', 'upregulate', 'accelerate', 'activate', 'facilitate', 'augment', 'boost', 'trigger', 'potentiate', 'exacerbate'}
        self.NEGATIVE_VERBS = {'inhibit', 'reduce', 'decrease', 'suppress', 'antagonize', 'prevent', 'downregulate', 'block', 'attenuate', 'impair', 'diminish', 'restrict', 'hamper', 'curtail', 'restrain'}
        self.POSITIVE_INDICATORS = {'risk factor', 'biomarker', 'enriched', 'abundant', 'elevated', 'higher', 'correlation', 'association', 'positive', 'causal', 'oncogenic', 'pathogenic', 'pro-tumorigenic'}
        self.STAT_WORDS = {'significantly', 'notably', 'markedly', 'p <', 'p<'}
        
        self.FN_PATTERN = re.compile(r'(fusobacterium\s+nucleatum|f\.\s*nucleatum|fn)', re.IGNORECASE)
        self.CRC_PATTERN = re.compile(r'(colorectal\s+cancer|crc|colon\s+cancer|colorectal\s+neoplasms|tumorigenesis|colorectal adenocarcinoma|colorectal carcinoma)', re.IGNORECASE)

        # ================= 新增：次级标签(Sub-Category)正则表达式词典 =================
        self.TARGET_CATEGORIES = {
            "AI-2 & Quorum Sensing":[r'ai-2', r'autoinducer\s*2', r'luxs', r'quorum\s*sensing', r'qs'],
            "Early Screening & Biomarker":[r'biomarker', r'screen', r'early\s*detection', r'diagnos', r'prognosis', r'early-stage'],
            "Immune Microenvironment":[r'immune', r'macrophage', r't\s*cell', r'microenvironment', r'inflammation', r'cytokine', r'cd8'],
            "Tumorigenesis & Metastasis":[r'tumorigenesis', r'metastasis', r'proliferation', r'progression', r'invasion'],
            "Drug Resistance":[r'resistance', r'chemoresistance', r'therapy', r'drug']
        }
        self.category_patterns = {
            k: [re.compile(p, re.IGNORECASE) for p in v] 
            for k, v in self.TARGET_CATEGORIES.items()
        }

    def extract_polarity(self, text: str) -> List[Dict[str, Any]]:
        if not text or not isinstance(text, str):
            return []

        doc = self.nlp(text)
        extracted_data =[]

        for sent in doc.sents:
            sent_text = sent.text.lower()
            
            if self.FN_PATTERN.search(sent_text) and self.CRC_PATTERN.search(sent_text):
                sentence_polarity = "Neutral/Uncertain"
                found_reason =[]

                # --- 策略 A: 检查动词极性 ---
                for token in sent:
                    if token.pos_ == "VERB":
                        lemma = token.lemma_.lower()
                        if lemma in self.POSITIVE_VERBS or lemma in self.NEGATIVE_VERBS:
                            is_negated = any(child.dep_ == "neg" for child in token.children)
                            if lemma in self.POSITIVE_VERBS:
                                sentence_polarity = "Negative" if is_negated else "Positive"
                            else:
                                sentence_polarity = "Positive" if is_negated else "Negative"
                            found_reason.append(f"Verb:{lemma}")
                            break 

                # --- 策略 B: 检查形容词/名词指标 ---
                if sentence_polarity == "Neutral/Uncertain":
                    for indicator in self.POSITIVE_INDICATORS:
                        if indicator in sent_text:
                            if any(sw in sent_text for sw in self.STAT_WORDS):
                                sentence_polarity = "Positive"
                                found_reason.append(f"Indicator:{indicator}(Stat)")
                                break
                            else:
                                if indicator in['risk factor', 'oncogenic', 'causal', 'biomarker']:
                                    sentence_polarity = "Positive"
                                    found_reason.append(f"StrongTerm:{indicator}")
                                    break

                # ================= 新增：次级标签提取逻辑 =================
                matched_categories =[]
                for category, patterns in self.category_patterns.items():
                    if any(p.search(sent_text) for p in patterns):
                        matched_categories.append(category)
                
                # 如果没有匹配到特定的高级词汇，则归类为通用关联
                if not matched_categories:
                    matched_categories =["General CRC Correlation"]

                # 为每个匹配到的次级标签生成一条记录（方便后续画桑基图）
                for category in matched_categories:
                    extracted_data.append({
                        "Sentence": sent.text.strip(),
                        "Reason": ", ".join(found_reason) if found_reason else "Implicit",
                        "Polarity": sentence_polarity,
                        "Sub_Category": category  # 存储提取出的次级标签
                    })
                
        return extracted_data

    def get_processed_pmids(self, output_filepath: str) -> Set[str]:
            """
            改进版：支持多编码尝试，避免崩溃
            """
            if not os.path.exists(output_filepath):
                return set()
            
            # 依次尝试 utf-8-sig (推荐), gbk (Windows常用), utf-8
            for enc in ['utf-8-sig', 'gbk', 'utf-8']:
                try:
                    df_old = pd.read_csv(output_filepath, encoding=enc)
                    if 'PMID' in df_old.columns:
                        return set(df_old['PMID'].astype(str).unique())
                except Exception:
                    continue # 如果报错，尝试下一种编码
            
            print("⚠️ 无法读取旧结果文件（可能是编码问题），将作为新任务开始。")
            return set()

    def analyze_and_save(self, input_filepath: str, output_filename: str):
        """
        修改后的分析主逻辑：实现增量更新
        """
        # 1. 加载 JSON 数据
        pubmed_data = []
        try:
            with open(input_filepath, 'r', encoding='utf-8') as file:
                pubmed_data = json.load(file)
        except Exception as e:
            print(f"❌ 无法加载输入文件: {e}")
            return

        print(f"📂 JSON中共有 {len(pubmed_data)} 条文献记录")

        # 2. 获取已经分析过的 PMID
        processed_pmids = self.get_processed_pmids(output_filename)
        print(f"🔍 检查到 CSV 中已有 {len(processed_pmids)} 篇文献分析结果")

        # 3. 过滤出真正需要分析的新数据
        new_records = [r for r in pubmed_data if str(r.get('pmid')) not in processed_pmids]
        
        if not new_records:
            print("☕ 所有文献均已分析过，无需更新。")
            return

        print(f"🚀 发现 {len(new_records)} 篇新文献，开始文本挖掘...")

        # 4. 执行分析
        new_results = []
        for i, record in enumerate(new_records):
            pmid = str(record.get('pmid'))
            title = record.get('title', '')
            abstract = record.get('abstract', '')
            full_text = f"{title} {abstract}".strip()
            year = record.get('year', 'N/A')

            results = self.extract_polarity(full_text)
            for res in results:
                res['PMID'] = pmid
                res['Title'] = title
                res['Year'] = year
                new_results.append(res)
            
            if (i + 1) % 50 == 0:
                print(f"已处理 {i + 1}/{len(new_records)} 篇新文献...")

        # 5. 合并并保存 (关键修复点)
        new_df = pd.DataFrame(new_results)
        
        if os.path.exists(output_filename) and not new_df.empty:
            # 读取旧数据也需要多编码支持
            old_df = pd.DataFrame()
            for enc in ['utf-8-sig', 'gbk', 'utf-8']:
                try:
                    old_df = pd.read_csv(output_filename, encoding=enc)
                    break
                except:
                    continue
            
            final_df = pd.concat([old_df, new_df], ignore_index=True)
        else:
            final_df = new_df

        if not final_df.empty:
            # 统一使用 utf-8-sig 保存，这是解决 Excel/Python 兼容性的黄金标准
            final_df.to_csv(output_filename, index=False, encoding='utf-8-sig')
            print(f"✅ 更新完成！总分析结果行数: {len(final_df)}")
        else:
            print("💡 本次未从新文献中挖掘到有效结论。")

def main():
    extractor = BiomedicalPolarityExtractor()
    input_path = Config.OUTPUT_DIR + "\\pubmed_results.json"
    output_path = Config.OUTPUT_DIR + "\\example_polarity_results.csv"

    extractor.analyze_and_save(input_path, output_path)

if __name__ == "__main__":
    main()