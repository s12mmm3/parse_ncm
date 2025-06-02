import asyncio
import time
import functools
from typing import Dict, Any, Optional, Callable, TypeVar, Awaitable, Union, List, Type
import aiohttp
from collections import defaultdict

from zhenxun.services.log import logger

from ..config import HTTP_TIMEOUT, HTTP_CONNECT_TIMEOUT
from ..utils.exceptions import (
    NcmRequestError,
    RateLimitError,
    NcmBaseException,
)
from ..utils.headers import get_ncm_headers

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])
AF = TypeVar("AF", bound=Callable[..., Awaitable[Any]])

RetryConditionType = Callable[[Exception, int], bool]


def _log_exception(
    e: Exception, error_msg: str, log_level: str, error_context: Dict[str, Any]
):
    """记录异常日志"""
    log_func = getattr(logger, log_level)
    if isinstance(e, NcmBaseException):
        e.with_context(**error_context)
        log_func(f"{error_msg}: {e}", "网易云解析")
    else:
        log_func(f"{error_msg}: {e}", "网易云解析")


def handle_errors(
    error_msg: str = "操作执行失败",
    exc_types: Union[Type[Exception], List[Type[Exception]]] = Exception,
    log_level: str = "error",
    reraise: bool = True,
    default_return: Any = None,
    context: Optional[Dict[str, Any]] = None,
) -> Callable[[F], F]:
    """同步函数错误处理装饰器"""
    if isinstance(exc_types, type) and issubclass(exc_types, Exception):
        exc_types = [exc_types]

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except tuple(exc_types) as e:
                error_context = context or {}
                error_context.update(
                    {
                        "function": func.__name__,
                        "args": str(args),
                        "kwargs": str(kwargs),
                    }
                )

                _log_exception(e, error_msg, log_level, error_context)

                if reraise:
                    raise

                return default_return

        return wrapper

    return decorator


def async_handle_errors(
    error_msg: str = "操作执行失败",
    exc_types: Union[Type[Exception], List[Type[Exception]]] = Exception,
    log_level: str = "error",
    reraise: bool = True,
    default_return: Any = None,
    context: Optional[Dict[str, Any]] = None,
) -> Callable[[AF], AF]:
    """异步函数错误处理装饰器"""
    if isinstance(exc_types, type) and issubclass(exc_types, Exception):
        exc_types = [exc_types]

    def decorator(func: AF) -> AF:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except tuple(exc_types) as e:
                error_context = context or {}
                error_context.update(
                    {
                        "function": func.__name__,
                        "args": str(args),
                        "kwargs": str(kwargs),
                    }
                )

                _log_exception(e, error_msg, log_level, error_context)

                if reraise:
                    raise

                return default_return

        return wrapper

    return decorator


class RateLimiter:
    """请求限流器，控制对特定域名的请求频率"""

    _domain_limits: Dict[str, tuple[float, float]] = {}

    _domain_counters = defaultdict(int)

    _domain_rate_limits = {
    }

    _DEFAULT_INTERVAL = 0.2

    @classmethod
    async def acquire(cls, url: str) -> float:
        """获取请求许可"""
        domain = url.split("//")[-1].split("/")[0]

        interval = cls._domain_rate_limits.get(domain, cls._DEFAULT_INTERVAL)

        last_time, _ = cls._domain_limits.get(domain, (0, interval))
        current_time = time.time()
        wait_time = max(0, last_time + interval - current_time)

        if wait_time > 0:
            logger.debug(f"限流: 等待 {wait_time:.2f}s 后请求 {domain}", "网易云解析")
            await asyncio.sleep(wait_time)

        cls._domain_limits[domain] = (time.time(), interval)

        cls._domain_counters[domain] += 1
        if cls._domain_counters[domain] % 10 == 0:
            logger.debug(
                f"已对 {domain} 发送 {cls._domain_counters[domain]} 个请求", "网易云解析"
            )

        return wait_time


class NetworkService:
    """网络请求服务，提供优化的请求方法"""

    _session: Optional[aiohttp.ClientSession] = None

    _session_lock = asyncio.Lock()

    @classmethod
    async def get_session(cls) -> aiohttp.ClientSession:
        """获取或创建HTTP会话"""
        async with cls._session_lock:
            if cls._session is None or cls._session.closed:
                timeout = aiohttp.ClientTimeout(
                    total=HTTP_TIMEOUT,
                    connect=HTTP_CONNECT_TIMEOUT,
                )
                cls._session = aiohttp.ClientSession(
                    timeout=timeout,
                    headers=get_ncm_headers(),
                )
                logger.debug("创建了新的HTTP会话", "网易云解析")
            return cls._session

    @classmethod
    async def get(
        cls,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        use_rate_limit: bool = True,
        max_attempts: int = 3,
    ) -> aiohttp.ClientResponse:
        """发送GET请求"""
        if use_rate_limit:
            await RateLimiter.acquire(url)

        context = {
            "url": url,
            "params": str(params) if params else None,
            "attempt": 0,
            "max_attempts": max_attempts,
        }

        for attempt in range(1, max_attempts + 1):
            context["attempt"] = attempt

            try:
                session = await cls.get_session()

                if timeout:
                    timeout_obj = aiohttp.ClientTimeout(total=timeout)
                else:
                    timeout_obj = session.timeout

                response = await session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=timeout_obj,
                    allow_redirects=True,
                )

                if response.status == 429:
                    retry_after = int(response.headers.get("Retry-After", "5"))
                    logger.warning(
                        f"请求频率限制 ({attempt}/{max_attempts}): {url}, 需等待 {retry_after}s",
                        "网易云解析",
                    )

                    if attempt < max_attempts:
                        await asyncio.sleep(retry_after)
                        continue
                    else:
                        raise RateLimitError(
                            f"请求频率限制: {url}",
                            retry_after=retry_after,
                            context=context,
                        )

                return response

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt < max_attempts:
                    wait_time = 1.0 * (2 ** (attempt - 1))
                    logger.warning(
                        f"请求失败 ({attempt}/{max_attempts}): {url}, 等待 {wait_time:.1f}s 后重试: {e}",
                        "网易云解析",
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        f"请求失败 ({attempt}/{max_attempts}): {url}: {e}", "网易云解析"
                    )
                    raise NcmRequestError(f"请求失败: {e}", context=context) from e

            except Exception as e:
                logger.error(
                    f"请求异常 ({attempt}/{max_attempts}): {url}: {e}", "网易云解析"
                )
                raise NcmRequestError(f"请求异常: {e}", context=context) from e

    @classmethod
    @async_handle_errors(
        error_msg="解析短链接失败",
        exc_types=[aiohttp.ClientError, asyncio.TimeoutError, NcmRequestError],
        reraise=True,
    )
    async def resolve_short_url(cls, url: str, max_attempts: int = 3) -> str:
        """解析短链接"""
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        async with await cls.get(
            url, use_rate_limit=True, timeout=10, max_attempts=max_attempts
        ) as response:
            resolved_url = str(response.url)
            clean_url = resolved_url

            logger.debug(f"短链接 {url} 解析为 {resolved_url}", "网易云解析")
            if clean_url != resolved_url:
                logger.debug(f"清理后的URL: {clean_url}", "网易云解析")

            return clean_url