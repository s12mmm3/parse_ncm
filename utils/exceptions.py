from typing import Any, Dict, Optional


class NcmBaseException(Exception):
    """网易云相关异常基类"""

    def __init__(
        self,
        message: str,
        cause: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """初始化异常"""
        self.message = message
        self.cause = cause
        self.context = context or {}
        super().__init__(message)

    def __str__(self) -> str:
        result = self.message

        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            result += f" [上下文: {context_str}]"

        if self.cause:
            result += f" (原因: {self.cause})"

        return result

    def with_context(self, **kwargs) -> "NcmBaseException":
        """添加上下文信息并返回自身"""
        self.context.update(kwargs)
        return self


class NetworkError(NcmBaseException):
    """网络错误基类"""

    pass


class NcmRequestError(NetworkError):
    """网易云 API请求错误，如网络连接失败、超时等"""

    pass


class NcmResponseError(NetworkError):
    """网易云 API响应数据错误，如响应格式错误、状态码异常等"""

    pass


class RateLimitError(NetworkError):
    """请求频率限制错误"""

    def __init__(self, message: str, retry_after: Optional[int] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class UrlError(NcmBaseException):
    """URL错误基类"""

    pass


class UrlParseError(UrlError):
    """无法解析URL或识别类型，如URL格式错误、缺少必要参数等"""

    pass


class UnsupportedUrlError(UrlParseError):
    """不支持的URL类型，如非网易云URL或未实现支持的网易云页面类型"""

    pass


class ShortUrlError(UrlError):
    """短链接解析错误"""

    pass


class ResourceError(NcmBaseException):
    """资源错误基类"""

    pass


class FeatureError(NcmBaseException):
    """功能错误基类"""

    pass


class ScreenshotError(FeatureError):
    """截图失败，如浏览器渲染错误、页面加载失败等"""

    pass


class DownloadError(FeatureError):
    """下载失败，如无法获取下载链接、写入文件失败等"""

    pass


class MediaProcessError(FeatureError):
    """媒体处理错误，如视频合并失败、格式转换失败等"""

    pass


class ConfigError(NcmBaseException):
    """配置错误，如配置项缺失、格式错误等"""

    pass
