from typing import Union

from zhenxun.services.log import logger

from ..model import ArtistInfo, SongInfo, AlbumInfo, UserInfo, PlaylistInfo
from ..services.api_service import NcmApiService
from ..services.network_service import NetworkService
from ..utils.exceptions import UrlParseError, UnsupportedUrlError, ShortUrlError
from ..utils.url_parser import ResourceType, UrlParserRegistry


class ParserService:
    """URL解析服务，负责解析网易云各类URL并返回对应的信息模型"""

    @staticmethod
    async def resolve_short_url(url: str) -> str:
        """解析短链接，返回原始URL"""
        original_url = url.strip()

        if "163cn.tv" in original_url:
            logger.debug(f"检测到163cn.tv短链接: {original_url}", "网易云解析")
            try:
                resolved_url = await NetworkService.resolve_short_url(original_url)
                logger.debug(f"短链接解析结果: {resolved_url}", "网易云解析")
                return resolved_url
            except ShortUrlError as e:
                logger.warning(
                    f"短链接解析失败 {original_url}: {e}，将使用原始链接继续尝试解析",
                    "网易云解析",
                )

        return original_url

    @staticmethod
    async def fetch_resource_info(
        resource_type: ResourceType, resource_id: str, parsed_url: str
    ) -> Union[SongInfo, AlbumInfo, UserInfo, PlaylistInfo, ArtistInfo]:
        """根据资源类型和ID获取详细信息"""
        logger.debug(
            f"获取资源信息: 类型={resource_type.name}, ID={resource_id}",
            "网易云解析",
        )

        if resource_type == ResourceType.SONG:
            return await NcmApiService.get_song_info(
                id=resource_id
            )
        elif resource_type == ResourceType.ALBUM:
            return await NcmApiService.get_album_info(
                id=resource_id
            )
        elif resource_type == ResourceType.USER:
            return await NcmApiService.get_user_info(
                id=resource_id
            )
        elif resource_type == ResourceType.PLAYLIST:
            return await NcmApiService.get_playlist_info(
                id=resource_id
            )
        elif resource_type == ResourceType.ARTIST:
            return await NcmApiService.get_artist_info(
                id=resource_id
            )
        else:
            raise UnsupportedUrlError(f"不支持的资源类型: {resource_type}")

    @classmethod
    async def parse(
        cls, url: str
    ) -> Union[SongInfo, AlbumInfo, UserInfo, PlaylistInfo, ArtistInfo]:
        """解析网易云 URL，返回相应的信息模型"""
        original_url = url.strip()
        logger.debug(f"开始解析URL: {original_url}", "网易云解析")

        final_url = await cls.resolve_short_url(original_url)

        try:
            resource_type, resource_id = UrlParserRegistry.parse(final_url)
            logger.debug(
                f"从URL提取资源信息: 类型={resource_type.name}, ID={resource_id}",
                "网易云解析",
            )
        except (UrlParseError, UnsupportedUrlError):
            if final_url != original_url:
                logger.debug(
                    f"最终URL解析失败，尝试解析原始URL: {original_url}", "网易云解析"
                )
                try:
                    resource_type, resource_id = UrlParserRegistry.parse(original_url)
                    logger.debug(
                        f"从原始URL提取资源信息: 类型={resource_type.name}, ID={resource_id}",
                        "网易云解析",
                    )
                except (UrlParseError, UnsupportedUrlError) as e:
                    logger.warning(
                        f"无法从URL确定资源类型或ID: {original_url} (解析为: {final_url})",
                        "网易云解析",
                    )
                    raise UrlParseError(
                        f"无法从URL确定资源类型或ID: {original_url} (解析为: {final_url})",
                        cause=e,
                        context={"original_url": original_url, "final_url": final_url},
                    )
            else:
                logger.warning(f"无法解析URL: {original_url}", "网易云解析")
                raise

        if resource_type == ResourceType.SHORT_URL:
            resolved_url = await cls.resolve_short_url(original_url)
            if resolved_url == original_url:
                raise ShortUrlError(
                    f"无法解析短链接: {original_url}", context={"url": original_url}
                )

            logger.debug(f"递归解析短链接解析结果: {resolved_url}", "网易云解析")
            return await cls.parse(resolved_url)

        parsed_url = final_url if final_url != original_url else original_url

        return await cls.fetch_resource_info(
            resource_type=resource_type, resource_id=resource_id, parsed_url=parsed_url
        )
