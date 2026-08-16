import discord
from discord import app_commands
from discord.ext import commands
import aiohttp

CURRENCIES = [
    ("KRW", "대한민국 원", "🇰🇷"),
    ("USD", "미국 달러", "🇺🇸"),
    ("EUR", "유로", "🇪🇺"),
    ("JPY", "일본 엔", "🇯🇵"),
    ("CNY", "중국 위안", "🇨🇳"),
    ("GBP", "영국 파운드", "🇬🇧"),
    ("AUD", "호주 달러", "🇦🇺"),
    ("CAD", "캐나다 달러", "🇨🇦"),
    ("CHF", "스위스 프랑", "🇨🇭"),
    ("HKD", "홍콩 달러", "🇭🇰"),
]

FLAG_MAP = {code: flag for code, _, flag in CURRENCIES}


async def get_exchange_rate(base: str, target: str) -> float:
    url = f"https://api.frankfurter.app/latest?amount=1&from={base}&to={target}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise RuntimeError(f"API 응답 오류 (status={resp.status})")
            data = await resp.json()
            rates = data.get("rates", {})
            if target not in rates:
                raise RuntimeError("해당 통화 조합을 지원하지 않아요.")
            return rates[target]


class AmountModal(discord.ui.Modal):

    def __init__(self, base: str, target: str):
        super().__init__(title="환율 변환")
        self.base = base
        self.target = target
        self.amount_input = discord.ui.TextInput(
            label=f"{FLAG_MAP.get(base, '')} {base} 금액을 입력해주세요!",
            placeholder="예: 100",
            required=True,
            max_length=20,
        )
        self.add_item(self.amount_input)

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.amount_input.value.replace(",", "").strip()
        try:
            amount = float(raw)
            if amount <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "0보다 큰 값을 입력해야 해요!", ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            rate = await get_exchange_rate(self.base, self.target)
        except Exception as e:
            await interaction.followup.send(f"환율 정보를 가져오지 못했습니다: {e}", ephemeral=True)
            return

        converted = amount * rate
        embed = discord.Embed(title="💱 환율 변환 결과", color=discord.Color.blurple())
        embed.add_field(
            name="입력 금액",
            value=f"{FLAG_MAP.get(self.base, '')} {amount:,.2f} {self.base}",
            inline=False,
        )
        embed.add_field(
            name="변환 결과",
            value=f"{FLAG_MAP.get(self.target, '')} {converted:,.2f} {self.target}",
            inline=False,
        )
        embed.set_footer(text=f"1 {self.base} = {rate:,.4f} {self.target}")
        await interaction.followup.send(embed=embed, ephemeral=True)


class CurrencySelect(discord.ui.Select):

    def __init__(self, placeholder: str, select_id: str):
        self.select_id = select_id  # "base" or "target"
        options = [
            discord.SelectOption(label=f"{code} · {name}", value=code, emoji=flag)
            for code, name, flag in CURRENCIES
        ]
        super().__init__(
            placeholder=placeholder,
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        view: "CurrencyView" = self.view
        if self.select_id == "base":
            view.base_currency = self.values[0]
        else:
            view.target_currency = self.values[0]
        await view.update_message(interaction)


class ConvertButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="금액 입력",
            style=discord.ButtonStyle.primary,
            emoji="💱",
            disabled=True,
        )

    async def callback(self, interaction: discord.Interaction):
        view: "CurrencyView" = self.view
        if not view.base_currency or not view.target_currency:
            await interaction.response.send_message(
                "두 개의 통화 중 하나만 선택되어 있어요. 둘 다 선택해주세요.", ephemeral=True
            )
            return
        if view.base_currency == view.target_currency:
            await interaction.response.send_message(
                "기준 통화와 변환 통화가 같아요. 다르게 선택해주세요.", ephemeral=True
            )
            return
        await interaction.response.send_modal(
            AmountModal(view.base_currency, view.target_currency)
        )

class CurrencyView(discord.ui.View):
    def __init__(self, author_id: int, timeout: float = 120):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.base_currency: str | None = None
        self.target_currency: str | None = None

        self.base_select = CurrencySelect("기준 통화를 선택하세요!", "base")
        self.target_select = CurrencySelect("변환할 통화를 선택하세요!", "target")
        self.button = ConvertButton()

        self.add_item(self.base_select)
        self.add_item(self.target_select)
        self.add_item(self.button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "본인이 요청한 메뉴만 사용할 수 있어요.", ephemeral=True
            )
            return False
        return True

    def _build_embed(self) -> discord.Embed:
        base_display = (
            f"{FLAG_MAP.get(self.base_currency, '')} {self.base_currency}"
            if self.base_currency else "미선택"
        )
        target_display = (
            f"{FLAG_MAP.get(self.target_currency, '')} {self.target_currency}"
            if self.target_currency else "미선택"
        )
        desc = (
            f"기준 통화: **{base_display}**\n"
            f"변환 통화: **{target_display}**\n\n"
            f"둘 다 선택 후 아래 버튼을 눌러 금액을 입력하세요."
        )
        return discord.Embed(title="💱 환율 변환기", description=desc, color=discord.Color.green())

    async def update_message(self, interaction: discord.Interaction):
        self.button.disabled = not (self.base_currency and self.target_currency)
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

class Currency(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="환율", description="통화를 선택해서 환율을 변환해요.")
    async def currency(self, interaction: discord.Interaction):
        view = CurrencyView(author_id=interaction.user.id)
        await interaction.response.send_message(embed=view._build_embed(), view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Currency(bot))