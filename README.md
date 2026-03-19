BioMiner
========

项目简介
- BioMiner 是用于细菌相关文献抓取、分析与可视化的 Python 工具集，包含 `src` 中的抓取、解析与可视化脚本，结果输出在 `outputs` 或 `Bacteria_Analysis_Reports` 文件夹中。

快速开始
1. 创建虚拟环境并激活：

   Windows (PowerShell):
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

3. 运行主程序：
   ```bash
   python -m src.gui.py
   ```

版本锁定
- 若需锁定当前环境依赖，使用 `pip freeze > requirements.txt` 生成精确版本列表（推荐在新虚拟环境中运行）。

注意
- 若 `config/settings.py` 包含私密信息，请在上传前移除或使用环境变量替换敏感配置。
