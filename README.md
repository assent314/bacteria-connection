# Bacteria-Connection: 菌群-疾病关联文献挖掘与可视化工具

🚀 **Bacteria-Connection** 是一款专为生物医学研究（如 iGEM 建模、合成生物学调研）设计的文献挖掘系统。它可以自动从 PubMed 抓取特定疾病相关的细菌研究，利用 NLP 提取极性关系，并生成多维度的机制可视化报告。

## 核心功能
- **动态发现**：基于疾病关键词自动筛选高频关联菌株。
- **机制提取**：使用 `SciSpacy` 识别摘要中的生物学作用机制（促进/抑制）。
- **多维可视化**：生成桑基图（Sankey）、演进趋势图、机制热力图及词云。
- **图形化界面**：支持一键启动，无需复杂命令行操作。

---

## 快速开始

### 1. 克隆仓库
```bash
git clone [https://github.com/assent314/bacteria-connection.git](https://github.com/assent314/bacteria-connection.git)
cd bacteria-connection
2. 环境安装
建议使用 Python 3.9+ 环境。

Bash
pip install -r requirements.txt
# 安装医学 NLP 实体识别模型
pip install [https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.1/en_core_sci_sm-0.5.1.tar.gz](https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.1/en_core_sci_sm-0.5.1.tar.gz)
3. 数据准备 (关键步骤 ❗)
由于 NCBI 分类数据库体积较大，仓库未包含该文件。

下载数据：前往 NCBI Taxonomy FTP 下载 taxdump.tar.gz。

解压文件：解压后找到 names.dmp 文件。

放置路径：在项目根目录下新建 data/ 文件夹，将 names.dmp 放入其中：

Plaintext
bacteria-connection/
├── data/
│   └── names.dmp  <-- 放在这里
├── config/
└── ...
4. 配置设置
在运行前，你需要配置个人信息和路径：

环境变量：在根目录创建 .env 文件（或修改 config/settings.py）：

Plaintext
ENTREZ_EMAIL=你的邮箱@example.com
Settings 配置：检查 config/settings.py 中的 Config 类，确保 DB_PATH 指向正确的本地数据库生成位置。

使用指南
方式 A：GUI 界面（推荐）
直接运行根目录下的 gui.pyw 或 gui.py：

Bash
python src/gui.py
在界面中输入目标疾病（如 Colorectal cancer），点击 "Run Analysis" 即可。

方式 B：命令行脚本
运行 main.py 执行默认配置的批量分析：

Bash
python src/main.py
输出结果
分析完成后，所有报告将保存在 outputs/ 文件夹下：

Global_Summary_Analysis/: 跨菌株的比对热力图和汇总表。

[菌名]_Report/: 单个菌株的独立分析图表。

贡献与致谢
作者: assent314

技术支持: 基于 SciSpacy 与 NCBI Entrez API 构建。
