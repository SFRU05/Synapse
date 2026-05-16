from __future__ import annotations
import asyncio
import yt_dlp

YDL_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
}


def _fetch_recommendations(query: str, limit: int = 5) -> list[dict] | None:
    """YouTube에서 비슷한 곡 검색 (동기 함수 — executor에서 실행)"""
    with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
        try:
            # 검색어에 기반해 유사 곡 찾기
            search_query = f"ytsearch{limit}:{query} similar"
            info = ydl.extract_info(search_query, download=False)

            if info and "entries" in info:
                results = []
                for entry in info["entries"]:
                    if entry:
                        results.append({
                            "title": entry.get("title", "알 수 없음"),
                            "url": entry["url"],
                            "webpage_url": entry.get("webpage_url", ""),
                            "thumbnail": entry.get("thumbnail", ""),
                            "duration": entry.get("duration", 0),
                            "uploader": entry.get("uploader", "알 수 없음"),
                        })
                return results if results else None
        except Exception as e:
            print(f"추천곡 검색 오류: {e}")
    return None


async def fetch_recommendations(query: str, limit: int = 5) -> list[dict] | None:
    """비동기 래퍼"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_recommendations, query, limit)


def _extract_song_info(title: str) -> str:
    """제목에서 아티스트/장르 정보 추출하여 검색어 정제"""
    # 예: "곡명 - 아티스트" 형태에서 아티스트 추출
    if " - " in title:
        parts = title.split(" - ")
        return parts[-1].strip()  # 아티스트명
    return title


async def get_similar_tracks(track_title: str, limit: int = 5) -> list[dict] | None:
    """현재 곡과 비슷한 곡 추천"""
    # 검색어 정제 (아티스트명 기반)
    search_query = _extract_song_info(track_title)

    # 비슷한 곡 검색
    recommendations = await fetch_recommendations(search_query, limit)

    return recommendations


async def get_artist_tracks(artist_name: str, limit: int = 5, exclude_titles: list[str] | None = None) -> list[
                                                                                                              dict] | None:
    """특정 작곡가의 다른 곡 추천 (이미 재생한 곡 제외)"""
    if exclude_titles is None:
        exclude_titles = []

    # 작곡가명으로 직접 검색 (similar 키워드 없음)
    recommendations = await fetch_recommendations(artist_name, limit=20)  # 더 많이 가져오기

    if not recommendations:
        return None

    # 제외 목록에 없는 곡만 필터링
    filtered = [rec for rec in recommendations if rec["title"] not in exclude_titles]

    # 필요한 개수만 반환
    return filtered[:limit] if filtered else None