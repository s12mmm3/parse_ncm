import asyncio
import os
import aiofiles
import httpx
from pathlib import Path
from typing import Optional, Dict

from zhenxun.services.log import logger

from ..config import PLUGIN_TEMP_DIR

async def download_file(
    url: str,
    file_path: Path,
    headers: Optional[Dict[str, str]] = None,
    proxies: Optional[Dict[str, str]] = None,
    chunk_size: int = 8192,
    timeout: int = 60,
    max_retries: int = 3,
) -> bool:
    """下载文件"""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    download_timeout = httpx.Timeout(timeout)

    current_size = 0
    if file_path.exists():
        os.remove(file_path)
        # current_size = file_path.stat().st_size
        # if current_size > 0:
        #     logger.info(
        #         f"文件已存在，尝试断点续传: {file_path.name}, 已下载: {current_size / 1024 / 1024:.2f}MB"
        #     )
        #     if headers is None:
        #         headers = {}
        #     headers["Range"] = f"bytes={current_size}-"

    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(
                headers=headers,
                proxies=proxies,
                timeout=download_timeout,
                follow_redirects=True,
            ) as client:
                async with client.stream("GET", url) as resp:
                    resp.raise_for_status()

                    if current_size > 0 and resp.status_code == 206:
                        logger.debug(
                            f"服务器支持断点续传，从 {current_size} 字节继续下载"
                        )
                    elif current_size > 0 and resp.status_code == 200:
                        logger.warning("服务器不支持断点续传，将重新下载完整文件")
                        current_size = 0

                    total_len = int(resp.headers.get("content-length", 0))
                    if resp.status_code == 206:
                        total_len += current_size

                    mode = (
                        "ab" if current_size > 0 and resp.status_code == 206 else "wb"
                    )
                    downloaded_size = current_size

                    async with aiofiles.open(file_path, mode) as f:
                        async for chunk in resp.aiter_bytes(chunk_size=chunk_size):
                            await f.write(chunk)
                            downloaded_size += len(chunk)

                    if total_len == 0 or downloaded_size == total_len:
                        logger.debug(
                            f"文件流下载完成: {file_path.name}, 大小: {downloaded_size / 1024 / 1024:.2f}MB"
                        )
                        return True
                    else:
                        logger.warning(
                            f"文件下载不完整: {file_path.name}, {downloaded_size}/{total_len} ({downloaded_size / total_len * 100:.1f}%)"
                        )

        except (httpx.HTTPError, httpx.RequestError, asyncio.TimeoutError) as e:
            is_last_attempt = attempt >= max_retries

            from .common import calculate_retry_wait_time

            delay = calculate_retry_wait_time(attempt=attempt)

            error_type = type(e).__name__
            error_msg = str(e)

            if not is_last_attempt:
                logger.warning(
                    f"下载失败 (尝试 {attempt}/{max_retries}): {file_path.name}, 错误: {error_type}: {error_msg}, "
                    f"{delay:.1f}秒后重试"
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"下载失败，已达到最大重试次数 ({max_retries}): {file_path.name}, 错误: {error_type}: {error_msg}"
                )
                return False

    return False

def get_temp_file_path(
    prefix: str,
    suffix: str,
    identifier: str,
    title: Optional[str] = None,
) -> Path:
    """生成临时文件路径"""
    filename = f"{prefix}{identifier}{suffix}"
    return PLUGIN_TEMP_DIR / filename
