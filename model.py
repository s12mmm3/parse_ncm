from pydantic import BaseModel
from typing import Optional, Dict, Any

class SongInfo(BaseModel):
    id: str            # id
    name: str          # 歌名
    ar: list           # 歌手
    al: dict           # 专辑
    publishTime: int   # 发布时间
    dt: int            # 时长
    commentCount: int  # 评论数
    shareCount: int    # 分享数
    lyricUser: dict    # 歌词上传者
    transUser: dict    # 翻译上传者
    tns: list          # 翻译名
    alia: list         # 副标题
    hotComments: list  # 热门评论

class AlbumInfo(BaseModel):
    id: str            # id
    name: str          # 专辑名
    artists: list      # 歌手
    picUrl: str        # 封面
    description: str   # 简介
    publishTime: int   # 发布时间
    commentCount: int  # 评论数
    shareCount: int    # 分享数
    songs: list        # 歌曲列表信息
    hotComments: list  # 热门评论

class UserInfo(BaseModel):
    id: str            # id
    name: str          # 用户名
    createTime: int    # 注册时间
    avatarUrl: str     # 头像
    birthday: int      # 出生日期
    signature: str     # 签名
    followeds: int     # 粉丝
    follows: int       # 关注
    eventCount: int    # 动态数量
    playlistCount: int # 歌单数量

class PlaylistInfo(BaseModel):
    id: str            # id
    name: str          # 歌单名
    createTime: int    # 创建时间
    coverImgUrl: str   # 封面
    playCount: int     # 播放量
    subscribedCount: int # 收藏量
    description: str   # 简介
    tags: list         # 标签
    commentCount: int  # 评论数
    shareCount: int    # 分享数
    creator: dict      # 创建者
    tracks: list       # 歌曲列表信息（不全）
    trackIds: list     # 歌曲id列表
    hotComments: list  # 热门评论

class ArtistInfo(BaseModel):
    id: str            # id
    name: str          # 歌手名
    picUrl: str        # 头像
    alias: list        # 别名
    briefDesc: str     # 详情
    musicSize: int     # 歌曲数
    albumSize: int     # 专辑数
    mvSize: int        # MV数
    hotSongs: list     # 热门歌曲
