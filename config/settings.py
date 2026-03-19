import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()
CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CONFIG_DIR)

class Config:
    ENTREZ_EMAIL = os.getenv("ENTREZ_EMAIL", "default@example.com")
    SEARCH_QUERY_TEMPLATE = '("{bacteria}"[Title/Abstract]) AND ("{disease}"[Title/Abstract])'
    RETMAX = 300
    OUTPUT_DIR = "Bacteria_Analysis_Reports"
    DB_PATH = os.path.join(PROJECT_ROOT, "data", "ncbi_taxonomy.sqlite")
    NAMES_DMP_PATH = os.path.join(PROJECT_ROOT, "data", "names.dmp")
