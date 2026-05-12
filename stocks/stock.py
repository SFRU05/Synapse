import discord
from discord import app_commands
import os
import sqlite3
import yfinance as yf
import requests
import datetime
import pytz
import pandas as pd

def build_name_to_symbol_map():
    name2symbol = {}
    krx_files = [
        ('kospi.xls', '.KS'),
        ('kosdaq.xls', '.KQ')
    ]
    for filename, market_suffix in krx_files:
        if not os.path.exists(filename):
            print(f"{filename} 파일이 없습니다! (KRX 자동 매핑 일부 제한)")
            continue
        df = pd.read_html(filename, header=0, encoding="euc-kr")[0]
        for _, row in df.iterrows():
            try:
                name = str(row['회사명']).strip()
                code = f"{int(row['종목코드']):06d}{market_suffix}"
                name2symbol[name] = code
            except Exception:
                continue
    return name2symbol

KOR_NAME2SYMBOL = build_name_to_symbol_map()
symbol_map = {
    '삼전': '005930.KS',
    '삼성전자': '005930.KS',
    '카카오': '035720.KS',
    'AAPL': 'AAPL',
}

def resolve_symbol(user_input):
    kor_input = user_input.strip()
    user_input = kor_input.upper()
    if kor_input in symbol_map:
        return symbol_map[kor_input]
    if kor_input in KOR_NAME2SYMBOL:
        return KOR_NAME2SYMBOL[kor_input]
    if user_input.isalpha():
        return user_input
    if (user_input.endswith('.KS') or user_input.endswith('.KQ')) and user_input[:-3].isdigit():
        return user_input
    return None

DB_PATH = 'favorite_stocks.db'
if not os.path.exists(DB_PATH):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS favorites (
        user_id TEXT, symbol TEXT, name TEXT,
        PRIMARY KEY (user_id, symbol)
    )""")
    conn.commit()
    conn.close()

def is_favorite(user_id, symbol):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM favorites WHERE user_id=? AND symbol=?", (user_id, symbol))
        return cur.fetchone() is not None

def add_favorite(user_id, symbol, name):
    with sqlite3.connect(DB_PATH) as conn:
        try:
            conn.execute("INSERT INTO favorites (user_id, symbol, name) VALUES (?, ?, ?)", (user_id, symbol, name))
            conn.commit()
        except sqlite3.IntegrityError:
            pass

def remove_favorite(user_id, symbol):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM favorites WHERE user_id=? AND symbol=?", (user_id, symbol))
        conn.commit()

def get_usd_krw_rate():
    try:
        resp = requests.get('https://api.exchangerate.host/latest?base=USD&symbols=KRW', timeout=5)
        data = resp.json()
        if 'rates' in data and 'KRW' in data['rates']:
            return data['rates']['KRW']
    except Exception:
        pass
    return None

class DateSelect(discord.ui.Select):
    def __init__(self, parent_view):
        self.parent_view = parent_view
        today = datetime.datetime.now(pytz.timezone(parent_view.tz)).date()
        options = []
        for i in range(6, -1, -1):
            d = today - datetime.timedelta(days=i)
            label = d.strftime("%Y-%m-%d")
            options.append(discord.SelectOption(label=label, value=label))
        super().__init__(placeholder="날짜 선택", min_values=1, max_values=1, options=options, row=0)
    async def callback(self, interaction: discord.Interaction):
        self.parent_view.page = 0
        self.parent_view.date = datetime.datetime.strptime(self.values[0], "%Y-%m-%d").date()
        await self.parent_view.update_embed(interaction)

class StockView(discord.ui.View):
    def __init__(self, interaction, symbol, name, interval, currency, date, tz, user_id, is_fav):
        super().__init__(timeout=120)
        self.interaction = interaction
        self.symbol = symbol
        self.name = name
        self.interval = interval
        self.currency = currency
        self.tz = tz
        self.user_id = user_id
        self.is_fav_now = is_fav
        self.date = date
        self.page = 0
        self.closes = []
        self.times = []
        self.message = None
        self.add_item(DateSelect(self))
        self.update_fav_label()
    def update_fav_label(self):
        for item in self.children:
            if isinstance(item, discord.ui.Button) and getattr(item, "custom_id", None) == "fav":
                if self.is_fav_now:
                    item.label = "🗑️ 관심종목 삭제"
                    item.style = discord.ButtonStyle.danger
                else:
                    item.label = "⭐ 관심종목 추가"
                    item.style = discord.ButtonStyle.success
    async def update_embed(self, interaction=None):
        start_str = self.date.strftime('%Y-%m-%d')
        end_str = (self.date + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        ticker = yf.Ticker(self.symbol)
        h = ticker.history(interval=self.interval, start=start_str, end=end_str)
        n_per_page = 10
        self.closes, self.times = [], []
        rows = []
        if h is not None and not h.empty and 'Close' in h and len(h['Close']) > 1:
            self.closes = h['Close'].tolist()
            self.times = h.index.tolist()
            page_max = (len(self.closes)-2)//n_per_page if self.closes else 0
            self.page = min(self.page, page_max)
            st = self.page * n_per_page + 1
            ed = st + n_per_page
            for i in range(st, min(ed, len(self.closes))):
                diff = self.closes[i] - self.closes[i-1]
                emoji = "🟢" if diff > 0 else "🔴" if diff < 0 else "🟡"
                tm_str = self.times[i].strftime('%H:%M')
                price_str = (f"{self.closes[i]:,.0f}원" if self.currency == 'KRW'
                             else f"{self.closes[i]:,.2f}{self.currency}")
                rows.append(f"{tm_str} | {emoji} | {price_str}")
            sparkline = (
                "```\n시간    | 등락 | 가격\n-------|-----|----------\n"
                + "\n".join(rows)
                + "\n```"
            ) if rows else "차트 데이터 없음"
        else:
            sparkline = "차트 데이터 없음"
        embed = discord.Embed(
            title=f"{self.name} {start_str} 시간별 등락 및 주가 (page {self.page+1})",
            color=discord.Color.blue()
        )
        embed.add_field(
            name=f"{start_str} ({self.interval})",
            value=sparkline,
            inline=False
        )
        price = ticker.info.get('regularMarketPrice')
        price_text = ""
        if price is not None:
            if self.currency == 'USD':
                rate = get_usd_krw_rate()
                if rate:
                    price_text = f"{price:,.2f}달러 ≈ {int(price*rate):,}원"
                else:
                    price_text = f"{price:.2f}달러"
            elif self.currency == 'KRW':
                price_text = f"{price:,}원"
            else:
                price_text = f"{price} {self.currency}"
            embed.set_footer(text=f"현재가: {price_text}")
        if interaction:
            await interaction.response.edit_message(embed=embed, view=self)
        elif self.message:
            await self.message.edit(embed=embed, view=self)
        else:
            sent = await self.interaction.followup.send(embed=embed, view=self)
            self.message = sent
    @discord.ui.button(label="◀ PREV(시간)", style=discord.ButtonStyle.secondary, row=1)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            await self.update_embed(interaction)
    @discord.ui.button(label="NEXT(시간) ▶", style=discord.ButtonStyle.secondary, row=1)
    async def next_(self, interaction: discord.Interaction, button: discord.ui.Button):
        max_page = (len(self.closes)-2)//10 if self.closes else 0
        if self.page < max_page:
            self.page += 1
            await self.update_embed(interaction)
    @discord.ui.button(label="-", style=discord.ButtonStyle.success, row=2, custom_id="fav")
    async def favorite(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_favorite(self.user_id, self.symbol):
            add_favorite(self.user_id, self.symbol, self.name)
            self.is_fav_now = True
            self.update_fav_label()
            await interaction.response.edit_message(content="관심종목에 추가되었습니다.", embed=None, view=self)
        else:
            remove_favorite(self.user_id, self.symbol)
            self.is_fav_now = False
            self.update_fav_label()
            await interaction.response.edit_message(content="관심종목에서 삭제되었습니다.", embed=None, view=self)
    async def interaction_check(self, interaction):
        return interaction.user.id == int(self.user_id)
    async def on_timeout(self):
        try:
            if self.message:
                await self.message.edit(view=None)
        except Exception:
            pass

@app_commands.command(name="stock", description="주식 시세와 차트 보기")
@app_commands.describe(symbol="조회할 종목명/티커")
@app_commands.choices(
    interval=[
        app_commands.Choice(name="1분봉", value="1m"),
        app_commands.Choice(name="5분봉", value="5m"),
        app_commands.Choice(name="10분봉", value="10m"),
        app_commands.Choice(name="15분봉", value="15m"),
        app_commands.Choice(name="30분봉", value="30m"),
        app_commands.Choice(name="1시간봉", value="60m"),
    ]
)
async def stock_slash(
    interaction: discord.Interaction,
    symbol: str,
    interval: app_commands.Choice[str] = None
):
    await interaction.response.defer(thinking=True, ephemeral=False)
    actual_interval = interval.value if interval else "60m"
    query_symbol = resolve_symbol(symbol)
    if not query_symbol:
        await interaction.followup.send(f"**{symbol}**: 등록된(지원되는) 종목명이 아닙니다.")
        return

    try:
        ticker = yf.Ticker(query_symbol)
        info = ticker.info
    except Exception as e:
        await interaction.followup.send(f"야후 파이낸스 데이터 요청 실패: {symbol} ({query_symbol}) / {e}")
        return

    short_name = info.get('shortName')
    price = info.get('regularMarketPrice')
    if not short_name or price is None:
        await interaction.followup.send(f"**{symbol}**: 유효하지 않은 종목(심볼)입니다. 실제 상장 종목이 맞는지 확인하세요.")
        return

    currency = info.get('currency', '')
    name = short_name
    tz = 'Asia/Seoul' if currency == 'KRW' else 'America/New_York'
    now = datetime.datetime.now(pytz.timezone(tz))
    user_id = str(interaction.user.id)
    is_fav = is_favorite(user_id, query_symbol)
    view = StockView(
        interaction, query_symbol, name, actual_interval, currency, now.date(), tz, user_id, is_fav)
    await view.update_embed()