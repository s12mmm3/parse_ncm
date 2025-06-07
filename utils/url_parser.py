import re
import json
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import List, Optional, Pattern, Tuple, Type, ClassVar, Dict, Any
from nonebot.adapters import Event, Bot
from nonebot_plugin_alconna.uniseg import Hyper, UniMsg, Text
from nonebot_plugin_alconna.uniseg.tools import reply_fetch

from zhenxun.services.log import logger

from ..utils.exceptions import UrlParseError, UnsupportedUrlError


class ResourceType(Enum):
    """资源类型"""
    # 歌曲、专辑、歌单、歌手、用户、mv、短链接
    SONG = auto()
    ALBUM = auto()
    PLAYLIST = auto()
    USER = auto()
    ARTIST = auto()
    MV = auto()
    SHORT_URL = auto()


class UrlParser(ABC):
    """URL解析器基类"""

    PRIORITY: ClassVar[int] = 100
    RESOURCE_TYPE: ClassVar[ResourceType] = None

    @classmethod
    @abstractmethod
    def can_parse(cls, url: str) -> bool:
        """检查是否可以解析指定URL"""
        pass

    @classmethod
    @abstractmethod
    def parse(cls, url: str) -> Tuple[ResourceType, str]:
        """解析URL，提取资源类型和ID"""
        pass


class RegexUrlParser(UrlParser):
    """基于正则表达式的URL解析器基类"""

    PATTERN: ClassVar[Pattern] = None
    GROUP_INDEX: ClassVar[int] = 1

    @classmethod
    def can_parse(cls, url: str) -> bool:
        """检查是否可以解析指定URL"""
        if not cls.PATTERN:
            return False
        return bool(cls.PATTERN.search(url))

    @classmethod
    def parse(cls, url: str) -> Tuple[ResourceType, str]:
        """解析URL，提取资源类型和ID"""
        if not cls.RESOURCE_TYPE:
            raise ValueError(f"解析器 {cls.__name__} 未定义资源类型")

        match = cls.PATTERN.search(url)
        if not match:
            raise UrlParseError(f"URL不匹配模式: {url}")

        resource_id = match.group(cls.GROUP_INDEX)
        if not resource_id:
            raise UrlParseError(f"无法从URL提取资源ID: {url}")

        return cls.RESOURCE_TYPE, resource_id

class SongParser(RegexUrlParser):
    """网易云音乐歌曲链接解析器"""
    
    PRIORITY = 10
    RESOURCE_TYPE = ResourceType.SONG
    PATTERN = re.compile(
        r"music\.163\.com.*/song(?:\?id=|/)(\d+)",
        re.IGNORECASE          # 忽略大小写
    )
    """
    https://y.music.163.com/m/song?id=2709431534&uct2=Arr0WMm044%2BJ8enAgZ5KPw%3D%3D&fx-wechatnew=t1&fx-wxqd=c&fx-wordtest=&fx-listentest=t3&H5_DownloadVIPGift=&playerUIModeId=76001&PlayerStyles_SynchronousSharing=t3&dlt=0846&app_version=9.3.10&sc=wm&tn=
    https://music.163.com/#/song?id=2708737458
    https://music.163.com/#/song/2708737458
    """

class AlbumParser(RegexUrlParser):
    """网易云音乐专辑链接解析器"""
    
    PRIORITY = 10
    RESOURCE_TYPE = ResourceType.ALBUM
    PATTERN = re.compile(
        r"music\.163\.com.*/album(?:\?id=|/)(\d+)",
        re.IGNORECASE          # 忽略大小写
    )

class UserParser(RegexUrlParser):
    """网易云音乐用户链接解析器"""
    
    PRIORITY = 10
    RESOURCE_TYPE = ResourceType.USER
    PATTERN = re.compile(
        r"music\.163\.com.*/user(?:/home|)\?id=(\d+)",
        re.IGNORECASE          # 忽略大小写
    )
    """
    https://music.163.com/#/user/home?id=1463586082
    https://y.music.163.com/m/user?id=1463586082
    """

class PlaylistParser(RegexUrlParser):
    """网易云音乐歌单链接解析器"""
    
    PRIORITY = 10
    RESOURCE_TYPE = ResourceType.PLAYLIST
    PATTERN = re.compile(
        r"music\.163\.com.*/playlist(?:\?id=|/)(\d+)",
        re.IGNORECASE          # 忽略大小写
    )

class ArtistParser(RegexUrlParser):
    """网易云音乐歌手链接解析器"""
    
    PRIORITY = 10
    RESOURCE_TYPE = ResourceType.ARTIST
    PATTERN = re.compile(
        r"music\.163\.com.*/artist\?id=(\d+)",
        re.IGNORECASE          # 忽略大小写
    )

class MVParser(RegexUrlParser):
    """网易云音乐mv链接解析器"""
    
    PRIORITY = 10
    RESOURCE_TYPE = ResourceType.MV
    PATTERN = re.compile(
        r"music\.163\.com.*/mv(?:\?id=|/)(\d+)",
        re.IGNORECASE          # 忽略大小写
    )
    """
    https://music.163.com/mv?id=14575961
    https://music.163.com/#/mv/14575961
    """

class ShortUrlParser(RegexUrlParser):
    """网易云短链接解析器"""

    PRIORITY = 10
    RESOURCE_TYPE = ResourceType.SHORT_URL
    PATTERN = re.compile(r"163cn\.tv/([A-Za-z0-9]+)")


class UrlParserRegistry:
    """URL解析器注册表"""

    _parsers: List[Type[UrlParser]] = []

    @classmethod
    def register(cls, parser_class: Type[UrlParser]):
        """注册解析器"""
        if parser_class not in cls._parsers:
            cls._parsers.append(parser_class)
            cls._parsers.sort(key=lambda p: p.PRIORITY)
            logger.debug(f"注册URL解析器: {parser_class.__name__}", "网易云解析")

    @classmethod
    def get_parser(cls, url: str) -> Optional[Type[UrlParser]]:
        """获取能够解析指定URL的解析器"""
        for parser in cls._parsers:
            if parser.can_parse(url):
                return parser
        return None

    @classmethod
    def parse(cls, url: str) -> Tuple[ResourceType, str]:
        """解析URL"""
        parser = cls.get_parser(url)
        if not parser:
            raise UnsupportedUrlError(f"不支持的URL格式: {url}")

        try:
            return parser.parse(url)
        except UrlParseError:
            raise
        except Exception as e:
            raise UrlParseError(f"解析URL时出错: {e}") from e

UrlParserRegistry.register(SongParser)
UrlParserRegistry.register(AlbumParser)
UrlParserRegistry.register(UserParser)
UrlParserRegistry.register(PlaylistParser)
UrlParserRegistry.register(ArtistParser)
UrlParserRegistry.register(MVParser)
UrlParserRegistry.register(ShortUrlParser)

def extract_url_from_text(text: str) -> Optional[str]:
    """提取URL"""
    from .common import extract_url_from_text as common_extract_url

    return common_extract_url(text)


def extract_ncm_url_from_miniprogram(raw_str: str) -> Optional[str]:
    """从小程序消息提取网易云URL"""
    logger.debug(f"开始解析小程序消息，原始数据长度: {len(raw_str)}")

    try:
        data = json.loads(raw_str)

        excluded_apps = [
            "com.tencent.qun.invite",
            "com.tencent.qqav.groupvideo",
            "com.tencent.mobileqq.reading",
            "com.tencent.weather",
        ]

        app_name = data.get("app") or data.get("meta", {}).get("detail_1", {}).get(
            "appid"
        )
        if app_name in excluded_apps:
            logger.debug(f"小程序 app '{app_name}' 在排除列表，跳过", "网易云解析")
            return None

        view_data = data.get("view", "")
        meta_data = data.get("meta", {})
        detail_data = meta_data.get(view_data, {})

        jump_url = (detail_data.get("jumpUrl")
            or detail_data.get("musicUrl")
        )

        if jump_url and isinstance(jump_url, str):
            if "music.163.com" in jump_url or "163cn.tv" in jump_url:
                logger.info(f"从小程序JSON数据提取到网易云链接: {jump_url}")
                return jump_url

    except Exception as e:
        logger.debug(f"解析小程序JSON失败: {e}")

    return None


def extract_ncm_url_from_message(
    message, check_hyper: bool = True
) -> Optional[str]:
    """从消息提取网易云URL"""
    target_url = None

    if check_hyper:
        for seg in message:
            if isinstance(seg, Hyper) and seg.raw:
                try:
                    extracted_url = extract_ncm_url_from_miniprogram(seg.raw)
                    if extracted_url:
                        target_url = extracted_url
                        logger.debug(f"从Hyper段提取到网易云链接: {target_url}")
                        break
                except Exception as e:
                    logger.debug(f"解析Hyper段失败: {e}")

    if not target_url:
        plain_text = message.extract_plain_text().strip()
        if plain_text:
            parser_found = UrlParserRegistry.get_parser(plain_text)
            if parser_found:
                match = (
                    parser_found.PATTERN.search(plain_text)
                    if parser_found.PATTERN
                    else None
                )
                if match:
                    target_url = match.group(0)
                    logger.debug(f"从文本内容提取到URL: {target_url}")
            else:
                url = extract_url_from_text(plain_text)
                if url and ("music.163.com" in url or "163cn.tv" in url):
                    target_url = url
                    logger.debug(f"从文本内容提取到通用URL: {target_url}")

    return target_url


async def extract_ncm_url_from_reply(reply: Optional[UniMsg]) -> Optional[str]:
    """从回复消息中提取网易云URL"""
    if not reply or not reply.msg:
        logger.debug("回复消息为空")
        return None

    target_url = None
    
    for seg in reply.msg:
        if isinstance(seg, Hyper) and seg.raw:
            logger.debug(f"处理回复消息的 Hyper 段，raw 长度: {len(seg.raw)}")
            extracted_url = extract_ncm_url_from_miniprogram(seg.raw)
            if extracted_url:
                target_url = extracted_url
                logger.info(f"从回复消息提取到网易云链接: {target_url}")
                break

    if not target_url:
        patterns = {
            "b23_tv": ShortUrlParser.PATTERN,
        }
        url_match_order = ["b23_tv", "video", "bangumi", "live", "article", "opus"]

        for seg in reply.msg:
            if isinstance(seg, Text):
                text_content = seg.text.strip()
                if not text_content:
                    continue
                logger.debug(f"检查回复消息的 Text 段: '{text_content}'")

                for key in url_match_order:
                    match = patterns[key].search(text_content)
                    if match:
                        potential_url = match.group(0)
                        if (
                            potential_url.startswith("http")
                            or "b23.tv" in potential_url
                            or key == "b23_tv"
                        ):
                            target_url = potential_url
                            logger.info(f"从回复消息提取到网易云链接: {target_url}")
                            break

                if target_url:
                    break

                if not target_url:
                    match = patterns["pure_video_id"].search(text_content)
                    if match:
                        target_url = match.group(0)
                        logger.info(f"从回复消息提取到网易云视频ID: {target_url}")
                        break

        if not target_url:
            try:
                plain_text = reply.msg.extract_plain_text().strip()
                if plain_text:
                    logger.debug(f"尝试从回复消息的纯文本提取: '{plain_text}'")

                    bangumi_pattern = re.compile(
                        r"(?:https?://)?(?:www\.|m\.)?bilibili\.com/bangumi/play/(ss\d+|ep\d+)"
                    )
                    bangumi_match = bangumi_pattern.search(plain_text)
                    if bangumi_match:
                        target_url = bangumi_match.group(0)
                        logger.info(f"从回复消息提取到网易云番剧链接: {target_url}")
                    else:
                        for key in url_match_order:
                            match = patterns[key].search(plain_text)
                            if match:
                                potential_url = match.group(0)
                                if (
                                    potential_url.startswith("http")
                                    or "b23.tv" in potential_url
                                    or key == "b23_tv"
                                ):
                                    target_url = potential_url
                                    logger.info(
                                        f"从回复消息提取到网易云链接: {target_url}"
                                    )
                                    break

                        if not target_url:
                            match = patterns["pure_video_id"].fullmatch(plain_text)
                            if match:
                                target_url = match.group(0)
                                logger.info(f"从回复消息提取到网易云视频ID: {target_url}")
            except Exception as e:
                logger.warning(f"提取回复纯文本失败: {e}")

    return target_url


async def extract_ncm_url_from_json_data(json_data: str) -> Optional[str]:
    """从JSON数据中提取网易云URL"""
    if not json_data:
        return None

    qqdocurl_match = re.search(r'"qqdocurl"\s*:\s*"([^"]+)"', json_data)
    if qqdocurl_match:
        qqdocurl = qqdocurl_match.group(1).replace("\\", "")
        if "163cn.tv" in qqdocurl or "music.163.com" in qqdocurl:
            logger.info(f"从JSON数据中提取到网易云链接: {qqdocurl}")
            return qqdocurl

    url_match = re.search(
        r'https?://[^\s"\']+(?:music\.163\.com|163cn\.tv)[^\s"\']*', json_data
    )
    if url_match:
        extracted_url = url_match.group(0)
        logger.info(f"从JSON数据中提取到网易云链接: {extracted_url}")
        return extracted_url

    return None


async def extract_bilibili_url_from_event(bot: Bot, event: Event) -> Optional[str]:
    """从事件中提取网易云URL（包括回复和当前消息）"""
    target_url = None

    try:
        reply = await reply_fetch(event, bot)
        if reply:
            logger.debug("找到回复消息")
            target_url = await extract_ncm_url_from_reply(reply)
            if target_url:
                return target_url

        if hasattr(event, "model_dump"):
            raw_event = event.model_dump()
        elif hasattr(event, "dict"):
            raw_event = event.dict()
        else:
            raw_event = {}
            logger.debug("事件对象没有model_dump或dict方法")

        if hasattr(event, "reply") and event.reply:
            logger.debug("事件中包含回复信息")

            reply_message = event.reply.message
            logger.debug("获取到回复消息")

            for seg in reply_message:
                if (
                    hasattr(seg, "type")
                    and seg.type == "json"
                    and hasattr(seg, "data")
                    and "data" in seg.data
                ):
                    json_data = seg.data["data"]
                    logger.debug("找到回复消息中的JSON数据")

                    extracted_url = await extract_ncm_url_from_json_data(json_data)
                    if extracted_url:
                        target_url = extracted_url
                        return target_url

        elif "reply" in raw_event:
            logger.debug("原始事件中包含回复字段")

            reply_data = raw_event.get("reply", {})
            if "message" in reply_data:
                reply_message = reply_data["message"]
                logger.debug("获取到原始回复消息")

                json_match = re.search(r"\[CQ:json,data=(.+?)\]", str(reply_message))
                if json_match:
                    json_data = json_match.group(1)
                    logger.debug("找到原始回复消息中的JSON数据")

                    extracted_url = await extract_ncm_url_from_json_data(json_data)
                    if extracted_url:
                        target_url = extracted_url
                        return target_url

        message = event.get_message()
        reply_id = None

        for i, seg in enumerate(message):
            logger.debug(f"检查消息段 {i}")
            if hasattr(seg, "type") and seg.type == "reply":
                logger.debug("找到回复段")
                if hasattr(seg, "data") and "id" in seg.data:
                    reply_id = seg.data["id"]
                    logger.debug(f"从消息段中提取到回复ID: {reply_id}")
                    break

        if reply_id and hasattr(bot, "get_msg"):
            logger.debug("尝试使用bot.get_msg获取消息")
            try:
                msg_info = await bot.get_msg(message_id=int(reply_id))
                logger.debug("获取到消息")

                if "message" in msg_info:
                    raw_message = msg_info["message"]
                    logger.debug("获取到原始消息内容")

                    if isinstance(raw_message, str) and "json" in raw_message:
                        logger.debug("消息包含JSON内容，可能是小程序")
                        json_match = re.search(r"\[json:data=(.+?)\]", raw_message)
                        if json_match:
                            json_data = json_match.group(1)
                            logger.debug("提取到JSON数据")

                            extracted_url = await extract_ncm_url_from_json_data(
                                json_data
                            )
                            if extracted_url:
                                target_url = extracted_url
                                return target_url
            except Exception as e:
                logger.error(f"使用bot.get_msg获取消息失败: {e}")

    except Exception as e:
        logger.error(f"检查事件回复信息时出错: {e}")

    try:
        current_message = event.get_message()

        for seg in current_message:
            if isinstance(seg, Hyper) and seg.raw:
                extracted_url = await extract_ncm_url_from_miniprogram(seg.raw)
                if extracted_url:
                    target_url = extracted_url
                    logger.info(f"从当前消息提取到网易云链接: {target_url}")
                    return target_url

        target_url = extract_ncm_url_from_message(current_message)
        if target_url:
            return target_url

    except Exception as e:
        logger.error(f"从当前消息提取URL失败: {e}")

    return target_url
