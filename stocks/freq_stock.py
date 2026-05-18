import discord
from discord import app_commands
import os
import sqlite3
import yfinance as yf

DB_PATH = 'favorite_stocks.db'

def get_favorites(user_id):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT symbol, name FROM favorites WHERE user_id=?", (user_id,))
        return cur.fetchall()

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

@app_commands.command(name="관심종목", description="내 관심 종목 리스트 보기")
async def favorites_slash(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True, ephemeral=False)
    user_id = str(interaction.user.id)
    favs = get_favorites(user_id)
    if not favs:
        await interaction.followup.send("관심종목이 없어요. `/stock`으로 관심종목을 추가해보세요!")
        return
    price_list = []
    for symbol, name in favs:
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            price = info.get('regularMarketPrice')
            currency = info.get('currency', '')
            price_list.append((price if price is not None else 0, symbol, name, currency))
        except Exception:
            price_list.append((0, symbol, name, ''))
    price_list.sort(reverse=True, key=lambda x: (x[0] if x[0] is not None else 0))
    result_list = []
    for price, symbol, name, currency in price_list:
        p_str = f"{price:,.2f}{currency}" if currency and price else "정보없음"
        result_list.append(f"`{symbol}` `{name}`  |  **{p_str}**")
    embed = discord.Embed(
        title=f"{interaction.user.display_name} 님의 관심 종목이에요!",
        description="\n".join(result_list),
        color=discord.Color.gold()
    )
    await interaction.followup.send(embed=embed)