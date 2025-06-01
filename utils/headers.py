from typing import Dict

from zhenxun.utils.user_agent import get_user_agent_str


def get_ncm_headers() -> Dict[str, str]:
    """获取网易云请求头"""
    user_agent = get_user_agent_str()

    headers = {
        "User-Agent": user_agent,
    }

    return headers
