from __future__ import annotations

import asyncio
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands


class TMDBSelectionView(discord.ui.View):
    def __init__(
        self,
        cog: "Animation",
        results: list[dict[str, Any]],
    ):
        super().__init__(timeout=120)

        self.cog = cog
        self.results = results
        self.message: discord.Message | None = None

        options = []

        for index, item in enumerate(results[:25]):
            title = cog._tmdb_title(item)
            year = str(item.get("first_air_date") or "")[:4]
            score = item.get("vote_average")

            description_parts = []

            if year:
                description_parts.append(year)

            if score:
                description_parts.append(
                    f"평점 {float(score):.1f}"
                )

            description = " · ".join(description_parts)

            if not description:
                description = "상세 정보 없음"

            options.append(
                discord.SelectOption(
                    label=title[:100],
                    description=description[:100],
                    value=str(index),
                )
            )

        self.select = discord.ui.Select(
            placeholder="상세 정보를 볼 작품을 선택하세요.",
            min_values=1,
            max_values=1,
            options=options,
        )

        self.select.callback = self._select_callback
        self.add_item(self.select)

    async def _select_callback(
        self,
        interaction: discord.Interaction,
    ):
        selected_index = int(self.select.values[0])
        selected_item = self.results[selected_index]
        tv_id = selected_item.get("id")

        if not tv_id:
            await interaction.response.send_message(
                "⚠️ 선택한 작품의 ID를 찾지 못했어요.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        try:
            detail = await self.cog._tmdb_get_tv_details(
                int(tv_id)
            )

            embed = self.cog._create_tmdb_detail_embed(
                detail
            )

            if interaction.message:
                await interaction.message.edit(
                    embed=embed,
                    view=None,
                )

            self.stop()

        except RuntimeError as exc:
            await interaction.followup.send(
                f"⚠️ {exc}",
                ephemeral=True,
            )

        except Exception as exc:
            print(
                "[TMDB 선택 조회 오류] "
                f"{type(exc).__name__}: {exc}"
            )

            await interaction.followup.send(
                "⚠️ 선택한 작품의 상세 정보를 불러오지 못했어요.",
                ephemeral=True,
            )

    async def on_timeout(self):
        if self.message is None:
            return

        try:
            await self.message.edit(view=None)
        except discord.HTTPException:
            pass


class Animation(commands.Cog):
    ANISSIA_BASE_URL = "https://api.anissia.net/anime"

    TMDB_BASE_URL = "https://api.themoviedb.org/3"
    TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"

    TMDB_ATTRIBUTION = (
        "This product uses the TMDB API but is not "
        "endorsed or certified by TMDB."
    )

    WEEK_LABELS = {
        "0": "일요일",
        "1": "월요일",
        "2": "화요일",
        "3": "수요일",
        "4": "목요일",
        "5": "금요일",
        "6": "토요일",
        "7": "기타",
    }

    STATUS_LABELS = {
        "ON": "방영/등록 중",
        "OFF": "결방",
    }

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.tmdb_api_token = os.getenv("TMDB_API_TOKEN")

        self._schedule_cache: dict[
            str,
            list[dict[str, Any]],
        ] = {}

        self._schedule_cache_updated_at: datetime | None = None
        self._schedule_cache_ttl = timedelta(minutes=5)

        self._tmdb_cache: dict[
            str,
            tuple[datetime, list[dict[str, Any]]],
        ] = {}

        self._tmdb_cache_ttl = timedelta(minutes=10)

    @staticmethod
    def _escape(value: Any) -> str:
        return discord.utils.escape_markdown(str(value))

    @staticmethod
    def _safe_text(
        value: Any,
        default: str = "미등록",
    ) -> str:
        if value is None:
            return default

        value = str(value).strip()
        return value or default

    @staticmethod
    def _normalize_text(value: str | None) -> str:
        if not value:
            return ""

        value = str(value).casefold()
        value = re.sub(r"\s+", "", value)
        value = re.sub(
            r"[^\w가-힣ぁ-んァ-ン一-龥]",
            "",
            value,
        )

        return value

    @staticmethod
    def _format_anissia_date(value: Any) -> str:
        value = Animation._safe_text(value)

        if value == "미등록":
            return value

        value = value.strip()

        if value.endswith("-99-99"):
            value = value[:-6]
        elif value.endswith("-99"):
            value = value[:-3]

        return value.replace("-", ".")

    @staticmethod
    def _format_anissia_time(value: Any) -> str:
        value = Animation._safe_text(value)

        if value == "미등록":
            return value

        value = value.strip()

        if value.endswith("-99-99"):
            value = value[:-6]
        elif value.endswith("-99"):
            value = value[:-3]

        return value

    @staticmethod
    def _format_genres(value: Any) -> str:
        if not value:
            return "미등록"

        genres = [
            genre.strip()
            for genre in str(value).split(",")
            if genre.strip()
        ]

        return ", ".join(genres) or "미등록"

    @staticmethod
    def _tmdb_title(item: dict[str, Any]) -> str:
        return str(
            item.get("name")
            or item.get("original_name")
            or "제목 미상"
        )

    @staticmethod
    def _anissia_request(url: str) -> Any:
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json, text/plain, */*",
                "Accept-Encoding": "identity",
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/120.0 Safari/537.36"
                ),
            },
            method="GET",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=20,
            ) as response:
                raw_data = response.read()

                text = raw_data.decode(
                    "utf-8-sig",
                    errors="replace",
                ).strip()

                print(
                    "[애니시아 응답] "
                    f"status={response.status}, "
                    f"url={url}, "
                    f"preview={text[:300]!r}"
                )

                if not text:
                    raise RuntimeError(
                        "애니시아에서 빈 응답을 받았어요."
                    )

                try:
                    return json.loads(text)

                except json.JSONDecodeError as exc:
                    raise RuntimeError(
                        "애니시아가 JSON이 아닌 응답을 반환했어요."
                    ) from exc

        except urllib.error.HTTPError as exc:
            try:
                error_body = exc.read().decode(
                    "utf-8",
                    errors="replace",
                )[:500]
            except Exception:
                error_body = ""

            print(
                "[애니시아 HTTP 오류] "
                f"status={exc.code}, "
                f"url={url}, "
                f"body={error_body!r}"
            )

            raise RuntimeError(
                f"애니시아 API 오류(HTTP {exc.code})"
            ) from exc

        except urllib.error.URLError as exc:
            print(
                "[애니시아 연결 오류] "
                f"url={url}, "
                f"reason={exc.reason!r}"
            )

            raise RuntimeError(
                "애니시아 서버에 연결할 수 없어요. "
                "잠시 후 다시 시도해 주세요."
            ) from exc

        except TimeoutError as exc:
            raise RuntimeError(
                "애니시아 서버 응답이 늦어요. "
                "잠시 후 다시 시도해 주세요."
            ) from exc

    @staticmethod
    def _extract_list_response(
        data: Any,
    ) -> list[dict[str, Any]] | None:
        if isinstance(data, list):
            return [
                item
                for item in data
                if isinstance(item, dict)
            ]

        if not isinstance(data, dict):
            return None

        for key in (
            "data",
            "items",
            "results",
            "result",
            "content",
            "list",
            "anime",
        ):
            nested = data.get(key)

            if isinstance(nested, list):
                return [
                    item
                    for item in nested
                    if isinstance(item, dict)
                ]

        return None

    @staticmethod
    def _extract_error_message(data: Any) -> str | None:
        if not isinstance(data, dict):
            return None

        for key in (
            "message",
            "error",
            "detail",
            "errorMessage",
            "error_description",
        ):
            value = data.get(key)

            if value:
                return str(value)

        return None

    async def _fetch_schedule(
        self,
        week: str,
    ) -> list[dict[str, Any]]:
        url = f"{self.ANISSIA_BASE_URL}/schedule/{week}"

        data = await asyncio.to_thread(
            self._anissia_request,
            url,
        )

        items = self._extract_list_response(data)

        if items is not None:
            return items

        error_message = self._extract_error_message(data)

        if error_message:
            raise RuntimeError(
                f"애니시아 API 오류: {error_message}"
            )

        print(
            "[애니시아 응답 형식 오류] "
            f"week={week}, "
            f"type={type(data).__name__}, "
            f"data={repr(data)[:500]}"
        )

        raise RuntimeError(
            "애니시아에서 예상치 못한 응답을 받았어요."
        )

    async def _fetch_all_schedules(
        self,
    ) -> dict[str, list[dict[str, Any]]]:
        now = datetime.now()

        cache_is_valid = (
            bool(self._schedule_cache)
            and self._schedule_cache_updated_at is not None
            and now - self._schedule_cache_updated_at
            < self._schedule_cache_ttl
        )

        if cache_is_valid:
            return self._schedule_cache

        weeks = [str(index) for index in range(8)]

        results = await asyncio.gather(
            *(
                self._fetch_schedule(week)
                for week in weeks
            ),
            return_exceptions=True,
        )

        schedules: dict[
            str,
            list[dict[str, Any]],
        ] = {}

        failed_weeks: list[str] = []

        for week, result in zip(weeks, results):
            if isinstance(result, Exception):
                failed_weeks.append(week)

                print(
                    "[애니시아 편성표 건너뜀] "
                    f"week={week}, "
                    f"error={type(result).__name__}: {result}"
                )

                continue

            schedules[week] = result

        if not schedules:
            raise RuntimeError(
                "애니시아 편성표를 불러오지 못했어요. "
                "잠시 후 다시 시도해 주세요."
            )

        self._schedule_cache = schedules
        self._schedule_cache_updated_at = now

        if failed_weeks:
            print(
                "[애니시아 일부 요청 실패] "
                f"week={', '.join(failed_weeks)}"
            )

        return schedules

    def _tmdb_request(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.tmdb_api_token:
            raise RuntimeError(
                "환경 변수가 설정되지 않았어요."
            )

        query_string = urllib.parse.urlencode(params or {})
        url = f"{self.TMDB_BASE_URL}{path}"

        if query_string:
            url = f"{url}?{query_string}"

        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": (
                    f"Bearer {self.tmdb_api_token}"
                ),
                "User-Agent": "SynapseDiscordBot/1.0",
            },
            method="GET",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=20,
            ) as response:
                raw_data = response.read()

                text = raw_data.decode(
                    "utf-8-sig",
                    errors="replace",
                ).strip()

                if not text:
                    raise RuntimeError(
                        "TMDB에서 빈 응답을 받았어요."
                    )

                try:
                    data = json.loads(text)

                except json.JSONDecodeError as exc:
                    raise RuntimeError(
                        "TMDB가 JSON이 아닌 응답을 반환했어요."
                    ) from exc

        except urllib.error.HTTPError as exc:
            try:
                error_body = exc.read().decode(
                    "utf-8",
                    errors="replace",
                )[:500]
            except Exception:
                error_body = ""

            print(
                "[TMDB HTTP 오류] "
                f"status={exc.code}, "
                f"path={path}, "
                f"body={error_body!r}"
            )

            if exc.code in (401, 403):
                raise RuntimeError(
                    "TMDB API 토큰이 올바르지 않거나 "
                    "접근 권한이 없어요."
                ) from exc

            if exc.code == 429:
                raise RuntimeError(
                    "TMDB 검색 요청이 많아요. "
                    "잠시 후 다시 시도해 주세요."
                ) from exc

            raise RuntimeError(
                f"TMDB API 오류(HTTP {exc.code})"
            ) from exc

        except urllib.error.URLError as exc:
            print(
                "[TMDB 연결 오류] "
                f"path={path}, "
                f"reason={exc.reason!r}"
            )

            raise RuntimeError(
                "TMDB 서버에 연결할 수 없어요. "
                "잠시 후 다시 시도해 주세요."
            ) from exc

        except TimeoutError as exc:
            raise RuntimeError(
                "TMDB 서버 응답이 늦어요. "
                "잠시 후 다시 시도해 주세요."
            ) from exc

        if not isinstance(data, dict):
            raise RuntimeError(
                "TMDB 응답 형식이 올바르지 않아요."
            )

        if data.get("status_code") and data.get("status_message"):
            raise RuntimeError(
                f"API 오류: {data['status_message']}"
            )

        return data

    async def _tmdb_search_tv(
        self,
        query: str,
    ) -> list[dict[str, Any]]:
        normalized_query = self._normalize_text(query)
        now = datetime.now()

        cached = self._tmdb_cache.get(normalized_query)

        if cached:
            cached_at, cached_results = cached

            if now - cached_at < self._tmdb_cache_ttl:
                return cached_results

        data = await asyncio.to_thread(
            self._tmdb_request,
            "/search/tv",
            {
                "query": query,
                "language": "ko-KR",
                "include_adult": "false",
                "page": 1,
            },
        )

        results = data.get("results", [])

        if not isinstance(results, list):
            results = []

        results = [
            item
            for item in results
            if isinstance(item, dict)
        ]

        self._tmdb_cache[normalized_query] = (
            now,
            results,
        )

        return results

    async def _tmdb_get_tv_details(
        self,
        tv_id: int,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._tmdb_request,
            f"/tv/{tv_id}",
            {
                "language": "ko-KR",
            },
        )

    async def _tmdb_search_with_details(
        self,
        query: str,
    ) -> list[dict[str, Any]]:
        results = await self._tmdb_search_tv(query)

        if not results:
            return []

        detailed_results: list[dict[str, Any]] = []

        for index, item in enumerate(results[:25]):
            tv_id = item.get("id")

            if not tv_id:
                detailed_results.append(item)
                continue

            if index == 0:
                try:
                    details = await self._tmdb_get_tv_details(
                        int(tv_id)
                    )

                    detailed_results.append(details)
                    continue

                except RuntimeError as exc:
                    print(
                        "[TMDB 상세 조회 실패] "
                        f"tv_id={tv_id}, error={exc}"
                    )

            detailed_results.append(item)

        return detailed_results

    @classmethod
    def _anissia_title(
        cls,
        item: dict[str, Any],
    ) -> str:
        title = cls._safe_text(
            item.get("subject"),
            "제목 미상",
        )

        if item.get("status") == "OFF":
            return f"[결방] {title}"

        return title

    @classmethod
    def _create_schedule_embed(
        cls,
        schedules: dict[str, list[dict[str, Any]]],
    ) -> discord.Embed:
        today_week = str(
            (datetime.now().weekday() + 1) % 7
        )

        today_label = cls.WEEK_LABELS[today_week]
        items = schedules.get(today_week, [])

        embed = discord.Embed(
            title=f"📺 오늘의 편성표 · {today_label}",
            description="오늘의 편성표입니다.",
            color=discord.Color.blurple(),
        )

        if not items:
            embed.description = (
                "오늘 등록된 편성표를 찾지 못했어요."
            )

            embed.set_footer(text="데이터: 애니시아")
            return embed

        sorted_items = sorted(
            items,
            key=lambda item: (
                cls._safe_text(
                    item.get("time"),
                    "99:99",
                ),
                cls._safe_text(
                    item.get("subject"),
                    "",
                ),
            ),
        )

        for index, item in enumerate(
            sorted_items[:25],
            start=1,
        ):
            title = cls._anissia_title(item)
            time_value = cls._format_anissia_time(
                item.get("time")
            )
            genres = cls._format_genres(
                item.get("genres")
            )

            embed.add_field(
                name=f"{index}. {title}",
                value=(
                    f"🕒 {time_value}\n"
                    f"장르: {genres[:180]}"
                )[:1024],
                inline=False,
            )

        if len(sorted_items) > 25:
            embed.add_field(
                name="안내",
                value=(
                    f"총 {len(sorted_items)}개 중 "
                    "상위 25개만 표시했어요."
                ),
                inline=False,
            )

        embed.set_footer(text="데이터: 애니시아")

        return embed

    @classmethod
    def _create_tmdb_detail_embed(
        cls,
        item: dict[str, Any],
    ) -> discord.Embed:
        title = cls._tmdb_title(item)
        original_title = item.get("original_name")

        overview = item.get("overview") or (
            "줄거리 정보가 등록되어 있지 않아요."
        )

        if len(overview) > 900:
            overview = overview[:897] + "..."

        embed = discord.Embed(
            title=f"🎬 {title}",
            description=overview,
            color=discord.Color.green(),
        )

        poster_path = item.get("poster_path")

        if poster_path:
            embed.set_thumbnail(
                url=f"{cls.TMDB_IMAGE_BASE_URL}{poster_path}"
            )

        if original_title and original_title != title:
            embed.add_field(
                name="원제",
                value=str(original_title)[:1024],
                inline=False,
            )

        vote_average = item.get("vote_average")

        embed.add_field(
            name="평점",
            value=(
                f"⭐ {float(vote_average):.1f}/10"
                if vote_average
                else "미등록"
            ),
            inline=True,
        )

        embed.add_field(
            name="첫 방영일",
            value=item.get("first_air_date") or "미등록",
            inline=True,
        )

        number_of_seasons = item.get("number_of_seasons")
        number_of_episodes = item.get("number_of_episodes")

        if (
            number_of_seasons is not None
            or number_of_episodes is not None
        ):
            embed.add_field(
                name="방영 정보",
                value=(
                    f"시즌 {number_of_seasons or '미상'}"
                    f" · "
                    f"{number_of_episodes or '미상'}화"
                ),
                inline=True,
            )

        genres = item.get("genres") or []

        if isinstance(genres, list):
            genre_names = [
                genre.get("name")
                for genre in genres
                if isinstance(genre, dict)
                and genre.get("name")
            ]

            if genre_names:
                embed.add_field(
                    name="장르",
                    value=", ".join(genre_names)[:1000],
                    inline=False,
                )

        networks = item.get("networks") or []

        if isinstance(networks, list):
            network_names = [
                network.get("name")
                for network in networks
                if isinstance(network, dict)
                and network.get("name")
            ]

            if network_names:
                embed.add_field(
                    name="방송국",
                    value=", ".join(network_names)[:1000],
                    inline=False,
                )

        tv_id = item.get("id")

        if tv_id:
            embed.add_field(
                name="자세히 보기",
                value=(
                    "[TMDB에서 보기]"
                    f"(https://www.themoviedb.org/tv/{tv_id})"
                ),
                inline=False,
            )

        embed.set_footer(
            text=cls.TMDB_ATTRIBUTION
        )

        return embed

    @classmethod
    def _create_tmdb_result_embed(
        cls,
        query: str,
        results: list[dict[str, Any]],
    ) -> discord.Embed:
        embed = discord.Embed(
            title=f"🔎 '{query}'에 대한 검색 결과",
            description=(
                "아래 드롭다운에서 작품을 선택하세요."
            ),
            color=discord.Color.green(),
        )

        for index, item in enumerate(results[:25], start=1):
            title = cls._tmdb_title(item)
            original_title = item.get("original_name")
            first_air_date = item.get("first_air_date")
            vote_average = item.get("vote_average")

            values: list[str] = []

            if original_title and original_title != title:
                values.append(f"원제: {original_title}")

        embed.set_footer(
            text=f"{cls.TMDB_ATTRIBUTION}"
        )

        return embed

    async def _handle_tmdb_search(
        self,
        interaction: discord.Interaction,
        query: str,
    ) -> None:
        results = await self._tmdb_search_with_details(query)

        if not results:
            await interaction.followup.send(
                f"🔎 **{self._escape(query)}**에 해당하는 "
                "작품을 찾지 못했어요."
            )
            return

        if len(results) == 1:
            item = results[0]
            tv_id = item.get("id")

            if tv_id:
                try:
                    item = await self._tmdb_get_tv_details(
                        int(tv_id)
                    )
                except RuntimeError as exc:
                    print(
                        "[TMDB 상세 조회 실패] "
                        f"tv_id={tv_id}, error={exc}"
                    )

            embed = self._create_tmdb_detail_embed(item)

            await interaction.followup.send(
                embed=embed
            )
            return

        results = results[:25]

        embed = self._create_tmdb_result_embed(
            query,
            results,
        )

        view = TMDBSelectionView(
            cog=self,
            results=results,
        )

        message = await interaction.followup.send(
            embed=embed,
            view=view,
            wait=True,
        )

        view.message = message

    @app_commands.command(
        name="애니검색",
        description="편성표 또는 애니 작품 정보를 검색해요.",
    )
    @app_commands.describe(
        종류="검색할 항목을 선택하세요.",
        검색어=(
            "검색할 작품명을 입력하세요. "
            "편성표에서는 생략할 수 있어요."
        ),
    )
    @app_commands.choices(
        종류=[
            app_commands.Choice(
                name="작품 상세 검색",
                value="anime",
            ),
            app_commands.Choice(
                name="오늘의 편성표",
                value="schedule",
            ),
        ]
    )
    async def anime_search(
        self,
        interaction: discord.Interaction,
        종류: app_commands.Choice[str],
        검색어: str | None = None,
    ):
        mode = 종류.value
        query_text = (검색어 or "").strip()

        if mode == "anime" and not query_text:
            await interaction.response.send_message(
                "작품 상세 검색에는 작품명을 입력해 주세요.",
                ephemeral=True,
            )
            return

        if len(query_text) > 100:
            await interaction.response.send_message(
                "검색어는 100자 이하로 입력해 주세요.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)

        try:
            if mode == "schedule":
                schedules = await self._fetch_all_schedules()

                embed = self._create_schedule_embed(
                    schedules
                )

                await interaction.followup.send(
                    embed=embed
                )
                return

            if mode == "anime":
                await self._handle_tmdb_search(
                    interaction,
                    query_text,
                )
                return

            await interaction.followup.send(
                "⚠️ 알 수 없는 검색 종류에요.",
                ephemeral=True,
            )

        except RuntimeError as exc:
            await interaction.followup.send(
                f"⚠️ {exc}",
                ephemeral=True,
            )

        except Exception as exc:
            print(
                "[검색 오류] "
                f"{type(exc).__name__}: {exc}"
            )

            await interaction.followup.send(
                "⚠️ 검색 중 오류가 발생했어요. "
                "잠시 후 다시 시도해 주세요.",
                ephemeral=True,
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Animation(bot))