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
