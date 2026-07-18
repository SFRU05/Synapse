import io
import re

import aiohttp
import discord
from discord.ext import commands
import emoji as emoji_lib

from jumbo_emoji.toggle_store import is_enabled

CUSTOM_EMOJI_FULL_RE = re.compile(r"^<(a?):(\w+):(\d+)>$")


class JumboEmoji(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.http: aiohttp.ClientSession | None = None

    async def cog_load(self):
        self.http = aiohttp.ClientSession()

    async def cog_unload(self):
        if self.http and not self.http.closed:
            await self.http.close()

    # ---------- parse ----------
    def _extract_one_emoji_url(self, content: str):
        """반환값: (image_url, filename, kind) 또는 None. kind는 "custom" 또는 "unicode" """
        s = content.strip()
        if not s:
            return None

        # 커스텀 이모지 단독 메시지
        m = CUSTOM_EMOJI_FULL_RE.fullmatch(s)
        if m:
            animated, _, emoji_id = m.groups()
            ext = "gif" if animated == "a" else "png"
            return (
                f"https://cdn.discordapp.com/emojis/{emoji_id}.{ext}?size=512&quality=lossless",
                f"emoji.{ext}",
                "custom",
            )

        # 유니코드 이모지 단독 메시지
        em = emoji_lib.emoji_list(s)
        if len(em) != 1:
            return None

        token = em[0]["emoji"]
        if s != token:
            return None

        codepoints = "-".join(f"{ord(ch):x}" for ch in token)
        if not codepoints:
            return None

        return (
            f"https://cdn.jsdelivr.net/gh/jdecked/twemoji@latest/assets/72x72/{codepoints}.png",
            "emoji.png",
            "unicode",
        )

    # ---------- helpers ----------
    async def _download(self, url: str):
        if not self.http:
            return None
        try:
            async with self.http.get(url, timeout=10) as resp:
                if resp.status == 200:
                    return await resp.read()
        except Exception:
            return None
        return None

    async def _get_or_create_hook(self, channel: discord.TextChannel):
        hooks = await channel.webhooks()
        hook = discord.utils.get(hooks, name="EmojiAmplifier")
        if hook is None:
            hook = await channel.create_webhook(name="EmojiAmplifier")
        return hook

    def _one_line(self, text: str, limit: int = 30) -> str:
        t = (text or "").replace("\n", " ").strip()
        if not t:
            return "원본 메시지"
        return t if len(t) <= limit else t[:limit] + "…"

    async def _send_image_webhook(self, message: discord.Message, image_url: str, filename: str):
        data = await self._download(image_url)
        if not data:
            return

        hook = await self._get_or_create_hook(message.channel)
        file = discord.File(io.BytesIO(data), filename=filename)

        # 답장(reply)이었으면: "<@멘션>: <원본 내용 하이퍼링크>"
        content = None
        if message.reference and message.reference.message_id:
            try:
                ref_msg = await message.channel.fetch_message(message.reference.message_id)
                label = self._one_line(ref_msg.content, 30)
                jump = ref_msg.jump_url
                content = f"{ref_msg.author.mention}: [{label}]({jump})"
            except Exception:
                content = None

        await hook.send(
            content=content,
            file=file,
            username=message.author.display_name,
            avatar_url=message.author.display_avatar.url,
            allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
        )

    # ---------- event ----------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.webhook_id is not None:
            return
        if message.guild is None:
            return

        parsed = self._extract_one_emoji_url(message.content)
        if not parsed:
            return

        image_url, filename, kind = parsed

        # kind: "custom"(커스텀 이모지) 또는 "unicode"(기본 이모지) - 각각 따로 on/off 체크
        if not is_enabled(message.guild.id, kind):
            return

        # 원본 삭제
        try:
            await message.delete()
        except Exception:
            pass

        await self._send_image_webhook(message, image_url, filename)


async def setup(bot: commands.Bot):
    await bot.add_cog(JumboEmoji(bot))