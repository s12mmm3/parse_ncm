import re
from typing import Optional, TypeVar

from zhenxun.services.log import logger

T = TypeVar("T")

def extract_url_from_text(text: str) -> Optional[str]:
    """从文本中提取第一个URL"""
    url_pattern = re.compile(
        r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[/\w\.-]*(?:\?[/\w\.-=%&+]*)?"
    )
    match = url_pattern.search(text)
    if match:
        return match.group(0)
    return None


def calculate_retry_wait_time(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential: bool = True,
    jitter: bool = True,
) -> float:
    """计算重试等待时间"""
    import random

    if exponential:
        wait_time = base_delay * (2 ** (attempt - 1))
    else:
        wait_time = base_delay * attempt

    wait_time = min(wait_time, max_delay)

    if jitter:
        jitter_amount = wait_time * 0.25
        wait_time += random.uniform(-jitter_amount, jitter_amount)
        wait_time = max(base_delay * 0.5, wait_time)

    return wait_time
