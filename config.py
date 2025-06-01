from typing import Optional

try:
    from bilibili_api import Credential
except ImportError:
    raise ImportError(
        "错误：无法导入 bilibili_api 模块。\n"
        "请确保已安装 bilibili-api-python 包，而不是 bilibili-api。\n"
        "请使用以下命令安装：pip install bilibili-api-python"
    )
from zhenxun.configs.config import Config
from zhenxun.configs.path_config import DATA_PATH, TEMP_PATH
from zhenxun.services.log import logger

MODULE_NAME = "parse_ncm"
base_config = Config.get(MODULE_NAME)

HTTP_TIMEOUT = 30
HTTP_CONNECT_TIMEOUT = 10

PLUGIN_CACHE_DIR = DATA_PATH / MODULE_NAME / "cache"
PLUGIN_CACHE_DIR.mkdir(parents=True, exist_ok=True)

PLUGIN_TEMP_DIR = TEMP_PATH / MODULE_NAME
PLUGIN_TEMP_DIR.mkdir(parents=True, exist_ok=True)

# 图片缓存目录
IMAGE_CACHE_DIR = PLUGIN_TEMP_DIR / "image"
IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

SCREENSHOT_ELEMENT_OPUS = "#app > div.opus-detail > div.bili-opus-view"
SCREENSHOT_ELEMENT_ARTICLE = ".article-holder"
SCREENSHOT_TIMEOUT = 60

# 视频下载和发送相关配置
DOWNLOAD_TIMEOUT = 120  # 下载超时时间(秒)
DOWNLOAD_MAX_RETRIES = 3  # 下载文件最大重试次数
SEND_VIDEO_MAX_RETRIES = 3  # 发送视频最大重试次数
SEND_VIDEO_RETRY_DELAY = 5.0  # 发送视频重试基础延迟(秒)
SEND_VIDEO_TIMEOUT = 120  # 发送视频超时时间(秒)
