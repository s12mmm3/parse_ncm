import asyncio
import json
from typing import Awaitable, Callable, Dict, Any

import aiohttp
import requests

from zhenxun.services.log import logger

from ..model import (
    ArtistInfo, MVInfo, PlaylistInfo, SongInfo, AlbumInfo, UserInfo,
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
    async def resolve_short_url(url: str) -> str:
        """解析短链接"""
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        response = requests.get(url = url)
        response.raise_for_status()
        resolved_url = str(response.url)

        logger.debug(f"短链接 {url} 解析为 {resolved_url}", "网易云解析")

        return resolved_url

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
            lyricUser = dict(info.get("lyricUser", {})),
            transUser = dict(info.get("transUser", {})),
            tns = list(info.get("tns", {})),
            alia = list(info.get("alia", {})),
            hotComments = list(info.get("hotComments", {})),
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
            hotComments = list(info.get("hotComments", {})),
        )

        return album_model

    @staticmethod
    def _map_user_info_to_model(info: Dict[str, Any]) -> UserInfo:
        """将API返回的用户信息映射到UserInfo模型"""
        profile = dict(info["profile"])
        user_model = UserInfo(
            id = str(profile["userId"]),
            name = str(profile["nickname"]),
            createTime = int(profile.get("createTime", 0)),
            avatarUrl = str(profile["avatarUrl"]),
            birthday = int(profile.get("birthday", 0)),
            signature = str(profile["signature"]),
            followeds = int(profile["followeds"]),
            follows = int(profile["follows"]),
            eventCount = int(profile["eventCount"]),
            playlistCount = int(profile["playlistCount"]),
        )

        return user_model

    @staticmethod
    def _map_playlist_info_to_model(info: Dict[str, Any]) -> PlaylistInfo:
        """将API返回的歌单信息映射到PlaylistInfo模型"""
        playlist = dict(info["playlist"])
        playlist_model = PlaylistInfo(
            id = str(playlist["id"]),
            name = str(playlist["name"]),
            createTime = int(playlist["createTime"]),
            coverImgUrl = str(playlist["coverImgUrl"]),
            playCount = int(playlist["playCount"]),
            subscribedCount = int(playlist["subscribedCount"]),
            description = str(playlist["description"]),
            tags = list(playlist["tags"]),

            commentCount = int(playlist["commentCount"]),
            shareCount = int(playlist["shareCount"]),
            creator = dict(playlist["creator"]),
            tracks = list(playlist["tracks"]),
            trackIds = list(playlist["trackIds"]),
            hotComments = list(info.get("hotComments", {})),
        )

        return playlist_model

    @staticmethod
    def _map_artist_info_to_model(info: Dict[str, Any]) -> ArtistInfo:
        """将API返回的歌手信息映射到ArtistInfo模型"""
        artist = dict(info["artist"])
        artist_model = ArtistInfo(
            id = str(artist["id"]),
            name = str(artist["name"]),
            picUrl = str(artist["picUrl"]),
            alias = list(artist["alias"]),
            briefDesc = str(artist["briefDesc"]),
            musicSize = int(artist["musicSize"]),
            albumSize = int(artist["albumSize"]),
            mvSize = int(artist["mvSize"]),
            hotSongs = list(info["hotSongs"]),
        )

        return artist_model

    @staticmethod
    def _map_mv_info_to_model(info: Dict[str, Any]) -> MVInfo:
        """将API返回的mv信息映射到MVInfo模型"""
        data = dict(info["data"])
        mv_model = MVInfo(
            id = str(data["id"]),
            name = str(data["name"]),
            desc = str(data["desc"]),
            cover = str(data["cover"]),
            artists = list(data["artists"]),
            duration = int(data["duration"]),
            publishTime = str(data["publishTime"]),
            playCount = int(data["playCount"]),
            subCount = int(data["subCount"]),
            commentCount = int(data["commentCount"]),
            shareCount = int(data["shareCount"]),
            hotComments = list(info["hotComments"]),
        )

        return mv_model
    

    @staticmethod
    async def request(uri: str, data):
        domain = "https://music.163.com"
        url = domain + uri
        realIp = "58.100.87.193"
        response = requests.post(url = url, data = data, headers = {
            "X-Real-IP": realIp,
            "X-Forwarded-For": realIp,
        })
        response.raise_for_status()
        logger.info(f"URL: {url}, status_code: {response.status_code}, ", "网易云解析")
        data = json.loads(response.text)
        return data
    
    @staticmethod
    async def get_commentInfo(id: str, resourceType: int):
        # 简略评论信息
        data = {
            "fixliked": True,
            "needupgradedinfo": True,
            "resourceIds": json.dumps([ id ]),
            "resourceType": resourceType
        }
        return dict((await NcmApiService.request("/api/resource/commentInfo/list", data))["data"][0])
    
    @staticmethod
    async def comment_event(threadId: str):
        # 具体评论信息
        data = {
            "limit": 60,
            }
        return dict((await NcmApiService.request(f"/api/v1/resource/comments/{threadId}", data)))

    @staticmethod
    async def song_detail(id: str):
        # 歌曲详情
        c = json.dumps([ { "id": id } ])
        data0 = { "c": c }
        ret0 = dict((await NcmApiService.request("/api/v3/song/detail", data0))["songs"][0])

        # 简略评论信息
        ret1 = await NcmApiService.get_commentInfo(id = id, resourceType = 4)

        # 新版歌词
        data2 = {
            "id": id,
            }
        ret2 = dict((await NcmApiService.request("/api/song/lyric/v1", data2)))
        
        # 具体评论信息
        threadId = ret1.get("threadId", "")
        ret3 = await NcmApiService.comment_event(threadId = threadId)
        return { **ret0, **ret1, **ret2, **ret3, }

    @staticmethod
    async def album_detail(id: str):
        # 专辑详情
        data0 = { }
        ret0 = dict((await NcmApiService.request(f"/api/v1/album/{id}", data0)))

        # 简略评论信息
        ret1 = await NcmApiService.get_commentInfo(id = id, resourceType = 3)

        # 具体评论信息
        threadId = ret1.get("threadId", "")
        ret3 = await NcmApiService.comment_event(threadId = threadId)
        return { **ret0, **ret1, **ret3, }

    @staticmethod
    async def user_detail(id: str):
        # 用户详情
        data0 = { }
        ret0 = dict((await NcmApiService.request(f"/api/v1/user/detail/{id}", data0)))
        return { **ret0, }

    @staticmethod
    async def playlist_detail(id: str):
        # 歌单详情
        data0 = {
            "id": id,
            "n": "100000",
            "s": "8"
        }
        ret0 = dict((await NcmApiService.request(f"/api/v6/playlist/detail", data0)))

        # 简略评论信息
        ret1 = await NcmApiService.get_commentInfo(id = id, resourceType = 0)

        # 具体评论信息
        threadId = ret1.get("threadId", "")
        ret3 = await NcmApiService.comment_event(threadId = threadId)
        return { **ret0, **ret1, **ret3, }

    @staticmethod
    async def artist_detail(id: str):
        # 歌手详情
        data0 = { }
        ret0 = dict((await NcmApiService.request(f"/api/v1/artist/{id}", data0)))
        return { **ret0, }

    @staticmethod
    async def mv_detail(id: str):
        # mv详情
        data0 = {
            "id": id,
            "composeliked": True,
        }
        ret0 = dict((await NcmApiService.request(f"/api/v1/mv/detail", data0)))

        # 简略评论信息
        ret1 = await NcmApiService.get_commentInfo(id = id, resourceType = 5)

        # 具体评论信息
        threadId = ret1.get("threadId", "")
        ret3 = await NcmApiService.comment_event(threadId = threadId)
        return { **ret0, **ret1, **ret3, }


    @staticmethod
    async def get_info(id: str,
                       desc: str,
                       detail_func: Callable[[str], Awaitable[Any]],
                       model_func: Callable[[Dict[str, Any]], Any]) -> Any:
        """获取信息"""
        logger.debug(f"获取{desc}信息: {id}", "网易云解析")
        try:
            info = (await detail_func(id))
            logger.debug(f"创建{type(info)}模型: {id}", "网易云解析")
            model = model_func(info)
            logger.debug(f"{desc}信息获取成功: {getattr(model, 'name', '')}", "网易云解析")
            return model
        except Exception as e:
            logger.error(f"获取{desc}信息失败 ({id}): {e}", "网易云解析")
            raise NcmResponseError(
                f"获取{desc}信息意外错误 ({id}): {e}",
                cause=e,
                context={"id": id},
            )