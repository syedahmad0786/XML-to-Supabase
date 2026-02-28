"""
Shared configuration for Baidu video generation scripts.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Baidu Qianfan API credentials
QIANFAN_AK = os.getenv("QIANFAN_AK", "")
QIANFAN_SK = os.getenv("QIANFAN_SK", "")

# Qianfan API endpoints
QIANFAN_AUTH_URL = "https://aip.baidubce.com/oauth/2.0/token"
QIANFAN_VIDEO_API_BASE = "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/video"

# Huixiang platform
HUIXIANG_URL = "https://huixiang.baidu.com"

# Vidu model settings
VIDU_DEFAULT_DURATION = 5       # seconds (5 or 10)
VIDU_DEFAULT_RESOLUTION = "1080p"
VIDU_DEFAULT_MODEL = "turbo"    # turbo, lite, pro

# Output defaults
DEFAULT_OUTPUT_DIR = "output"
