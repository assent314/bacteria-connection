import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from wordcloud import WordCloud
import os
import json
import re
from pyecharts import options as opts
from pyecharts.charts import Sankey
from config.settings import Config
# ================= 配置区域 =================
# 请确保路径指向你最新的文件
JSON_PATH = Config.OUTPUT_DIR + "\\pubmed_results.json"
CSV_PATH = Config.OUTPUT_DIR + "\\example_polarity_results.csv"
# ==========================================


def plot_sankey_diagram(df):
    """根据文本挖掘结果绘制机制网络流向(Sankey Diagram)"""
    if 'Sub_Category' not in df.columns or 'Reason' not in df.columns:
        print("❌ CSV中缺少用于绘制桑基图的 'Sub_Category' 或 'Reason' 列，请先更新并运行提取脚本。")
        return
    
    # 只看具有正向结论的文献，因为我们要证明设计依据
    df_pos = df[df['Polarity'] == 'Positive'].copy()
    nodes_set = set(["F. nucleatum"])
    links_dict = {}

    for _, row in df_pos.iterrows():
        reason_str = str(row['Reason'])
        sub_cat = str(row['Sub_Category'])
        
        # 提取核心动词或指标
        action = "correlates with" # 默认动词
        verb_match = re.search(r'Verb:([a-z]+)', reason_str)
        indicator_match = re.search(r'(Indicator|StrongTerm):([a-z\s]+)', reason_str)
        
        if verb_match:
            action = verb_match.group(1)
            # 对相似动词进行聚类，防止图表中间节点过杂
            if action in['promote', 'induce', 'drive', 'stimulate', 'trigger', 'accelerate', 'exacerbate']:
                action = "Promotes / Induces"
            elif action in ['increase', 'enhance', 'upregulate', 'augment']:
                action = "Increases / Enhances"
            elif action in ['associate', 'correlate']:
                action = "Correlates with"
        elif indicator_match:
            action = "Acts as Biomarker"

        nodes_set.add(action)
        nodes_set.add(sub_cat)

        # 连线 1: Fn -> Action
        link1 = ("F. nucleatum", action)
        links_dict[link1] = links_dict.get(link1, 0) + 1
        
        # 连线 2: Action -> Sub_Category
        link2 = (action, sub_cat)
        links_dict[link2] = links_dict.get(link2, 0) + 1

    # 构建 pyecharts 所需的数据格式
    nodes =[{"name": node} for node in nodes_set]
    links =[{"source": src, "target": tgt, "value": val} for (src, tgt), val in links_dict.items()]

    # 初始化桑基图
    sankey = (
        Sankey(init_opts=opts.InitOpts(width="1000px", height="600px"))
        .add(
            "Frequency",
            nodes,
            links,
            linestyle_opt=opts.LineStyleOpts(opacity=0.3, curve=0.5, color="source"),
            label_opts=opts.LabelOpts(position="right", font_size=12, font_weight="bold"),
            node_align="left",
        )
        .set_global_opts(
            title_opts=opts.TitleOpts(
                title="Knowledge Graph: F. nucleatum Mechanisms & Interventions",
                subtitle="Extracted via Biomedical Text Mining",
                pos_left="center"
            )
        )
    )
    
    output_html = os.path.join(os.path.dirname(CSV_PATH), 'mechanism_sankey.html')
    sankey.render(output_html)
    print(f"✅ 桑基网络图已生成: {output_html} (请使用浏览器打开此文件查看动态效果！)")

def plot_donut_chart(df):
    """绘制极性分布环形图"""
    if 'Polarity' not in df.columns:
        print("❌ CSV中缺少 'Polarity' 列")
        return

    polarity_counts = df['Polarity'].value_counts()
    colors_map = {
        'Positive': '#B22222',
        'Neutral/Uncertain': '#D3D3D3',
        'Negative': '#4682B4'
    }
    
    labels = polarity_counts.index
    colors = [colors_map.get(label, '#999999') for label in labels]
    
    fig, ax = plt.subplots(figsize=(8, 8))
    wedges, texts, autotexts = ax.pie(
        polarity_counts, 
        labels=labels, 
        autopct='%1.1f%%', 
        startangle=140, 
        colors=colors,
        wedgeprops=dict(width=0.4, edgecolor='white', linewidth=2),
        textprops={'fontsize': 12, 'fontweight': 'bold'}
    )
    
    # 中心文本逻辑
    pos_count = polarity_counts.get('Positive', 0)
    total_valid = pos_count + polarity_counts.get('Negative', 0)
    if total_valid > 0:
        pos_ratio = (pos_count / total_valid) * 100
        center_text = f"{pos_ratio:.1f}%\nPositive\nConsensus"
    else:
        center_text = "Data\nAnalysis"

    ax.text(0, 0, center_text, ha='center', va='center', fontsize=18, fontweight='bold', color='#B22222')
    plt.title('Literature Consensus on F. nucleatum and CRC', fontsize=16, fontweight='bold', pad=20)
    
    output_filename = os.path.join(os.path.dirname(CSV_PATH), 'polarity_donut_chart.png')
    plt.savefig(output_filename, dpi=300, transparent=True, bbox_inches='tight')
    print(f"✅ 环形图已保存为: {output_filename}")
    plt.close()

def plot_positive_wordcloud(df):
    """绘制正向核心动词/指标词云图 (适配 Reason 列)"""
    # 修复点 1：检查 Reason 列是否存在
    target_col = 'Reason' 
    positive_df = df[df['Polarity'] == 'Positive']
    all_terms = []
    for entry in positive_df[target_col].dropna():
        # 移除 "Verb:", "Indicator:", "StrongTerm:" 以及括号内的内容
        clean_entry = re.sub(r'(Verb:|Indicator:|StrongTerm:)', '', str(entry))
        clean_entry = re.sub(r'\(.*?\)', '', clean_entry)
        
        # 按逗号拆分多个词
        terms = [t.strip() for t in clean_entry.split(',')]
        all_terms.extend(terms)
    
    text_for_cloud = " ".join(all_terms)
    
    if not text_for_cloud.strip():
        print("⚠️ 提取出的关键词为空，无法生成词云。")
        return

    wordcloud = WordCloud(
        width=1000, height=600, 
        background_color='white', 
        colormap='Reds', 
        max_words=40,
        collocations=False
    ).generate(text_for_cloud)
    
    plt.figure(figsize=(10, 6))
    plt.imshow(wordcloud, interpolation='bilinear')
    plt.axis('off')
    plt.title('Core Pathogenic Mechanisms & Indicators', fontsize=16, fontweight='bold')
    
    output_filename = os.path.join(os.path.dirname(CSV_PATH), 'positive_verbs_wordcloud.png')
    plt.savefig(output_filename, dpi=300, bbox_inches='tight')
    print(f"✅ 词云图已保存为: {output_filename}")
    plt.close()

def plot_research_trend(df):
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        year_lookup = pd.DataFrame(json.load(f))[['pmid', 'year']]
    
    # 统一类型以便关联
    df['PMID'] = df['PMID'].astype(str)
    year_lookup['pmid'] = year_lookup['pmid'].astype(str) 
    df = pd.merge(df, year_lookup, left_on='PMID', right_on='pmid')
    df = df[df['year'] != 'N/A']
    df['year'] = pd.to_numeric(df['year'])
    
    # 统计趋势
    trend_df = df.groupby(['year', 'Polarity']).size().unstack(fill_value=0)
    cols = [c for c in ['Positive', 'Neutral/Uncertain', 'Negative'] if c in trend_df.columns]
    trend_df = trend_df[cols]

    plt.figure(figsize=(12, 6))
    colors = {'Positive': '#B22222', 'Neutral/Uncertain': '#D3D3D3', 'Negative': '#4682B4'}
    current_colors = [colors[c] for c in trend_df.columns]

    trend_df.plot(kind='area', stacked=True, ax=plt.gca(), color=current_colors, alpha=0.8)
    plt.title('Evolution of Research Consensus (Last 15 Years)', fontsize=15, fontweight='bold')
    plt.xlabel('Year')
    plt.ylabel('Sentence Count')
    
    output_file = os.path.join(os.path.dirname(CSV_PATH), 'research_trend_evolution.png')
    plt.savefig(output_file, dpi=300, transparent=True)
    print(f"✅ 趋势演进图已保存为: {output_file}")
    plt.close()
def plot_comparison_bar(combined_df):
    """对比不同细菌极性占比的堆叠条形图"""
    print("📊 正在绘制跨菌株对比图...")
    plt.figure(figsize=(12, 8))
    
    # 统计 细菌 x 极性
    comp_df = combined_df.groupby(['Bacteria', 'Polarity']).size().unstack(fill_value=0)
    # 转化为百分比
    comp_df_percent = comp_df.div(comp_df.sum(axis=1), axis=0) * 100
    
    colors = {'Positive': '#B22222', 'Neutral/Uncertain': '#D3D3D3', 'Negative': '#4682B4'}
    available_colors = [colors.get(c, '#999') for c in comp_df_percent.columns]
    
    comp_df_percent.plot(kind='barh', stacked=True, color=available_colors, ax=plt.gca())
    
    plt.title('Pathogenic Evidence Distribution Across Species', fontsize=14, fontweight='bold')
    plt.xlabel('Percentage (%)')
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig(os.path.join(os.path.dirname(CSV_PATH), "global_comparison_bar.png"), dpi=300)
    plt.close()

def generate_global_wordcloud(combined_df):
    """基于所有细菌正向结论的全局机制词云"""
    print("☁️ 正在绘制全局词云...")
    pos_data = combined_df[combined_df['Polarity'] == 'Positive']
    text = " ".join(pos_data['Reason'].astype(str))
    # 清理词缀
    text = re.sub(r'(Verb:|Indicator:|StrongTerm:|\(Stat\))', '', text)
    
    if not text.strip(): return

    wc = WordCloud(width=1200, height=600, background_color='white', colormap='tab20').generate(text)
    plt.figure(figsize=(15, 8))
    plt.imshow(wc, interpolation='bilinear')
    plt.axis('off')
    plt.savefig(os.path.join(os.path.dirname(CSV_PATH), "global_mechanism_wordcloud.png"), dpi=300)
    plt.close()

def plot_mechanism_heatmap(combined_df):
    """
    [创新可视化] 细菌-作用机制热力图
    展示不同细菌在各个生物学子类（Sub_Category）中的研究热度
    """
    print("🔥 正在绘制机制热力图...")
    # 交叉汇总数据
    heatmap_data = pd.crosstab(combined_df['Bacteria'], combined_df['Sub_Category'])
    
    plt.figure(figsize=(14, 10))
    sns.heatmap(heatmap_data, annot=True, cmap="YlOrRd", fmt='d', linewidths=.5)
    
    plt.title('Heatmap of Bacterial Impact on Biological Mechanisms', fontsize=15, fontweight='bold', pad=20)
    plt.xlabel('Research Sub-Category', fontsize=12)
    plt.ylabel('Bacterial Species', fontsize=12)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    
    plt.savefig(os.path.join(os.path.dirname(CSV_PATH), "global_mechanism_heatmap.png"), dpi=300)
    plt.close()
def main():
    if not os.path.exists(CSV_PATH):
        print(f"❌ 找不到文件: {CSV_PATH}")
        return
        
    print("读取数据中...")
    # 使用 utf-8-sig 兼容我们之前修复的编码格式
    try:
        df = pd.read_csv(CSV_PATH, encoding='utf-8-sig')
    except Exception as e:
        try:
            df = pd.read_csv(CSV_PATH, encoding='gbk')
        except Exception as e2:
            print(f"❌ 读取CSV文件失败: {e2}")
            return
    output_dir = Config.OUTPUT_DIR     
    print(f"成功读取 {len(df)} 条记录，开始绘制图表...")
    plot_sankey_diagram(df)
    plot_donut_chart(df)
    plot_positive_wordcloud(df)
    plot_research_trend(df)
    print("🎉 可视化全流程完成！请在桌面文件夹查看图片。")

if __name__ == "__main__":
    main()