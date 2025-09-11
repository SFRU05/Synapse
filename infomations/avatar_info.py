import discord
import datetime

async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(
        title=f"{member.display_name}의 아바타",
        color=discord.Color.blue(),
        timestamp = datetime.datetime.now()
    )
    embed.set_image(url=member.avatar.url if member.avatar else discord.Embed.Empty)
    await ctx.send(embed=embed)