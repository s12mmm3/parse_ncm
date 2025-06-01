import asyncio
import json
from typing import Dict, Any

import aiohttp
import requests

from zhenxun.services.log import logger

from ..model import (
    SongInfo, AlbumInfo,
)
from ..utils.exceptions import (
    NcmResponseError,
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
        """将API返回的歌曲信息映射到SongInfo模型"""
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
    def _map_album_info_to_model(info: Dict[str, Any]) -> AlbumInfo:
        """将API返回的专辑信息映射到AlbumInfo模型"""
        album = dict(info["album"])
        album_model = AlbumInfo(
            id = str(album["id"]),
            name = str(album["name"]),
            artists = list(album["artists"]),
            picUrl = str(album["picUrl"]),
            description = str(album["description"]),
            publishTime = int(album["publishTime"]),

            commentCount = int(info["commentCount"]),
            shareCount = int(info["shareCount"]),
            songs = list(info["songs"]),
        )

        return album_model
    

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
            "resourceType": 3
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
    async def album_detail(id: str):
        # 专辑详情
        data0 = { }
        ret0 = dict((await NcmApiService.request(f"/api/v1/album/{id}", data0)))
        # 专辑评论信息
        data1 = {
            "fixliked": True,
            "needupgradedinfo": True,
            "resourceIds": json.dumps([ id ]),
            "resourceType": 3
        }

        ret1 = dict((await NcmApiService.request("/api/resource/commentInfo/list", data1))["data"][0])
        return { **ret0, **ret1, }

    @staticmethod
    async def get_song_info(id: str) -> SongInfo:
        """获取歌曲信息"""
        logger.debug(f"获取歌曲信息: {id}", "网易云解析")

        try:
            info = (await NcmApiService.song_detail(id))

            logger.debug(f"创建SongInfo模型: {id}", "网易云解析")
            model = NcmApiService._map_song_info_to_model(info)

            logger.debug(f"歌曲信息获取成功: {model.name}", "网易云解析")
            return model

        except Exception as e:
            logger.error(f"获取歌曲信息失败 ({id}): {e}", "网易云解析")
            raise NcmResponseError(
                f"获取歌曲信息意外错误 ({id}): {e}",
                cause=e,
                context={"id": id},
            )

    @staticmethod
    async def get_album_info(id: str) -> AlbumInfo:
        """获取专辑信息"""
        logger.debug(f"获取专辑信息: {id}", "网易云解析")

        try:
            info = (await NcmApiService.album_detail(id))

            logger.debug(f"创建AlbumInfo模型: {id}", "网易云解析")
            model = NcmApiService._map_album_info_to_model(info)

            logger.debug(f"专辑信息获取成功: {model.name}", "网易云解析")
            return model

        except Exception as e:
            logger.error(f"获取专辑信息失败 ({id}): {e}", "网易云解析")
            raise NcmResponseError(
                f"获取专辑信息意外错误 ({id}): {e}",
                cause=e,
                context={"id": id},
            )