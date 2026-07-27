import discord
from discord.ext import commands
import json
import os


class ServerManager(commands.Cog):
    """서버 구조 관리 (채널, 권한, 카테고리)"""

    def __init__(self, bot):
        self.bot = bot

    async def create_channel(self, guild: discord.Guild, channel_name: str,
                             category_name: str = None, channel_type: str = "text"):
        """채널 생성"""
        try:
            # 카테고리 찾기
            category = None
            if category_name:
                for cat in guild.categories:
                    if cat.name.lower() == category_name.lower():
                        category = cat
                        break

            # 채널 생성
            if channel_type == "voice":
                channel = await guild.create_voice_channel(
                    name=channel_name,
                    category=category
                )
            else:
                channel = await guild.create_text_channel(
                    name=channel_name,
                    category=category
                )

            return {
                "success": True,
                "message": f"✅ '{channel_name}' 채널이 생성되었어요!"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"❌ 채널 생성 실패: {str(e)}"
            }

    async def delete_channel(self, guild: discord.Guild, channel_name: str):
        """채널 삭제"""
        try:
            # 채널 찾기
            channel = None
            for ch in guild.channels:
                if ch.name.lower() == channel_name.lower():
                    channel = ch
                    break

            if not channel:
                return {
                    "success": False,
                    "message": f"❌ '{channel_name}' 채널을 찾을 수 없어요."
                }

            await channel.delete()
            return {
                "success": True,
                "message": f"✅ '{channel_name}' 채널이 삭제되었어요!"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"❌ 채널 삭제 실패: {str(e)}"
            }

    async def change_permissions(self, guild: discord.Guild, channel_name: str,
                                 role_name: str, permission_type: str, allow: bool):
        """채널 권한 변경"""
        try:
            # 채널 찾기
            channel = None
            for ch in guild.channels:
                if ch.name.lower() == channel_name.lower():
                    channel = ch
                    break

            if not channel:
                return {
                    "success": False,
                    "message": f"❌ '{channel_name}' 채널을 찾을 수 없어요."
                }

            # 역할 찾기
            role = None
            if role_name.lower() == "@everyone":
                role = guild.default_role
            else:
                for r in guild.roles:
                    if r.name.lower() == role_name.lower():
                        role = r
                        break

            if not role:
                return {
                    "success": False,
                    "message": f"❌ '{role_name}' 역할을 찾을 수 없어요."
                }

            # 권한 맵핑
            permission_map = {
                "view": "view_channel",
                "send_messages": "send_messages",
                "read_messages": "view_channel",
                "connect": "connect",
                "speak": "speak",
                "manage": "manage_channels"
            }

            perm_key = permission_map.get(permission_type, permission_type)

            # 권한 설정
            perms = channel.permissions_for(role)
            if allow:
                await channel.set_permissions(role, **{perm_key: True})
                action = "허용"
            else:
                await channel.set_permissions(role, **{perm_key: False})
                action = "거부"

            return {
                "success": True,
                "message": f"✅ '{channel_name}' 채널에서 '{role_name}'의 '{permission_type}' 권한을 {action}했어요!"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"❌ 권한 변경 실패: {str(e)}"
            }

    async def move_channel(self, guild: discord.Guild, channel_name: str,
                           target_category: str):
        """채널을 다른 카테고리로 이동"""
        try:
            # 채널 찾기
            channel = None
            for ch in guild.channels:
                if ch.name.lower() == channel_name.lower():
                    channel = ch
                    break

            if not channel:
                return {
                    "success": False,
                    "message": f"❌ '{channel_name}' 채널을 찾을 수 없어요."
                }

            # 카테고리 찾기
            category = None
            for cat in guild.categories:
                if cat.name.lower() == target_category.lower():
                    category = cat
                    break

            if not category:
                return {
                    "success": False,
                    "message": f"❌ '{target_category}' 카테고리를 찾을 수 없어요."
                }

            # 채널 이동
            await channel.edit(category=category)
            return {
                "success": True,
                "message": f"✅ '{channel_name}' 채널이 '{target_category}' 카테고리로 이동했어요!"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"❌ 채널 이동 실패: {str(e)}"
            }

    async def sort_channels(self, guild: discord.Guild, category_name: str,
                            channel_order: list):
        """카테고리 내 채널 순서 정렬"""
        try:
            # 카테고리 찾기
            category = None
            for cat in guild.categories:
                if cat.name.lower() == category_name.lower():
                    category = cat
                    break

            if not category:
                return {
                    "success": False,
                    "message": f"❌ '{category_name}' 카테고리를 찾을 수 없어요."
                }

            # 채널들을 순서대로 정렬
            position = 0
            for channel_name in channel_order:
                for ch in category.channels:
                    if ch.name.lower() == channel_name.lower():
                        await ch.edit(position=position)
                        position += 1
                        break

            return {
                "success": True,
                "message": f"✅ '{category_name}' 카테고리의 채널이 정렬되었어요!"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"❌ 채널 정렬 실패: {str(e)}"
            }

    async def create_category(self, guild: discord.Guild, category_name: str):
        """카테고리 생성"""
        try:
            category = await guild.create_category(name=category_name)
            return {
                "success": True,
                "message": f"✅ '{category_name}' 카테고리가 생성되었어요!"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"❌ 카테고리 생성 실패: {str(e)}"
            }

    async def list_channels(self, guild: discord.Guild):
        """현재 서버의 채널과 카테고리 목록"""
        try:
            info = "📋 **서버 구조:**\n\n"

            # 카테고리별 정렬
            for category in guild.categories:
                info += f"📁 **{category.name}**\n"
                for channel in category.channels:
                    icon = "🔊" if isinstance(channel, discord.VoiceChannel) else "💬"
                    info += f"  {icon} {channel.name}\n"
                info += "\n"

            # 카테고리 없는 채널
            uncategorized = [ch for ch in guild.channels if ch.category is None]
            if uncategorized:
                info += "📁 **카테고리 없음**\n"
                for channel in uncategorized:
                    icon = "🔊" if isinstance(channel, discord.VoiceChannel) else "💬"
                    info += f"  {icon} {channel.name}\n"

            return {
                "success": True,
                "message": info
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"❌ 조회 실패: {str(e)}"
            }

    # ========== 역할 관리 ==========
    async def create_role(self, guild: discord.Guild, role_name: str, color: str = None):
        """역할 생성"""
        try:
            # 색상 변환
            role_color = discord.Color.default()
            if color:
                color_map = {
                    "빨강": discord.Color.red(),
                    "파랑": discord.Color.blue(),
                    "초록": discord.Color.green(),
                    "노랑": discord.Color.yellow(),
                    "보라": discord.Color.purple(),
                    "주황": discord.Color.orange(),
                    "분홍": discord.Color.pink(),
                }
                role_color = color_map.get(color.lower(), discord.Color.default())

            role = await guild.create_role(name=role_name, color=role_color)
            return {
                "success": True,
                "message": f"✅ '{role_name}' 역할이 생성되었어요!"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"❌ 역할 생성 실패: {str(e)}"
            }

    async def delete_role(self, guild: discord.Guild, role_name: str):
        """역할 삭제"""
        try:
            role = None
            for r in guild.roles:
                if r.name.lower() == role_name.lower():
                    role = r
                    break

            if not role:
                return {
                    "success": False,
                    "message": f"❌ '{role_name}' 역할을 찾을 수 없어요."
                }

            await role.delete()
            return {
                "success": True,
                "message": f"✅ '{role_name}' 역할이 삭제되었어요!"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"❌ 역할 삭제 실패: {str(e)}"
            }

    async def list_roles(self, guild: discord.Guild):
        """모든 역할 나열"""
        try:
            info = "📋 **서버 역할:**\n\n"
            for role in guild.roles:
                if role.name != "@everyone":
                    info += f"🎭 {role.name}\n"

            return {
                "success": True,
                "message": info if info != "📋 **서버 역할:**\n\n" else "역할이 없어요."
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"❌ 조회 실패: {str(e)}"
            }

    # ========== 멤버 역할 관리 ==========
    async def add_member_role(self, guild: discord.Guild, member_name: str, role_name: str):
        """멤버에게 역할 부여"""
        try:
            # 멤버 찾기
            member = None
            for m in guild.members:
                if m.name.lower() == member_name.lower() or m.display_name.lower() == member_name.lower():
                    member = m
                    break

            if not member:
                return {
                    "success": False,
                    "message": f"❌ '{member_name}' 멤버를 찾을 수 없어요."
                }

            # 역할 찾기
            role = None
            for r in guild.roles:
                if r.name.lower() == role_name.lower():
                    role = r
                    break

            if not role:
                return {
                    "success": False,
                    "message": f"❌ '{role_name}' 역할을 찾을 수 없어요."
                }

            await member.add_roles(role)
            return {
                "success": True,
                "message": f"✅ {member_name}에게 '{role_name}' 역할을 부여했어요!"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"❌ 역할 부여 실패: {str(e)}"
            }

    async def remove_member_role(self, guild: discord.Guild, member_name: str, role_name: str):
        """멤버에게서 역할 제거"""
        try:
            # 멤버 찾기
            member = None
            for m in guild.members:
                if m.name.lower() == member_name.lower() or m.display_name.lower() == member_name.lower():
                    member = m
                    break

            if not member:
                return {
                    "success": False,
                    "message": f"❌ '{member_name}' 멤버를 찾을 수 없어요."
                }

            # 역할 찾기
            role = None
            for r in guild.roles:
                if r.name.lower() == role_name.lower():
                    role = r
                    break

            if not role:
                return {
                    "success": False,
                    "message": f"❌ '{role_name}' 역할을 찾을 수 없어요."
                }

            await member.remove_roles(role)
            return {
                "success": True,
                "message": f"✅ {member_name}에게서 '{role_name}' 역할을 제거했어요!"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"❌ 역할 제거 실패: {str(e)}"
            }

    # ========== 채널 순서 정렬 ==========
    async def sort_channels_by_category(self, guild: discord.Guild, category_name: str, channel_order: list):
        """카테고리 내 채널 순서 정렬"""
        try:
            # 카테고리 찾기
            category = None
            for cat in guild.categories:
                if cat.name.lower() == category_name.lower():
                    category = cat
                    break

            if not category:
                return {
                    "success": False,
                    "message": f"❌ '{category_name}' 카테고리를 찾을 수 없어요."
                }

            # 채널들을 순서대로 정렬
            position = 0
            for channel_name in channel_order:
                for ch in category.channels:
                    if ch.name.lower() == channel_name.lower():
                        await ch.edit(position=position)
                        position += 1
                        break

            return {
                "success": True,
                "message": f"✅ '{category_name}' 카테고리의 채널이 정렬되었어요!"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"❌ 채널 정렬 실패: {str(e)}"
            }

    # ========== 핸들(슬러그) 변경 ==========
    async def change_server_name(self, guild: discord.Guild, new_name: str):
        """서버 이름 변경"""
        try:
            await guild.edit(name=new_name)
            return {
                "success": True,
                "message": f"✅ 서버 이름을 '{new_name}'으로 변경했어요!"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"❌ 서버 이름 변경 실패: {str(e)}"
            }

    # ========== 서버 설정 ==========
    async def change_server_description(self, guild: discord.Guild, description: str):
        """서버 설명 변경"""
        try:
            await guild.edit(description=description)
            return {
                "success": True,
                "message": f"✅ 서버 설명을 변경했어요!"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"❌ 서버 설명 변경 실패: {str(e)}"
            }

    async def change_server_icon(self, guild: discord.Guild, icon_emoji: str):
        """서버 아이콘 변경 (이모지 형태)"""
        try:
            # 현재 Discord API로는 이미지 파일만 지원하므로
            # 이모지 형태로는 변경 불가능
            return {
                "success": False,
                "message": "❌ 서버 아이콘은 이미지 파일로만 변경 가능해요."
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"❌ 서버 아이콘 변경 실패: {str(e)}"
            }

    # ========== 메시지 핀 고정 ==========
    async def pin_message(self, guild: discord.Guild, channel_name: str, message_content: str):
        """메시지 핀 고정 (특정 내용의 최근 메시지)"""
        try:
            # 채널 찾기
            channel = None
            for ch in guild.channels:
                if ch.name.lower() == channel_name.lower() and isinstance(ch, discord.TextChannel):
                    channel = ch
                    break

            if not channel:
                return {
                    "success": False,
                    "message": f"❌ '{channel_name}' 채널을 찾을 수 없어요."
                }

            # 메시지 찾기
            async for message in channel.history(limit=50):
                if message_content.lower() in message.content.lower():
                    await message.pin()
                    return {
                        "success": True,
                        "message": f"✅ '{channel_name}' 채널의 메시지를 핀 고정했어요!"
                    }

            return {
                "success": False,
                "message": f"❌ '{message_content}'를 포함한 메시지를 찾을 수 없어요."
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"❌ 메시지 핀 고정 실패: {str(e)}"
            }

    async def unpin_message(self, guild: discord.Guild, channel_name: str, message_content: str):
        """메시지 핀 해제"""
        try:
            # 채널 찾기
            channel = None
            for ch in guild.channels:
                if ch.name.lower() == channel_name.lower() and isinstance(ch, discord.TextChannel):
                    channel = ch
                    break

            if not channel:
                return {
                    "success": False,
                    "message": f"❌ '{channel_name}' 채널을 찾을 수 없어요."
                }

            # 핀 고정된 메시지 중에서 찾기
            pinned = await channel.pins()
            for message in pinned:
                if message_content.lower() in message.content.lower():
                    await message.unpin()
                    return {
                        "success": True,
                        "message": f"✅ '{channel_name}' 채널의 메시지 핀을 해제했어요!"
                    }

            return {
                "success": False,
                "message": f"❌ 핀 고정된 메시지를 찾을 수 없어요."
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"❌ 메시지 핀 해제 실패: {str(e)}"
            }

    # ========== 스레드 생성 ==========
    async def create_thread(self, guild: discord.Guild, channel_name: str, thread_name: str,
                            message_content: str = None):
        """스레드 생성"""
        try:
            # 채널 찾기
            channel = None
            for ch in guild.channels:
                if ch.name.lower() == channel_name.lower() and isinstance(ch, discord.TextChannel):
                    channel = ch
                    break

            if not channel:
                return {
                    "success": False,
                    "message": f"❌ '{channel_name}' 채널을 찾을 수 없어요."
                }

            # 메시지가 지정되지 않으면 새 메시지 생성 후 스레드 생성
            if message_content:
                # 특정 메시지에서 스레드 생성
                async for message in channel.history(limit=50):
                    if message_content.lower() in message.content.lower():
                        thread = await message.create_thread(name=thread_name)
                        return {
                            "success": True,
                            "message": f"✅ '{thread_name}' 스레드가 생성되었어요!"
                        }
                return {
                    "success": False,
                    "message": f"❌ '{message_content}'를 포함한 메시지를 찾을 수 없어요."
                }
            else:
                # 새 메시지 생성 후 스레드 생성
                msg = await channel.send(f"🧵 **{thread_name}** 스레드가 시작되었어요!")
                thread = await msg.create_thread(name=thread_name)
                return {
                    "success": True,
                    "message": f"✅ '{thread_name}' 스레드가 생성되었어요!"
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"❌ 스레드 생성 실패: {str(e)}"
            }

    async def close_thread(self, guild: discord.Guild, channel_name: str, thread_name: str):
        """스레드 종료"""
        try:
            # 채널 찾기
            channel = None
            for ch in guild.channels:
                if ch.name.lower() == channel_name.lower() and isinstance(ch, discord.TextChannel):
                    channel = ch
                    break

            if not channel:
                return {
                    "success": False,
                    "message": f"❌ '{channel_name}' 채널을 찾을 수 없어요."
                }

            # 스레드 찾기
            async for thread in channel.archived_threads():
                if thread.name.lower() == thread_name.lower():
                    await thread.edit(archived=True)
                    return {
                        "success": True,
                        "message": f"✅ '{thread_name}' 스레드를 종료했어요!"
                    }

            # 활성 스레드에서도 찾기
            for thread in channel.threads:
                if thread.name.lower() == thread_name.lower():
                    await thread.edit(archived=True)
                    return {
                        "success": True,
                        "message": f"✅ '{thread_name}' 스레드를 종료했어요!"
                    }

            return {
                "success": False,
                "message": f"❌ '{thread_name}' 스레드를 찾을 수 없어요."
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"❌ 스레드 종료 실패: {str(e)}"
            }


async def setup(bot):
    await bot.add_cog(ServerManager(bot))