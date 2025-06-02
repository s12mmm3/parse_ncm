import traceback
import asyncio
from typing import Union, Optional
from nonebot import on_message, get_driver
from nonebot.plugin import PluginMetadata
from nonebot.params import RawCommand
from nonebot.adapters import Bot, Event

from nonebot_plugin_uninfo import Uninfo
from nonebot_plugin_session import EventSession
from nonebot_plugin_alconna import UniMsg, Text, Image

from zhenxun.services.log import logger
from zhenxun.utils.enum import PluginType

from zhenxun.utils.common_utils import CommonUtils
from zhenxun.configs.utils import Task, RegisterConfig, PluginExtraData

from .config import (
    base_config,
)

from .services.parser_service import ParserService
from .utils.message import (
    MessageBuilder,
)
from .utils.exceptions import (
    UrlParseError,
    UnsupportedUrlError,
    NcmRequestError,
    NcmResponseError,
    ScreenshotError,
)
from .model import SongInfo, AlbumInfo, UserInfo
from .utils.url_parser import UrlParserRegistry, extract_ncm_url_from_message

__plugin_meta__ = PluginMetadata(
    name="网易云内容解析",
    description="网易云内容解析（歌曲、专辑、歌单、歌手、用户），支持被动解析。",
    usage="""
    插件功能：
    1. 被动解析：自动监听消息中的网易云链接，并发送解析结果。
       - 支持歌曲、专辑。
       - 支持短链(163cn.tv)。
       - 开启方式：
         方式一：使用命令「开启群被动网易云解析」或「关闭群被动网易云解析」
         方式二：在bot的Webui页面的「群组」中修改群被动状态「网易云解析」
    """.strip(),
    extra=PluginExtraData(
        author="overwriter",
        version="1.0.0",
        plugin_type=PluginType.DEPENDANT,
        menu_type="其他",
        configs=[],
        tasks=[Task(module="parse_ncm", name="网易云解析")],
    ).dict(),
)


async def _rule(
    uninfo: Uninfo, message: UniMsg, cmd: tuple | None = RawCommand()
) -> bool:
    # if await CommonUtils.task_is_block(uninfo, "parse_ncm"):
    #     return False

    url = extract_ncm_url_from_message(message, check_hyper=check_hyper)

    if url:
        logger.debug(f"从消息中提取到网易云URL: {url}", "网易云解析")
        return True

    plain_text_for_check = message.extract_plain_text().strip()
    if plain_text_for_check:
        logger.debug(f"检查文本内容: '{plain_text_for_check[:100]}...'", "网易云解析")
        parser_found = UrlParserRegistry.get_parser(plain_text_for_check)
        if parser_found and parser_found.__name__ == "PureVideoIdParser":
            if parser_found.PATTERN.fullmatch(plain_text_for_check):
                logger.debug("文本内容匹配到纯视频ID，符合规则", "网易云解析")
                return True

    logger.debug("消息不符合被动解析规则", "网易云解析")
    return False

_matcher = on_message(priority=50, block=False, rule=_rule)

check_hyper = True # 是否解析小程序

@_matcher.handle()
async def _(
    bot: Bot,
    event: Event,
    session: EventSession,
    message: UniMsg,
):
    logger.debug(f"Handler received message: {message}", "网易云解析")

    parsed_content: Union[
        SongInfo, AlbumInfo, UserInfo, None
    ] = None

    target_url = extract_ncm_url_from_message(message, check_hyper=check_hyper)

    if not target_url:
        logger.debug("未在消息中找到有效的 网易云 URL，退出处理", "网易云解析")
        return

    try:
        logger.info(f"开始解析URL: {target_url}", "网易云解析", session=session)

        parsed_content: Union[
            SongInfo, AlbumInfo, UserInfo, None
        ] = await ParserService.parse(target_url)
        logger.debug(f"解析结果类型: {type(parsed_content).__name__}", "网易云解析")

    except (UrlParseError, UnsupportedUrlError) as e:
        logger.warning(
            f"URL解析失败: {target_url}. 原因: {e}",
            "网易云解析",
            session=session,
        )
        return

    except (NcmRequestError, NcmResponseError) as e:
        logger.error(
            f"API请求或响应错误: {target_url}. 类型: {type(e).__name__}, 原因: {e}",
            "网易云解析",
            session=session,
        )
        return

    except ScreenshotError as e:
        logger.error(
            f"截图失败: {target_url}. 原因: {e}",
            "网易云解析",
            session=session,
        )
        return

    except Exception as e:
        logger.error(
            f"处理URL时发生意外错误: {target_url}",
            "网易云解析",
            session=session,
            e=e,
        )
        logger.error(traceback.format_exc())
        return

    if parsed_content:
        logger.debug(
            f"Building message for parsed content type: {type(parsed_content).__name__}",
            "网易云解析",
        )
        try:
            final_message: UniMsg | None = None
            render_enabled = base_config.get("RENDER_AS_IMAGE", False)

            if isinstance(parsed_content, SongInfo):
                final_message = await MessageBuilder.build_song_message(parsed_content)
            elif isinstance(parsed_content, AlbumInfo):
                final_message = await MessageBuilder.build_album_message(parsed_content)
            elif isinstance(parsed_content, UserInfo):
                final_message = await MessageBuilder.build_user_message(parsed_content)
            else:
                logger.warning(
                    f"内容类型不支持或已禁用: {type(parsed_content).__name__}",
                    "网易云解析",
                )

            if final_message:
                logger.debug(f"准备发送最终消息: {final_message}", "网易云解析")
                await final_message.send()
                logger.info(
                    f"成功被动解析并发送: {target_url}", "网易云解析", session=session
                )

            else:
                logger.info(
                    f"最终消息为空或未构建 (被动解析): {target_url}",
                    "网易云解析",
                    session=session,
                )

        except Exception as e:
            logger.error(
                f"Error building or sending message for {target_url}: {e}",
                "网易云解析",
                session=session,
            )
            logger.error(traceback.format_exc())
