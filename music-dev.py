import discord
from discord.ext import commands
import wavelink
import asyncio

class MusicQueue:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.current = None

    async def add_to_queue(self, track):
        await self.queue.put(track)

    async def get_next(self):
        self.current = await self.queue.get()
        return self.current

music_queue = MusicQueue()

def setup(bot):
    @bot.event
    async def on_ready():
        # Lavalink 서버에 연결
        if not hasattr(bot, "wavelink_ready"):
            await wavelink.NodePool.create_node(
                bot=bot,
                host="localhost",  # Lavalink 서버 주소
                port=2333,         # Lavalink 서버 포트
                password="youshallnotpass",  # Lavalink 서버 비밀번호
                https=False
            )
            bot.wavelink_ready = True
        print("Lavalink 연결됨")

    @bot.command()
    async def join(ctx):
        if ctx.author.voice:
            channel = ctx.author.voice.channel
            await channel.connect(cls=wavelink.Player)
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
    async def play(ctx, *, query):
        if not ctx.voice_client:
            if ctx.author.voice:
                await ctx.invoke(bot.get_command("join"))
            else:
                await ctx.send("먼저 음성 채널에 들어가세요.")
                return

        # 유튜브 검색
        tracks = await wavelink.YouTubeTrack.search(query=query, return_first=True)
        if not tracks:
            await ctx.send("트랙을 찾을 수 없습니다.")
            return

        await music_queue.add_to_queue(tracks)
        embed = discord.Embed(title="곡 추가됨", description=tracks.title, color=discord.Color.blue())
        embed.add_field(name="요청자", value=ctx.author.mention)
        await ctx.send(embed=embed)

        if not ctx.voice_client.is_playing():
            await play_next(ctx)

    async def play_next(ctx):
        if not music_queue.queue.empty():
            track = await music_queue.get_next()
            await ctx.voice_client.play(track)
            embed = discord.Embed(title="🎶 현재 재생 중", description=track.title, color=discord.Color.green())
            embed.add_field(name="요청자", value=ctx.author.mention)
            await ctx.send(embed=embed)

            def after_play(error):
                fut = asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)
                try:
                    fut.result()
                except Exception as e:
                    print(f"Error in after_play: {e}")

            ctx.voice_client.after = after_play

    @bot.command()
    async def skip(ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            await ctx.voice_client.stop()
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
            await ctx.voice_client.stop()
            while not music_queue.queue.empty():
                music_queue.queue.get_nowait()
            await ctx.send("음악을 정지하고 큐를 비웠습니다.")
        else:
            await ctx.send("재생 중인 곡이 없습니다.")

    @bot.command()
    async def queue(ctx, action: str = None, *, query: str = None):
        if action == "add" and query:
            try:
                tracks = await wavelink.YouTubeTrack.search(query=query, return_first=True)
                if not tracks:
                    await ctx.send("트랙을 찾을 수 없습니다.")
                    return
                await music_queue.add_to_queue(tracks)
                embed = discord.Embed(title="곡 추가됨", description=tracks.title, color=discord.Color.blue())
                embed.add_field(name="요청자", value=ctx.author.mention)
                await ctx.send(embed=embed)
            except Exception as e:
                await ctx.send(f"곡을 추가하는 중 오류가 발생했습니다: {e}")
        elif music_queue.queue.empty():
            embed = discord.Embed(title="🎵 현재 큐", description="현재 큐에 곡이 없습니다.", color=discord.Color.red())
            await ctx.send(embed=embed)
        else:
            queue_list = list(music_queue.queue._queue)
            description = "\n".join([f"{i + 1}. [{item.title}]({item.uri})" for i, item in enumerate(queue_list)])
            embed = discord.Embed(title="🎵 현재 큐", description=description, color=discord.Color.blue())
            await ctx.send(embed=embed)