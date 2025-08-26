import discord
import yt_dlp
import asyncio

ytdl_format_options = {
    'format': 'bestaudio/best',
    'quiet': True,
    'noplaylist': True,
}
ffmpeg_options = {
    'options': '-reconnect_on_network_error -vn'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

def search_youtube(url):
    info = ytdl.extract_info(url, download=False)
    return info['url'], info.get('title', 'Unknown Title')

class MusicQueue:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.current = None

    async def add_to_queue(self, url, title):
        await self.queue.put((url, title))

    async def get_next(self):
        self.current = await self.queue.get()
        return self.current

music_queue = MusicQueue()

def setup(bot):
    @bot.command()
    async def join(ctx):
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
            await ctx.send("음성 채널에 접속했습니다.")
        else:
            await ctx.send("먼저 음성 채널에 들어가세요.")


    @bot.command()
    async def leave(ctx):
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await ctx.send("음성 채널에서 나갔습니다.")
        else:
            await ctx.send("이미 음성 채널에 없습니다.")

    @bot.command()
    async def play(ctx, url):
        if not ctx.voice_client:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("먼저 음성 채널에 들어가세요.")
                return

        stream_url, title = search_youtube(url)
        await music_queue.add_to_queue(stream_url, title)

        embed = discord.Embed(title="곡 추가됨", description=title, color=discord.Color.blue())
        embed.add_field(name="요청자", value=ctx.author.mention)
        await ctx.send(embed=embed)

        if not ctx.voice_client.is_playing():
            await play_next(ctx)

    async def play_next(ctx):
        if not music_queue.queue.empty():
            stream_url, title = await music_queue.get_next()
            ctx.voice_client.play(
                discord.FFmpegPCMAudio(stream_url, **ffmpeg_options),
                after=lambda e: bot.loop.create_task(play_next(ctx))
            )

            embed = discord.Embed(title="🎶 현재 재생 중", description=title, color=discord.Color.green())
            embed.add_field(name="요청자", value=ctx.author.mention)
            await ctx.send(embed=embed)

    @bot.command()
    async def skip(ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            if music_queue.queue.empty():
                embed = discord.Embed(title="🎵 스킵", description="다음에 재생할 곡이 없습니다.", color=discord.Color.red())
                await ctx.message.add_reaction("❌")
                await ctx.send(embed=embed)

            else:
                await ctx.message.add_reaction("⏭️")
        else:
            await ctx.send("재생 중인 곡이 없습니다.")

    @bot.command()
    async def stop(ctx):
        if ctx.voice_client:
            ctx.voice_client.stop()
            while not music_queue.queue.empty():
                music_queue.queue.get_nowait()
            await ctx.send("음악을 정지하고 큐를 비웠습니다.")
        else:
            await ctx.send("재생 중인 곡이 없습니다.")

    @bot.command()
    async def queue(ctx, action: str = None, url: str = None):
        if action == "add" and url:
            try:
                stream_url, title = search_youtube(url)
                await music_queue.add_to_queue(stream_url, title)
                embed = discord.Embed(title="곡 추가됨", description=title, color=discord.Color.blue())
                embed.add_field(name="요청자", value=ctx.author.mention)
                await ctx.send(embed=embed)
            except Exception as e:
                await ctx.send(f"곡을 추가하는 중 오류가 발생했습니다: {e}")
        elif music_queue.queue.empty():
            embed = discord.Embed(title="🎵 현재 큐", description="현재 큐에 곡이 없습니다.", color=discord.Color.red())
            await ctx.send(embed=embed)
        else:
            queue_list = list(music_queue.queue._queue)
            description = "\n".join([f"{i + 1}. [{item[1]}]({item[0]})" for i, item in enumerate(queue_list)])

            embed = discord.Embed(title="🎵 현재 큐", description=description, color=discord.Color.blue())
            await ctx.send(embed=embed)