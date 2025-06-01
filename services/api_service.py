import asyncio
import json
from typing import Dict, Any

import aiohttp
import requests

from zhenxun.services.log import logger

from ..model import (
    SongInfo,
)
from ..utils.exceptions import (
    NcmResponseError,
    ResourceNotFoundError,
    RateLimitError,
)


RETRYABLE_EXCEPTIONS = (
    aiohttp.ClientError,
    asyncio.TimeoutError,
    RateLimitError,
)


class NcmApiService:
    """网易云API服务，负责获取歌曲、专辑等信息"""

    @staticmethod
    def _map_song_info_to_model(info: Dict[str, Any]) -> SongInfo:
        """
        将API返回的歌曲信息映射到SongInfo模型

        Args:
            info: API返回的歌曲信息
            parsed_url: 解析后的URL

        Returns:
            SongInfo模型实例
        """
        song_model = SongInfo(
            id = str(info["id"]),
            name = str(info["name"]),
            ar = list(info["ar"]),
            al = dict(info["al"]),
            publishTime = int(info["publishTime"]),
            dt = int(info["dt"]),
            commentCount = int(info["commentCount"]),
            shareCount = int(info["shareCount"]),
            lyricUser = dict(info["lyricUser"]),
            transUser = dict(info["transUser"]),
        )

        return song_model
    

    @staticmethod
    async def request(uri: str, data):
        domain = "https://music.163.com"
        url = domain + uri
        response = requests.post(url = url, data = data)
        response.raise_for_status()
        logger.info(f"URL: {url}, status_code: {response.status_code}, ", "网易云解析")
        data = json.loads(response.text)
        return data

    @staticmethod
    async def song_detail(id: str):
        # 歌曲详情
        c = json.dumps([ { "id": id } ])
        data0 = { "c": c }
        ret0 = dict((await NcmApiService.request("/api/v3/song/detail", data0))["songs"][0])

        # 歌曲评论信息
        data1 = {
            "fixliked": True,
            "needupgradedinfo": True,
            "resourceIds": json.dumps([ id ]),
            "resourceType": 4
        }

        ret1 = dict((await NcmApiService.request("/api/resource/commentInfo/list", data1))["data"][0])

        data2 = {
            "cp": "false",
            "id": id,
            "kv": "0",
            "lv": "0",
            "rv": "0",
            "tv": "0",
            "yrv": "0",
            "ytv": "0",
            "yv": "0",
            }

        # 新版歌词
        ret2 = dict((await NcmApiService.request("/api/song/lyric/v1", data2)))
        return { **ret0, **ret1, **ret2 }

    @staticmethod
    async def get_song_info(id: str) -> SongInfo:
        """
        获取歌曲信息

        Args:
            id: 歌曲ID

        Returns:
            SongInfo模型实例

        Raises:
            ResourceNotFoundError: 当视频不存在时
            NcmResponseError: 当API响应错误时
            NcmRequestError: 当网络请求错误时
        """
        logger.debug(f"获取歌曲信息: {id}", "网易云解析")

        try:
            info = (await NcmApiService.song_detail(id))

            if not info or "name" not in info:
                logger.warning(f"歌曲未找到: {id}", "网易云解析")
                raise ResourceNotFoundError(f"歌曲未找到: {id}")

            logger.debug(f"创建SongInfo模型: {id}", "网易云解析")
            song_model = NcmApiService._map_song_info_to_model(info)

            logger.debug(f"歌曲信息获取成功: {song_model.name}", "网易云解析")
            return song_model

        except ResourceNotFoundError:
            raise ResourceNotFoundError(
                f"歌曲未找到: {id}", context={"id": id}
            )

        except Exception as e:
            logger.error(f"获取歌曲信息失败 ({id}): {e}", "网易云解析")
            raise NcmResponseError(
                f"获取歌曲信息意外错误 ({id}): {e}",
                cause=e,
                context={"id": id},
            )