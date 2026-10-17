from __future__ import annotations

import math
import os
import re
from datetime import datetime, timedelta
from urllib.parse import unquote
from zoneinfo import ZoneInfo

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands


KST = ZoneInfo("Asia/Seoul")

KMA_SERVICE_KEY = unquote(
    os.getenv("KMA_SERVICE_KEY", "")
    .strip()
    .strip('"')
    .strip("'")
)

KAKAO_REST_API_KEY = (
    os.getenv("KAKAO_REST_API_KEY", "")
    .strip()
    .strip('"')
    .strip("'")
)

KMA_BASE_URL = (
    "https://apis.data.go.kr/"
    "1360000/VilageFcstInfoService_2.0"
)

KAKAO_LOCAL_URL = (
    "https://dapi.kakao.com/"
    "v2/local/search/keyword.json"
)


def convert_to_grid(lat: float, lon: float) -> tuple[int, int]:
    """위도·경도를 기상청 격자 좌표로 변환합니다."""
    earth_radius = 6371.00877
    grid_size = 5.0

    standard_latitude_1 = 30.0
    standard_latitude_2 = 60.0
    origin_lon = 126.0
    origin_lat = 38.0

    origin_x = 43
    origin_y = 136

    radian = math.pi / 180.0

    earth_radius /= grid_size

    standard_latitude_1 *= radian
    standard_latitude_2 *= radian
    origin_lon *= radian
    origin_lat *= radian

    sn = math.log(
        math.cos(standard_latitude_1)
        / math.cos(standard_latitude_2)
    ) / math.log(
        math.tan(math.pi / 4 + standard_latitude_2 / 2)
        / math.tan(math.pi / 4 + standard_latitude_1 / 2)
    )

    sf = (
        math.tan(math.pi / 4 + standard_latitude_1 / 2)
        ** sn
        * math.cos(standard_latitude_1)
        / sn
    )

    ro = (
        earth_radius
        * sf
        / math.tan(math.pi / 4 + origin_lat / 2) ** sn
    )

    ra = (
        earth_radius
        * sf
        / math.tan(math.pi / 4 + lat * radian / 2) ** sn
    )

    theta = lon * radian - origin_lon

    if theta > math.pi:
        theta -= 2 * math.pi

    if theta < -math.pi:
        theta += 2 * math.pi

    theta *= sn

    nx = int(ra * math.sin(theta) + origin_x + 0.5)
    ny = int(ro - ra * math.cos(theta) + origin_y + 0.5)

    return nx, ny


def shorten_address(address: str) -> str:
    address = " ".join(address.split())

    match = re.match(
        r"^(.+?(?:읍|면|동|리))(?:\s|$)",
        address,
    )

    if match:
        return match.group(1).strip()

    return address


def format_forecast_time(
    date_text: str,
    time_text: str,
) -> str:
    """기상청 날짜와 시간을 표시용 문자열로 변환합니다."""
    try:
        parsed = datetime.strptime(
            date_text + time_text,
            "%Y%m%d%H%M",
        )

        return parsed.strftime("%m/%d %H:%M")

    except ValueError:
        return f"{date_text} {time_text}"


def parse_probability(value) -> int | None:
    """강수확률을 0~100 사이 정수로 변환합니다."""
    if value in (None, "-"):
        return None

    try:
        return max(0, min(100, int(float(value))))
    except (TypeError, ValueError):
        return None


def make_probability_gauge(probability: int | None) -> str:
    """강수확률을 10칸 이모지 게이지로 표시합니다."""
    if probability is None:
        return "자료 없음"

    filled_count = round(probability / 10)

    if probability >= 70:
        filled = "🟥"
    elif probability >= 40:
        filled = "🟨"
    elif probability > 0:
        filled = "🟦"
    else:
        filled = "⬜"

    empty_count = 10 - filled_count

    return filled * filled_count + "⬜" * empty_count


def probability_color(
    probability: int | None,
) -> discord.Color:
    """강수확률에 따른 Embed 색상을 반환합니다."""
    if probability is None:
        return discord.Color.light_grey()

    if probability >= 70:
        return discord.Color.red()

    if probability >= 40:
        return discord.Color.gold()

    return discord.Color.blue()


async def request_json(
    session: aiohttp.ClientSession,
    url: str,
    params: dict,
    headers: dict | None = None,
) -> dict:
    """GET 요청 후 JSON을 반환합니다."""
    timeout = aiohttp.ClientTimeout(total=15)

    async with session.get(
        url,
        params=params,
        headers=headers,
        timeout=timeout,
    ) as response:
        body = await response.text()

        if response.status != 200:
            raise RuntimeError(
                f"API HTTP {response.status}: {body[:350]}"
            )

        try:
            return await response.json(content_type=None)
        except Exception as exc:
            raise RuntimeError(
                f"API 응답이 JSON이 아닙니다: {body[:350]}"
            ) from exc


async def search_regions(
    session: aiohttp.ClientSession,
    query: str,
) -> list[dict]:
    """
    카카오 검색 결과를 행정구역 단위로 정리합니다.

    같은 동 안의 건물·장소는 좌표가 달라도
    같은 읍·면·동·리 주소로 합칩니다.
    """
    headers = {
        "Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"
    }

    results: list[dict] = []
    seen_addresses: set[str] = set()

    for page in range(1, 4):
        data = await request_json(
            session,
            KAKAO_LOCAL_URL,
            {
                "query": query,
                "page": page,
                "size": 15,
                "sort": "accuracy",
            },
            headers,
        )

        for item in data.get("documents", []):
            raw_address = item.get("address_name") or ""

            if not raw_address:
                continue

            if not item.get("x") or not item.get("y"):
                continue

            try:
                lon = float(item["x"])
                lat = float(item["y"])
            except (TypeError, ValueError):
                continue

            address = shorten_address(raw_address)

            if not address:
                continue

            # 좌표나 건물명이 아니라 행정구역 주소만 기준으로 중복 제거합니다.
            if address in seen_addresses:
                continue

            seen_addresses.add(address)

            results.append(
                {
                    "name": address[:100],
                    "address": address[:100],
                    "lat": lat,
                    "lon": lon,
                }
            )

        if data.get("meta", {}).get("is_end", True):
            break

    return results


def get_latest_forecast_time(
    now: datetime,
) -> tuple[str, str]:
    available_time = now - timedelta(minutes=40)
    candidates: list[datetime] = []

    for day_offset in (1, 0):
        target_date = (
            available_time - timedelta(days=day_offset)
        ).date()

        for hour in (2, 5, 8, 11, 14, 17, 20, 23):
            candidate = datetime(
                target_date.year,
                target_date.month,
                target_date.day,
                hour,
                tzinfo=KST,
            )

            if candidate <= available_time:
                candidates.append(candidate)

    latest = max(candidates)

    return (
        latest.strftime("%Y%m%d"),
        latest.strftime("%H00"),
    )


async def get_kma_items(
    session: aiohttp.ClientSession,
    endpoint: str,
    params: dict,
) -> list[dict]:
    request_params = {
        **params,
        "serviceKey": KMA_SERVICE_KEY,
        "dataType": "JSON",
        "numOfRows": 1000,
        "pageNo": 1,
    }

    data = await request_json(
        session,
        f"{KMA_BASE_URL}/{endpoint}",
        request_params,
    )

    try:
        response = data["response"]
        header = response["header"]

        if header.get("resultCode") != "00":
            raise RuntimeError(
                header.get(
                    "resultMsg",
                    "기상청 API 오류",
                )
            )

        return response["body"]["items"]["item"]

    except (KeyError, TypeError) as exc:
        raise RuntimeError(
            "기상청 API 응답을 확인할 수 없습니다. "
            "서비스 키와 활용 승인을 확인해 주세요."
        ) from exc


async def get_weather(
    lat: float,
    lon: float,
) -> tuple[dict, list[dict]]:
    """현재 날씨와 시간별 예보를 조회합니다."""
    now = datetime.now(KST)
    nx, ny = convert_to_grid(lat, lon)

    async with aiohttp.ClientSession() as session:
        observation_items: list[dict] = []

        # 초단기실황 발표 지연에 대비해 최대 3번 재시도합니다.
        for back in range(3):
            target_time = now - timedelta(
                minutes=40,
                hours=back,
            )

            try:
                observation_items = await get_kma_items(
                    session,
                    "getUltraSrtNcst",
                    {
                        "base_date": target_time.strftime(
                            "%Y%m%d"
                        ),
                        "base_time": target_time.strftime(
                            "%H00"
                        ),
                        "nx": nx,
                        "ny": ny,
                    },
                )

                if observation_items:
                    break

            except Exception:
                if back == 2:
                    raise

        base_date, base_time = get_latest_forecast_time(now)

        forecast_items = await get_kma_items(
            session,
            "getVilageFcst",
            {
                "base_date": base_date,
                "base_time": base_time,
                "nx": nx,
                "ny": ny,
            },
        )

    observations = {
        item["category"]: item["obsrValue"]
        for item in observation_items
    }

    current = {
        "temp": observations.get("T1H"),
        "rain": observations.get("RN1"),
        "humidity": observations.get("REH"),
        "wind": observations.get("WSD"),
        "nx": nx,
        "ny": ny,
    }

    grouped: dict[tuple[str, str], dict] = {}

    for item in forecast_items:
        key = (
            item["fcstDate"],
            item["fcstTime"],
        )

        grouped.setdefault(key, {})
        grouped[key][item["category"]] = item["fcstValue"]

    forecast: list[dict] = []
    now_key = now.strftime("%Y%m%d%H%M")

    for (date, time), values in sorted(grouped.items()):
        if date + time < now_key:
            continue

        if not any(
            category in values
            for category in ("TMP", "SKY", "PTY", "POP")
        ):
            continue

        forecast.append(
            {
                "date": date,
                "time": time,
                "temp": values.get("TMP"),
                "sky": values.get("SKY"),
                "pty": values.get("PTY"),
                "humidity": values.get("REH"),
                "wind": values.get("WSD"),
                "pop": values.get("POP"),
            }
        )

        if len(forecast) >= 8:
            break

    return current, forecast


def weather_condition(sky, pty) -> str:
    """하늘 상태와 강수 형태를 변환합니다."""
    precipitation_names = {
        "1": "비",
        "2": "비/눈",
        "3": "눈",
        "4": "소나기",
        "5": "빗방울",
        "6": "빗방울/눈날림",
        "7": "눈날림",
    }

    sky_names = {
        "1": "맑음",
        "3": "구름 많음",
        "4": "흐림",
    }

    if pty is not None and str(pty) != "0":
        return precipitation_names.get(
            str(pty),
            "강수",
        )

    return sky_names.get(
        str(sky),
        "정보 없음",
    )


def make_weather_embed(
    region: dict,
    current: dict,
    forecast: list[dict],
) -> discord.Embed:

    embed = discord.Embed(
        title=f"🌦️ {region['address']}",
        description="현재 날씨와 시간별 예보입니다.",
        color=discord.Color.blue(),
    )

    temp = current.get("temp")
    humidity = current.get("humidity")
    wind = current.get("wind")
    rain = current.get("rain")

    embed.add_field(
        name="현재 기온",
        value=(
            f"**{temp}°C**"
            if temp not in (None, "-")
            else "자료 없음"
        ),
        inline=True,
    )

    embed.add_field(
        name="습도",
        value=(
            f"{humidity}%"
            if humidity not in (None, "-")
            else "자료 없음"
        ),
        inline=True,
    )

    embed.add_field(
        name="풍속",
        value=(
            f"{wind} m/s"
            if wind not in (None, "-")
            else "자료 없음"
        ),
        inline=True,
    )

    embed.add_field(
        name="최근 1시간 강수",
        value=(
            f"{rain} mm"
            if rain not in (None, "-")
            else "자료 없음"
        ),
        inline=True,
    )

    lines: list[str] = []

    for item in forecast:
        label = format_forecast_time(
            item["date"],
            item["time"],
        )

        condition = weather_condition(
            item.get("sky"),
            item.get("pty"),
        )

        line = f"**{label}** · {condition}"

        if item.get("temp") not in (None, "-"):
            line += f" · {item['temp']}°C"

        if item.get("humidity") not in (None, "-"):
            line += f" · 습도 {item['humidity']}%"

        lines.append(line)

    embed.add_field(
        name="시간별 예보",
        value=(
            "\n".join(lines)[:1024]
            if lines
            else "예보 자료가 없어요."
        ),
        inline=False,
    )

    embed.set_footer(
        text=(
            "자료: 기상청 단기예보"
        )
    )

    return embed


def make_rain_embed(
    region: dict,
    forecast: list[dict],
) -> discord.Embed:
    """강수확률 Embed를 생성합니다."""
    probabilities = [
        parse_probability(item.get("pop"))
        for item in forecast
    ]

    valid_probabilities = [
        probability
        for probability in probabilities
        if probability is not None
    ]

    highest_probability = (
        max(valid_probabilities)
        if valid_probabilities
        else None
    )

    embed = discord.Embed(
        title=f"🌧️ {region['address']}",
        description=(
            "시간별 강수확률이에요.\n"
            "🟦 낮음 · 🟨 보통 · 🟥 높음"
        ),
        color=probability_color(highest_probability),
    )

    lines: list[str] = []

    for item in forecast:
        label = format_forecast_time(
            item["date"],
            item["time"],
        )

        probability = parse_probability(
            item.get("pop")
        )

        if probability is None:
            lines.append(
                f"**{label}** · 강수확률 자료 없음"
            )
            continue

        gauge = make_probability_gauge(probability)

        lines.append(
            f"**{label}** · 강수확률 **{probability}%**\n"
            f"{gauge}"
        )

    embed.add_field(
        name="시간별 강수확률",
        value=(
            "\n".join(lines)[:1024]
            if lines
            else "강수확률 자료가 없습니다."
        ),
        inline=False,
    )

    if highest_probability is not None:
        embed.add_field(
            name="최고 강수확률",
            value=f"**{highest_probability}%**",
            inline=False,
        )

    embed.set_footer(
        text="자료: 기상청 단기예보"
    )

    return embed


class WeatherResultView(discord.ui.View):
    """날씨 결과에 표시되는 버튼입니다."""

    def __init__(
        self,
        owner_id: int,
        region: dict,
        forecast: list[dict],
    ):
        super().__init__(timeout=300)

        self.owner_id = owner_id
        self.region = region
        self.forecast = forecast

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "날씨를 조회한 사용자만 사용할 수 있어요.",
                ephemeral=True,
            )
            return False

        return True

    @discord.ui.button(
        label="강수확률 보기",
        emoji="🌧️",
        style=discord.ButtonStyle.primary,
    )
    async def rain_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.send_message(
            embed=make_rain_embed(
                self.region,
                self.forecast,
            ),
            ephemeral=True,
        )


class RegionSelect(discord.ui.Select):
    """검색 결과에서 지역을 선택하는 드롭다운입니다."""

    def __init__(
        self,
        owner_id: int,
        regions: list[dict],
        page: int,
        page_count: int,
    ):
        self.owner_id = owner_id
        self.regions = regions

        start = page * 25
        page_regions = regions[start:start + 25]

        options = [
            discord.SelectOption(
                label=region["address"][:100],
                description="행정구역 기준 날씨 조회",
                value=str(index),
            )
            for index, region in enumerate(
                page_regions,
                start=start,
            )
        ]

        super().__init__(
            placeholder=f"지역 선택 ({page + 1}/{page_count})",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(
        self,
        interaction: discord.Interaction,
    ):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "검색을 실행한 사용자만 선택할 수 있어요.",
                ephemeral=True,
            )
            return

        region = self.regions[int(self.values[0])]

        # 지역 선택 후 처리 중인 메시지도 본인에게만 표시합니다.
        await interaction.response.defer(
            thinking=True,
            ephemeral=True,
        )

        try:
            current, forecast = await get_weather(
                region["lat"],
                region["lon"],
            )

            # 최종 날씨 결과도 본인에게만 표시합니다.
            await interaction.followup.send(
                embed=make_weather_embed(
                    region,
                    current,
                    forecast,
                ),
                view=WeatherResultView(
                    interaction.user.id,
                    region,
                    forecast,
                ),
                ephemeral=True,
            )

            if self.view:
                self.view.stop()

        except Exception as exc:
            await interaction.followup.send(
                f"날씨 조회 실패: `{str(exc)[:350]}`",
                ephemeral=True,
            )


class RegionView(discord.ui.View):
    """검색 결과 페이지와 이전·다음 버튼입니다."""

    def __init__(
        self,
        owner_id: int,
        regions: list[dict],
    ):
        super().__init__(timeout=120)

        self.owner_id = owner_id
        self.regions = regions
        self.page = 0
        self.page_count = max(
            1,
            math.ceil(len(regions) / 25),
        )

        self.refresh()

    def refresh(self):
        self.clear_items()

        self.add_item(
            RegionSelect(
                self.owner_id,
                self.regions,
                self.page,
                self.page_count,
            )
        )

        previous_button = discord.ui.Button(
            label="이전",
            style=discord.ButtonStyle.secondary,
            row=1,
            disabled=self.page == 0,
        )

        next_button = discord.ui.Button(
            label="다음",
            style=discord.ButtonStyle.secondary,
            row=1,
            disabled=self.page >= self.page_count - 1,
        )

        previous_button.callback = self.previous_page
        next_button.callback = self.next_page

        self.add_item(previous_button)
        self.add_item(next_button)

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "이 메뉴는 검색을 실행한 사용자만 사용할 수 있어요.",
                ephemeral=True,
            )
            return False

        return True

    async def previous_page(
        self,
        interaction: discord.Interaction,
    ):
        self.page = max(0, self.page - 1)
        self.refresh()

        await interaction.response.edit_message(
            view=self
        )

    async def next_page(
        self,
        interaction: discord.Interaction,
    ):
        self.page = min(
            self.page_count - 1,
            self.page + 1,
        )
        self.refresh()

        await interaction.response.edit_message(
            view=self
        )


class Weather(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session: aiohttp.ClientSession | None = None

    async def cog_load(self):
        if not KMA_SERVICE_KEY:
            print(
                "[Weather] "
                "KMA_SERVICE_KEY가 설정되지 않았습니다."
            )

        if not KAKAO_REST_API_KEY:
            print(
                "[Weather] "
                "KAKAO_REST_API_KEY가 설정되지 않았습니다."
            )

        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15)
        )

    async def cog_unload(self):
        if self.session and not self.session.closed:
            await self.session.close()

    @app_commands.command(
        name="날씨",
        description="지역의 현재 날씨와 시간별 예보를 조회해요.",
    )
    @app_commands.describe(
        지역="예: 신창동, 부산 수영구 수영동, 북구"
    )
    async def weather(
        self,
        interaction: discord.Interaction,
        지역: str,
    ):
        if not KMA_SERVICE_KEY or not KAKAO_REST_API_KEY:
            await interaction.response.send_message(
                (
                    "날씨 기능의 API 키가 설정되지 않았습니다. 개발자에게 문의해주세요."
                ),
                ephemeral=True,
            )
            return

        query = 지역.strip()

        if len(query) < 2:
            await interaction.response.send_message(
                "지역명을 두 글자 이상 입력해 주세요.",
                ephemeral=True,
            )
            return

        # 핵심 부분입니다.
        # 검색 시작부터 본인에게만 보이는 응답으로 만듭니다.
        await interaction.response.defer(
            thinking=True,
            ephemeral=True,
        )

        try:
            if self.session is None:
                raise RuntimeError(
                    "HTTP 세션이 아직 준비되지 않았어요."
                )

            regions = await search_regions(
                self.session,
                query,
            )

            if not regions:
                await interaction.followup.send(
                    (
                        f"`{query}` 에 대한 검색 결과가 없어요.\n"
                        "시·군·구를 함께 입력해 보세요.\n"
                        "예: 서울 송파구 잠실동, 부산 수영구 수영동, 북구 신창동"
                    ),
                    ephemeral=True,
                )
                return

            # 결과가 하나면 선택창 없이 바로 조회합니다.
            if len(regions) == 1:
                region = regions[0]

                current, forecast = await get_weather(
                    region["lat"],
                    region["lon"],
                )

                await interaction.followup.send(
                    embed=make_weather_embed(
                        region,
                        current,
                        forecast,
                    ),
                    view=WeatherResultView(
                        interaction.user.id,
                        region,
                        forecast,
                    ),
                    ephemeral=True,
                )
                return

            # 여러 결과도 본인에게만 표시합니다.
            view = RegionView(
                interaction.user.id,
                regions,
            )

            await interaction.followup.send(
                content=(
                    f"**`{query}`** 에 대한 검색 결과가 "
                    f"**{len(regions)}개** 있어요.\n"
                    "아래에서 지역을 선택해 주세요."
                ),
                view=view,
                ephemeral=True,
            )

        except Exception as exc:
            await interaction.followup.send(
                (
                    "날씨 요청을 처리하지 못했어요.\n"
                    f"오류: `{str(exc)[:350]}`"
                ),
                ephemeral=True,
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Weather(bot))