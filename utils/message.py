import base64
from pathlib import Path
import time
from typing import Optional

import aiofiles

import jinja2
from nonebot_plugin_alconna import Image, Text, UniMsg

from zhenxun.services.log import logger

from ..model import ArtistInfo, PlaylistInfo, SongInfo, AlbumInfo, UserInfo
from ..config import base_config, IMAGE_CACHE_DIR

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
FONT_FILE = TEMPLATE_DIR / "vanfont.ttf"
FONT_BASE64_CONTENT = ""
try:
    if FONT_FILE.exists():
        with open(FONT_FILE, "rb") as f:
            font_bytes = f.read()
        FONT_BASE64_CONTENT = base64.b64encode(font_bytes).decode()
        logger.debug("成功加载并编码 vanfont.ttf")
    else:
        logger.error(f"图标字体文件未找到: {FONT_FILE}")
except Exception as e:
    logger.error(f"加载或编码 vanfont.ttf 时出错: {e}")
template_loader = jinja2.FileSystemLoader(str(TEMPLATE_DIR))
template_env = jinja2.Environment(loader=template_loader, enable_async=True)


class ImageHelper:
    """图片处理辅助类"""

    @staticmethod
    async def download_image(url: str, save_path: Path) -> bool:
        """下载图片"""
        from .file_utils import download_file

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Referer": "https://www.bilibili.com",
            }
            return await download_file(url, save_path, headers=headers, timeout=30)
        except Exception as e:
            logger.error(f"下载图片时出错 {url}: {e}")
            return False

    @staticmethod
    async def get_image_as_base64(path: Path) -> Optional[str]:
        """转换图片为Base64"""
        if not (path.exists() and path.stat().st_size > 0):
            return None

        try:
            async with aiofiles.open(path, "rb") as f:
                img_bytes = await f.read()
            img_base64 = base64.b64encode(img_bytes).decode()
            img_format = path.suffix.lstrip(".") or "jpeg"
            return f"data:image/{img_format};base64,{img_base64}"
        except Exception as e:
            logger.error(f"读取或编码图片失败: {path}", e=e)
            return None


SONGCOUNTLIMIT = 10          # 限制打印的歌曲数量
COMMENTCOUNTLIMIT = 3        # 限制打印的评论数量
COMMENTTEXTCOUNTLIMIT = 40   # 限制打印的评论字数

class MessageBuilder:
    """消息构建器"""
    @staticmethod
    def truncate_with_ellipsis(text, max_length):
        """限制文本长度"""
        return text[:max_length] + "..." if len(text) > max_length else text
    
    @staticmethod
    def convertTimeToTag(milliseconds: float, fixed: int = 3, with_brackets: bool = True) -> str:
        """将毫秒时长转换为 mm:ss.ms 格式"""
        if milliseconds is None:
            return ""
        # 计算总秒数（毫秒转秒）
        total_seconds = milliseconds / 1000
        # 分离分钟、秒和毫秒部分
        minutes = int(total_seconds // 60)
        seconds = int(total_seconds % 60)
        milliseconds_part = int(round((total_seconds - int(total_seconds)) * 10**fixed))
        # 格式化各部分（补零）
        mm = f"{minutes:02d}"
        ss = f"{seconds:02d}"
        ms = f"{milliseconds_part:0{fixed}d}"[:fixed]
        
        formatted_time = f"{mm}:{ss}.{ms}"
        return f"[{formatted_time}]" if with_brackets else formatted_time

    @staticmethod
    def get_artist_names(artists):
        names = []
        for artist in artists:
            if 'name' in artist:
                names.append(artist['name'])
        
        return " / ".join(names) if names else ""
    
    @staticmethod
    def get_hotComments_text(hotComments: list):
        """构建热门评论消息"""
        result = "\n"
        result += f"热门评论:\n"
        for idx, hotComment in enumerate(hotComments[:COMMENTCOUNTLIMIT], 1):
            hotComment_info = "{nickname}: {richContent}\n".format(idx = idx,
                                                                   nickname = str(dict(hotComment.get("user", {})).get("nickname", "")),
                                                                   richContent = MessageBuilder.truncate_with_ellipsis(str(hotComment.get("content", "")), COMMENTTEXTCOUNTLIMIT),
                                                                   )
            result += hotComment_info
        return result
    
    @staticmethod
    def get_songs_text(songs: list):
        """构建歌曲列表消息"""
        result = "\n"
        for idx, song in enumerate(songs[:SONGCOUNTLIMIT], 1):
            # 显示歌曲翻译、别名
            alia = list(song.get("tns", {})) + list(song.get("alia", {}))
            alia_text = f"({' / '.join(alia)})" if alia else ""
            song_info = "{idx}. 《{name}》{alia_text} - {artist}\n".format(idx = idx,
                                                            name = song['name'],
                                                            alia_text = alia_text,
                                                            artist = MessageBuilder.get_artist_names(list(song['ar']))
                                                            )
            result += song_info
        result += ("...\n" if len(songs) > SONGCOUNTLIMIT else "")
        return result

    @staticmethod
    def toLocaleDateString(timestamp_ms):
        """将毫秒时间戳格式化为 yyyy-MM-dd hh:mm:ss.zzz"""
        seconds = timestamp_ms // 1000
        milliseconds = timestamp_ms % 1000
        time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(seconds))
        return f"{time_str}.{milliseconds:03d}"

    @staticmethod
    async def build_song_message(info: SongInfo) -> UniMsg:
        """构建歌曲信息消息"""
        segments = []

        picUrl = info.al["picUrl"]
        if base_config.get("SEND_VIDEO_PIC", True) and picUrl:
            file_name = f"ncm_song_cover_{info.id}.jpg"
            cover_path = IMAGE_CACHE_DIR / file_name
            if await ImageHelper.download_image(f"{picUrl}", cover_path):
                segments.append(Image(path=cover_path))

        text_content = (
            f"歌名: {info.name}\n"
            f"别名: {' / '.join(info.tns + info.alia)}\n"
            f"专辑: {info.al['name']}\n"
            f"时长: {MessageBuilder.convertTimeToTag(info.dt, 3, False)}\n"
            f"发布时间: {MessageBuilder.toLocaleDateString(info.publishTime)}\n"
            f"歌手: {MessageBuilder.get_artist_names(info.ar)}\n"
            # f"id: {info.id}\n"

            f"评论数: {info.commentCount} | 分享数: {info.shareCount}\n"
        )
        lyricNickname = f"歌词上传者: {info.lyricUser.get('nickname', '')}"
        lyricUptime = f"过审时间: {MessageBuilder.toLocaleDateString(info.lyricUser.get('uptime', 0)) if info.lyricUser.get('uptime') else ''}"
        transNickname = f"翻译上传者: {info.transUser.get('nickname', '')}"
        transUptime = f"过审时间: {MessageBuilder.toLocaleDateString(info.transUser.get('uptime', 0)) if info.transUser.get('uptime') else ''}"

        if True:
            text_content += f"{lyricNickname} | {transNickname}\n"
        else:
            text_content += f"{lyricNickname} | {lyricUptime}\n"
            text_content += f"{transNickname} | {transUptime}\n"

        # 热门评论
        # text_content += MessageBuilder.get_hotComments_text(info.hotComments)

        text_content += f"https://music.163.com/#/song?id={info.id}"
        segments.append(Text(text_content))

        return UniMsg(segments)

    @staticmethod
    async def build_album_message(info: AlbumInfo) -> UniMsg:
        """构建专辑信息消息"""
        segments = []

        picUrl = info.picUrl
        if base_config.get("SEND_VIDEO_PIC", True) and picUrl:
            file_name = f"ncm_album_cover_{info.id}.jpg"
            cover_path = IMAGE_CACHE_DIR / file_name
            if await ImageHelper.download_image(f"{picUrl}", cover_path):
                segments.append(Image(path=cover_path))

        text_content = (
            f"专辑名: {info.name}\n"
            f"发布时间: {MessageBuilder.toLocaleDateString(info.publishTime)}\n"
            f"歌手: {MessageBuilder.get_artist_names(info.artists)}\n"
            f"简介: {info.description}\n"
            # f"id: {info.id}\n"

            f"评论数: {info.commentCount} | 分享数: {info.shareCount}\n"
        )

        text_content += "\n"
        text_content += f"共{len(info.songs)}首曲子\n"
        text_content += MessageBuilder.get_songs_text(songs = info.songs)

        # 热门评论
        # text_content += MessageBuilder.get_hotComments_text(info.hotComments)

        text_content += f"https://music.163.com/#/album?id={info.id}"
        segments.append(Text(text_content))

        return UniMsg(segments)

    @staticmethod
    async def build_user_message(info: UserInfo) -> UniMsg:
        """构建用户信息消息"""
        segments = []

        picUrl = info.avatarUrl
        if base_config.get("SEND_VIDEO_PIC", True) and picUrl:
            file_name = f"ncm_user_cover_{info.id}.jpg"
            cover_path = IMAGE_CACHE_DIR / file_name
            if await ImageHelper.download_image(f"{picUrl}", cover_path):
                segments.append(Image(path=cover_path))

        text_content = (
            f"用户名: {info.name}\n"
            f"出生日期: {MessageBuilder.toLocaleDateString(info.birthday) if info.birthday > 0 else ''} | 注册时间: {MessageBuilder.toLocaleDateString(info.createTime) if info.createTime > 0 else ''}\n"
            f"签名: {info.signature}\n"
            # f"id: {info.id}\n"

            f"动态数量: {info.eventCount} | 歌单数量: {info.playlistCount}\n"
            f"关注: {info.follows} | 粉丝: {info.followeds}\n"

            f"https://music.163.com/#/user/home?id={info.id}"
        )
        segments.append(Text(text_content))

        return UniMsg(segments)

    @staticmethod
    async def build_playlist_message(info: PlaylistInfo) -> UniMsg:
        """构建歌单信息消息"""
        segments = []

        picUrl = info.coverImgUrl
        if base_config.get("SEND_VIDEO_PIC", True) and picUrl:
            file_name = f"ncm_playlist_cover_{info.id}.jpg"
            cover_path = IMAGE_CACHE_DIR / file_name
            if await ImageHelper.download_image(f"{picUrl}", cover_path):
                segments.append(Image(path=cover_path))

        text_content = (
            f"歌单名: {info.name}\n"
            f"创建者: {info.creator['nickname']}\n"
            f"创建时间: {MessageBuilder.toLocaleDateString(info.createTime)}\n"
            f"简介: {info.description}\n"
            f"播放量: {info.playCount} | 收藏量: {info.subscribedCount} | 评论数: {info.commentCount} | 分享数: {info.shareCount}\n"
            f"标签: {' / '.join(info.tags)}\n"
            # f"id: {info.id}\n"
        )

        text_content += "\n"
        text_content += f"共{len(info.trackIds)}首曲子\n" # 这里用的是trackIds
        text_content += MessageBuilder.get_songs_text(songs = info.tracks)

        # 热门评论
        # text_content += MessageBuilder.get_hotComments_text(info.hotComments)

        text_content += f"https://music.163.com/#/playlist?id={info.id}"
        segments.append(Text(text_content))

        return UniMsg(segments)

    @staticmethod
    async def build_artist_message(info: ArtistInfo) -> UniMsg:
        """构建歌手信息消息"""
        segments = []

        picUrl = info.picUrl
        if base_config.get("SEND_VIDEO_PIC", True) and picUrl:
            file_name = f"ncm_artist_cover_{info.id}.jpg"
            cover_path = IMAGE_CACHE_DIR / file_name
            if await ImageHelper.download_image(f"{picUrl}", cover_path):
                segments.append(Image(path=cover_path))

        text_content = (
            f"歌手名: {info.name}\n"
            f"别名: {' / '.join(info.alias)}\n"
            f"详情: {info.briefDesc}\n"
            f"歌曲数: {info.musicSize} | 专辑数: {info.albumSize} | MV数: {info.mvSize}\n"
            # f"id: {info.id}\n"
        )

        text_content += "\n"
        text_content += f"热门歌曲:\n"
        text_content += MessageBuilder.get_songs_text(songs = info.hotSongs)

        text_content += f"https://music.163.com/#/artist?id={info.id}"
        segments.append(Text(text_content))

        return UniMsg(segments)