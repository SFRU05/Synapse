import discord
from discord.ext import commands
from discord import ui
from openai import OpenAI
import json
import os
from pathlib import Path
import asyncio
from dotenv import load_dotenv
from duckduckgo_search import DDGS

load_dotenv()

# 개발자 ID 설정 (모든 서버에서 사용 가능)
DEVELOPER_IDS = [123456789, 987654321]


class ConfirmView(ui.View):
    """서버 관리 기능 일괄 실행 전 사용자 재확인 버튼 UI"""

    def __init__(self, requester_id, timeout=60):
        super().__init__(timeout=timeout)
        self.requester_id = requester_id
        self.confirmed = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # 명령을 요청한 본인만 버튼을 클릭할 수 있도록 제한
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message("❌ 요청한 사용자만 승인/취소할 수 있어요!", ephemeral=True)
            return False
        return True

    @ui.button(label="✅ 전체 승인", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        self.confirmed = True
        self.stop()
        # 나만 볼 수 있는 에페메럴 메시지
        await interaction.response.send_message("✅ 요청을 승인했어요. 작업을 진행합니다!", ephemeral=True)

    @ui.button(label="❌ 전체 취소", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        self.confirmed = False
        self.stop()
        # 나만 볼 수 있는 에페메럴 메시지
        await interaction.response.send_message("❌ 요청을 취소했어요.", ephemeral=True)


class SettingsView(ui.View):
    """챗봇 설정 UI"""

    def __init__(self, cog, guild_id):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id

    @ui.button(label="🌐 웹 검색", style=discord.ButtonStyle.primary)
    async def web_search_button(self, interaction: discord.Interaction, button: ui.Button):
        is_enabled = self.cog.toggle_web_search(self.guild_id)
        button.label = "🌐 웹 검색" + (" ✅" if is_enabled else " ❌")

        embed = self.cog.get_settings_embed(self.guild_id)
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="💾 저장", style=discord.ButtonStyle.success)
    async def save_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        await interaction.followup.send("✅ 설정이 저장되었어요!", ephemeral=True)
        self.stop()

    @ui.button(label="❌ 취소", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        self.stop()


class ChatBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.config_file = Path("server_config.json")
        self.load_config()
        self.bot_names = ["시냅아", "설탕아"]
        self.conversations = {}

        # 함수 및 매개변수 이름을 한국어로 매핑하는 사전
        self.function_names_kr = {
            "create_channel": "채널 생성",
            "delete_channel": "채널 삭제",
            "change_permissions": "권한 변경",
            "move_channel": "채널 이동",
            "create_category": "카테고리 생성",
            "create_role": "역할 생성",
            "delete_role": "역할 삭제",
            "add_member_role": "멤버 역할 부여",
            "remove_member_role": "멤버 역할 제거",
            "sort_channels_by_category": "채널 정렬",
            "change_server_name": "서버 이름 변경",
            "change_server_description": "서버 설명 변경",
            "pin_message": "메시지 고정",
            "unpin_message": "메시지 고정 해제",
            "create_thread": "스레드 생성",
            "close_thread": "스레드 종료"
        }

        self.param_names_kr = {
            "channel_name": "채널 이름",
            "category_name": "카테고리 이름",
            "channel_type": "채널 종류",
            "role_name": "역할 이름",
            "permission_type": "권한 종류",
            "allow": "허용 여부",
            "target_category": "이동할 카테고리",
            "color": "색상",
            "member_name": "멤버 이름",
            "channel_order": "채널 순서",
            "new_name": "새 서버 이름",
            "description": "설명",
            "message_content": "메시지 내용",
            "thread_name": "스레드 이름"
        }

    def load_config(self):
        if self.config_file.exists():
            with open(self.config_file, "r", encoding="utf-8") as f:
                self.config = json.load(f)
        else:
            self.config = {}
            self.save_config()

    def save_config(self):
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def is_enabled(self, guild_id):
        guild_id = str(guild_id)
        if guild_id not in self.config:
            self.config[guild_id] = {
                "enabled": True,
                "web_search": False,
                "disabled_by_dev": False
            }
            self.save_config()
        return self.config[guild_id].get("enabled", True)

    def is_web_search_enabled(self, guild_id):
        guild_id = str(guild_id)
        if guild_id not in self.config:
            return False
        return self.config[guild_id].get("web_search", False)

    def toggle_web_search(self, guild_id):
        guild_id = str(guild_id)
        if guild_id not in self.config:
            self.config[guild_id] = {"enabled": True, "web_search": False, "disabled_by_dev": False}
        self.config[guild_id]["web_search"] = not self.config[guild_id].get("web_search", False)
        self.save_config()
        return self.config[guild_id]["web_search"]

    def toggle(self, guild_id, status, disabled_by_dev=False):
        guild_id = str(guild_id)
        self.config[guild_id] = {
            "enabled": status,
            "web_search": self.config.get(guild_id, {}).get("web_search", False),
            "disabled_by_dev": disabled_by_dev if not status else False
        }
        self.save_config()

    def is_developer(self, user_id):
        return user_id in DEVELOPER_IDS

    def is_disabled_by_dev(self, guild_id):
        guild_id = str(guild_id)
        if guild_id not in self.config:
            return False
        return self.config[guild_id].get("disabled_by_dev", False)

    def get_settings_embed(self, guild_id):
        guild_id = str(guild_id)
        config = self.config.get(guild_id, {})

        embed = discord.Embed(
            title="⚙️ 챗봇 설정",
            description="아래 버튼으로 설정을 변경할 수 있어요!",
            color=discord.Color.blurple()
        )

        status = "✅ 활성화" if config.get("enabled", True) else "❌ 비활성화"
        web_search = "✅ ON" if config.get("web_search", False) else "❌ OFF"
        dev_disabled = "🔒 YES" if config.get("disabled_by_dev", False) else "❌ NO"

        embed.add_field(name="🤖 챗봇 상태", value=status, inline=False)
        embed.add_field(name="🌐 웹 검색", value=web_search, inline=True)
        embed.add_field(name="🔐 개발자 비활성화", value=dev_disabled, inline=True)
        embed.set_footer(text="설정은 자동으로 저장됩니다.")

        return embed

    def _conv_key(self, message: discord.Message, trigger_type: str = None):
        if trigger_type == "reply":
            return (message.guild.id, message.channel.id, message.author.id, "reply")
        else:
            return (message.guild.id, message.channel.id, message.author.id, "new")

    def _get_history(self, key):
        return self.conversations.setdefault(key, [])

    def _trim_history(self, history, max_turns=10):
        max_messages = max_turns * 2
        if len(history) > max_messages:
            del history[: len(history) - max_messages]

    def sanitize_text(self, text: str) -> str:
        """@everyone 및 @here 멘션 방지를 위해 Zero-Width Space(\\u200b) 추가"""
        if not text:
            return text
        return text.replace("@everyone", "@\u200beveryone").replace("@here", "@\u200bhere")

    def search_web(self, query):
        try:
            ddgs = DDGS()
            results = ddgs.text(query, max_results=3)

            search_results = ""
            for i, result in enumerate(results, 1):
                search_results += f"{i}. {result['title']}\n   {result['body']}\n"

            return search_results if search_results else "검색 결과가 없어요."
        except Exception as e:
            return f"검색 중 오류가 발생했어요: {str(e)}"

    def format_args_kr(self, args: dict) -> str:
        """JSON 인자를 읽기 쉬운 한국어 텍스트 패러그래프로 변환"""
        formatted_list = []
        for key, val in args.items():
            kr_key = self.param_names_kr.get(key, key)

            if key == "channel_type":
                val = "음성 채널" if val == "voice" else "텍스트 채널"
            elif key == "allow":
                val = "허용" if val else "거부"

            formatted_list.append(f"• **{kr_key}**: {val}")
        return "\n".join(formatted_list)

    def get_tools(self):
        return [
            # ========== 권한 조회 (관리자 전용) ==========
            {
                "type": "function",
                "function": {
                    "name": "get_role_permissions",
                    "description": "특정 역할에 할당된 권한들을 조회합니다 (관리자 전용)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "role_name": {"type": "string", "description": "조회할 역할 이름"}
                        },
                        "required": ["role_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_channel_permissions",
                    "description": "특정 채널에 설정된 역할별 권한(Overwrite) 상태를 조회합니다 (관리자 전용)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel_name": {"type": "string", "description": "조회할 채널 이름"}
                        },
                        "required": ["channel_name"]
                    }
                }
            },
            # ========== 채널 관리 ==========
            {
                "type": "function",
                "function": {
                    "name": "create_channel",
                    "description": "새로운 텍스트 또는 음성 채널을 생성합니다",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel_name": {"type": "string", "description": "채널 이름"},
                            "category_name": {"type": "string", "description": "카테고리 이름 (선택)"},
                            "channel_type": {"type": "string", "enum": ["text", "voice"], "description": "채널 종류"}
                        },
                        "required": ["channel_name", "channel_type"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "delete_channel",
                    "description": "채널을 삭제합니다",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel_name": {"type": "string", "description": "삭제할 채널 이름"}
                        },
                        "required": ["channel_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "change_permissions",
                    "description": "채널의 특정 역할에 대한 권한을 변경합니다",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel_name": {"type": "string", "description": "채널 이름"},
                            "role_name": {"type": "string", "description": "역할 이름 (예: '관리자', '@everyone')"},
                            "permission_type": {"type": "string",
                                                "enum": ["view", "send_messages", "connect", "speak", "manage"],
                                                "description": "권한 종류"},
                            "allow": {"type": "boolean", "description": "true: 허용, false: 거부"}
                        },
                        "required": ["channel_name", "role_name", "permission_type", "allow"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "move_channel",
                    "description": "채널을 다른 카테고리로 이동합니다",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel_name": {"type": "string", "description": "이동할 채널 이름"},
                            "target_category": {"type": "string", "description": "목표 카테고리 이름"}
                        },
                        "required": ["channel_name", "target_category"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "create_category",
                    "description": "새로운 카테고리를 생성합니다",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category_name": {"type": "string", "description": "카테고리 이름"}
                        },
                        "required": ["category_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_channels",
                    "description": "현재 서버의 모든 채널과 카테고리를 나열합니다",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            # ========== 역할 관리 ==========
            {
                "type": "function",
                "function": {
                    "name": "create_role",
                    "description": "새로운 역할을 생성합니다",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "role_name": {"type": "string", "description": "역할 이름"},
                            "color": {"type": "string", "enum": ["빨강", "파랑", "초록", "노랑", "보라", "주황", "분홍"],
                                      "description": "역할 색상 (선택)"}
                        },
                        "required": ["role_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "delete_role",
                    "description": "역할을 삭제합니다",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "role_name": {"type": "string", "description": "삭제할 역할 이름"}
                        },
                        "required": ["role_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_roles",
                    "description": "서버의 모든 역할을 나열합니다",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            # ========== 멤버 역할 관리 ==========
            {
                "type": "function",
                "function": {
                    "name": "add_member_role",
                    "description": "멤버에게 역할을 부여합니다",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "member_name": {"type": "string", "description": "멤버 이름"},
                            "role_name": {"type": "string", "description": "부여할 역할 이름"}
                        },
                        "required": ["member_name", "role_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "remove_member_role",
                    "description": "멤버에게서 역할을 제거합니다",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "member_name": {"type": "string", "description": "멤버 이름"},
                            "role_name": {"type": "string", "description": "제거할 역할 이름"}
                        },
                        "required": ["member_name", "role_name"]
                    }
                }
            },
            # ========== 채널 정렬 ==========
            {
                "type": "function",
                "function": {
                    "name": "sort_channels_by_category",
                    "description": "카테고리 내의 채널을 지정된 순서로 정렬합니다",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category_name": {"type": "string", "description": "카테고리 이름"},
                            "channel_order": {"type": "array", "items": {"type": "string"},
                                              "description": "채널 이름들의 순서 (예: ['공지', '일반', '자유'])"}
                        },
                        "required": ["category_name", "channel_order"]
                    }
                }
            },
            # ========== 서버 설정 ==========
            {
                "type": "function",
                "function": {
                    "name": "change_server_name",
                    "description": "서버 이름을 변경합니다",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "new_name": {"type": "string", "description": "새로운 서버 이름"}
                        },
                        "required": ["new_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "change_server_description",
                    "description": "서버 설명을 변경합니다",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string", "description": "새로운 서버 설명"}
                        },
                        "required": ["description"]
                    }
                }
            },
            # ========== 메시지 핀 ==========
            {
                "type": "function",
                "function": {
                    "name": "pin_message",
                    "description": "메시지를 핀 고정합니다",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel_name": {"type": "string", "description": "채널 이름"},
                            "message_content": {"type": "string", "description": "핀 고정할 메시지 내용 (일부)"}
                        },
                        "required": ["channel_name", "message_content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "unpin_message",
                    "description": "핀 고정된 메시지를 해제합니다",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel_name": {"type": "string", "description": "채널 이름"},
                            "message_content": {"type": "string", "description": "핀 해제할 메시지 내용 (일부)"}
                        },
                        "required": ["channel_name", "message_content"]
                    }
                }
            },
            # ========== 스레드 ==========
            {
                "type": "function",
                "function": {
                    "name": "create_thread",
                    "description": "새로운 스레드를 생성합니다",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel_name": {"type": "string", "description": "스레드를 만들 채널 이름"},
                            "thread_name": {"type": "string", "description": "스레드 이름"},
                            "message_content": {"type": "string", "description": "기존 메시지에 스레드 생성 (선택)"}
                        },
                        "required": ["channel_name", "thread_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "close_thread",
                    "description": "스레드를 종료합니다",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel_name": {"type": "string", "description": "스레드가 있는 채널 이름"},
                            "thread_name": {"type": "string", "description": "종료할 스레드 이름"}
                        },
                        "required": ["channel_name", "thread_name"]
                    }
                }
            }
        ]

    async def execute_server_function(self, guild: discord.Guild, function_name: str, arguments: dict):
        """서버 관리 및 권한 조회 함수 실행"""
        server_manager = self.bot.get_cog("ServerManager")

        # 1) 권한 조회 (역할)
        if function_name == "get_role_permissions":
            role_name = arguments.get("role_name")
            role = discord.utils.get(guild.roles, name=role_name)
            if not role:
                return {"success": False, "message": f"'{role_name}' 역할을 찾을 수 없어요."}

            perms = [perm_name for perm_name, value in role.permissions if value]
            return {
                "success": True,
                "role_name": role.name,
                "permissions": perms if perms else ["기본 권한만 허용되어 있음"]
            }

        # 2) 권한 조회 (채널)
        elif function_name == "get_channel_permissions":
            channel_name = arguments.get("channel_name")
            channel = discord.utils.get(guild.channels, name=channel_name)
            if not channel:
                return {"success": False, "message": f"'{channel_name}' 채널을 찾을 수 없어요."}

            overwrites_info = []
            for target, overwrite in channel.overwrites.items():
                allow, deny = overwrite.pair()
                allowed_perms = [perm for perm, val in allow if val]
                denied_perms = [perm for perm, val in deny if val]

                overwrites_info.append({
                    "대상": target.name,
                    "허용된_권한": allowed_perms,
                    "거부된_권한": denied_perms
                })

            return {
                "success": True,
                "channel_name": channel.name,
                "overwrites": overwrites_info if overwrites_info else ["특별히 설정된 역할/멤버별 권한 덮어쓰기가 없어요."]
            }

        if not server_manager:
            return {"success": False, "message": "서버 관리 기능을 사용할 수 없어요."}

        # 채널 관리
        if function_name == "create_channel":
            return await server_manager.create_channel(
                guild,
                arguments.get("channel_name"),
                arguments.get("category_name"),
                arguments.get("channel_type", "text")
            )
        elif function_name == "delete_channel":
            return await server_manager.delete_channel(guild, arguments.get("channel_name"))
        elif function_name == "change_permissions":
            return await server_manager.change_permissions(
                guild,
                arguments.get("channel_name"),
                arguments.get("role_name"),
                arguments.get("permission_type"),
                arguments.get("allow")
            )
        elif function_name == "move_channel":
            return await server_manager.move_channel(
                guild,
                arguments.get("channel_name"),
                arguments.get("target_category")
            )
        elif function_name == "create_category":
            return await server_manager.create_category(guild, arguments.get("category_name"))
        elif function_name == "list_channels":
            return await server_manager.list_channels(guild)

        # 역할 관리
        elif function_name == "create_role":
            return await server_manager.create_role(
                guild,
                arguments.get("role_name"),
                arguments.get("color")
            )
        elif function_name == "delete_role":
            return await server_manager.delete_role(guild, arguments.get("role_name"))
        elif function_name == "list_roles":
            return await server_manager.list_roles(guild)

        # 멤버 역할 관리
        elif function_name == "add_member_role":
            return await server_manager.add_member_role(
                guild,
                arguments.get("member_name"),
                arguments.get("role_name")
            )
        elif function_name == "remove_member_role":
            return await server_manager.remove_member_role(
                guild,
                arguments.get("member_name"),
                arguments.get("role_name")
            )

        # 채널 정렬
        elif function_name == "sort_channels_by_category":
            return await server_manager.sort_channels_by_category(
                guild,
                arguments.get("category_name"),
                arguments.get("channel_order")
            )

        # 서버 설정
        elif function_name == "change_server_name":
            return await server_manager.change_server_name(guild, arguments.get("new_name"))
        elif function_name == "change_server_description":
            return await server_manager.change_server_description(guild, arguments.get("description"))

        # 메시지 핀
        elif function_name == "pin_message":
            return await server_manager.pin_message(
                guild,
                arguments.get("channel_name"),
                arguments.get("message_content")
            )
        elif function_name == "unpin_message":
            return await server_manager.unpin_message(
                guild,
                arguments.get("channel_name"),
                arguments.get("message_content")
            )

        # 스레드
        elif function_name == "create_thread":
            return await server_manager.create_thread(
                guild,
                arguments.get("channel_name"),
                arguments.get("thread_name"),
                arguments.get("message_content")
            )
        elif function_name == "close_thread":
            return await server_manager.close_thread(
                guild,
                arguments.get("channel_name"),
                arguments.get("thread_name")
            )

        return {"success": False, "message": "알 수 없는 함수입니다."}

    async def get_response_realtime(self, key, user_message, discord_message: discord.Message, guild_id,
                                    guild: discord.Guild, author: discord.Member):
        """실시간 스트리밍 답변 및 서버 관리 권한 검증 / 승인 재확인 버튼 UI 제공"""
        try:
            history = self._get_history(key)
            web_search_enabled = self.is_web_search_enabled(guild_id)
            web_search_info = ""

            system_content = (
                "너는 16살 한국 여자 캐릭터야. "
                "존댓말로 다정하게 대답해."
                "\n\n사용자가 서버 구조를 변경하거나 권한/채널 정보를 알고 싶으면 함수를 사용해서 도와줘."
            )

            if web_search_enabled:
                web_search_info = f"\n\n[웹 검색 결과]\n{self.search_web(user_message)}"
                system_content += "\n\n사용자가 웹 검색 결과를 제공했으면 그 정보를 바탕으로 답변해."

            messages = [{"role": "system", "content": system_content}]

            if len(history) > 20:
                messages.extend(history[-20:])
            else:
                messages.extend(history)

            messages.append({"role": "user", "content": user_message + web_search_info})

            allowed_mentions = discord.AllowedMentions(everyone=False, roles=False)

            while True:
                stream = await asyncio.to_thread(
                    self.client.chat.completions.create,
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=1,
                    tools=self.get_tools(),
                    tool_choice="auto",
                    stream=True
                )

                tool_calls_builder = {}
                full_content = ""
                last_update = asyncio.get_event_loop().time()

                for chunk in stream:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if not delta:
                        continue

                    if delta.content:
                        full_content += delta.content
                        now = asyncio.get_event_loop().time()
                        # 0.5초 주기로 실시간 스트리밍 답변 업데이트
                        if now - last_update > 0.5:
                            try:
                                safe_text = self.sanitize_text(full_content[:2000])
                                await discord_message.edit(
                                    content=safe_text,
                                    allowed_mentions=allowed_mentions
                                )
                                last_update = now
                            except Exception:
                                pass

                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in tool_calls_builder:
                                tool_calls_builder[idx] = {
                                    "id": tc.id or "",
                                    "name": tc.function.name or "" if tc.function else "",
                                    "arguments": tc.function.arguments or "" if tc.function else ""
                                }
                            else:
                                if tc.id:
                                    tool_calls_builder[idx]["id"] += tc.id
                                if tc.function and tc.function.name:
                                    tool_calls_builder[idx]["name"] += tc.function.name
                                if tc.function and tc.function.arguments:
                                    tool_calls_builder[idx]["arguments"] += tc.function.arguments

                if not tool_calls_builder:
                    final_answer = full_content if full_content else "..."
                    final_answer = self.sanitize_text(final_answer)

                    if len(final_answer) > 2000:
                        chunks = [final_answer[i:i + 2000] for i in range(0, len(final_answer), 2000)]
                        await discord_message.edit(
                            content=chunks[0],
                            allowed_mentions=allowed_mentions
                        )
                        for chunk in chunks[1:]:
                            await discord_message.reply(
                                chunk,
                                mention_author=False,
                                allowed_mentions=allowed_mentions
                            )
                    else:
                        await discord_message.edit(
                            content=final_answer,
                            allowed_mentions=allowed_mentions
                        )

                    history.append({"role": "user", "content": user_message})
                    history.append({"role": "assistant", "content": final_answer})
                    self._trim_history(history, max_turns=10)
                    break

                tool_calls = [
                    {
                        "id": v["id"],
                        "type": "function",
                        "function": {"name": v["name"], "arguments": v["arguments"]}
                    }
                    for v in tool_calls_builder.values()
                ]

                messages.append({
                    "role": "assistant",
                    "content": full_content if full_content else None,
                    "tool_calls": tool_calls
                })

                # 관리자 승인이 필요한 함수와 즉시 실행 가능한 함수 분류
                admin_required_calls = []
                read_only_calls = []

                read_only_functions = ["list_channels", "list_roles", "get_role_permissions", "get_channel_permissions"]

                for tc in tool_calls:
                    fn_name = tc["function"]["name"]
                    if fn_name in read_only_functions:
                        read_only_calls.append(tc)
                    else:
                        admin_required_calls.append(tc)

                # 1) 단순 조회 및 권한 조회 기능 실행 (버튼 승인 없음)
                for tc in read_only_calls:
                    fn_name = tc["function"]["name"]
                    args = json.loads(tc["function"]["arguments"])

                    # 권한 조회 기능은 버튼 승인은 생략하되, '관리자' 권한 여부는 필수 체크
                    if fn_name in ["get_role_permissions", "get_channel_permissions"]:
                        is_admin = author.guild_permissions.administrator
                        is_dev = self.is_developer(author.id)

                        if not (is_admin or is_dev):
                            result = {"success": False, "message": "❌ 권한 조회 기능은 관리자만 사용할 수 있어요!"}
                        else:
                            result = await self.execute_server_function(guild, fn_name, args)
                    else:
                        result = await self.execute_server_function(guild, fn_name, args)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": json.dumps(result, ensure_ascii=False)
                    })

                # 2) 서버 구조 변경 작업 일괄 승인 진행 (버튼 승인 필수)
                if admin_required_calls:
                    is_admin = author.guild_permissions.administrator
                    is_dev = self.is_developer(author.id)

                    if not (is_admin or is_dev):
                        for tc in admin_required_calls:
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": json.dumps(
                                    {"success": False, "message": "권한이 없습니다. 관리자만 서버 관리 기능을 사용할 수 있어요!"},
                                    ensure_ascii=False)
                            })
                    else:
                        embed = discord.Embed(
                            title="⚠️ 서버 변경 요청 확인",
                            description="AI가 아래 항목들을 일괄로 실행하려고 합니다. 확인 후 승인해주세요.",
                            color=discord.Color.gold()
                        )

                        for idx, tc in enumerate(admin_required_calls, 1):
                            fn_name = tc["function"]["name"]
                            args = json.loads(tc["function"]["arguments"])

                            kr_fn_name = self.function_names_kr.get(fn_name, fn_name)
                            kr_args_text = self.format_args_kr(args)

                            embed.add_field(
                                name=f"{idx}. {kr_fn_name}",
                                value=kr_args_text if kr_args_text else "설정 항목 없음",
                                inline=False
                            )

                        view = ConfirmView(requester_id=author.id, timeout=60)
                        confirm_msg = await discord_message.reply(embed=embed, view=view)

                        await view.wait()

                        if view.confirmed is True:
                            await confirm_msg.delete()
                            for tc in admin_required_calls:
                                fn_name = tc["function"]["name"]
                                args = json.loads(tc["function"]["arguments"])
                                result = await self.execute_server_function(guild, fn_name, args)

                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc["id"],
                                    "content": json.dumps(result, ensure_ascii=False)
                                })
                        else:
                            await confirm_msg.delete()
                            for tc in admin_required_calls:
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc["id"],
                                    "content": json.dumps(
                                        {"success": False, "message": "사용자가 해당 작업을 취소하였거나 요청 시간이 초과되었습니다."},
                                        ensure_ascii=False)
                                })

                await discord_message.edit(content="⚙️ 실행 결과를 바탕으로 답변을 정리하고 있어요...")

        except Exception as e:
            error_msg = f"죄송해요. 오류가 발생했어요: {str(e)}"
            try:
                await discord_message.edit(content=error_msg)
            except Exception:
                pass
            return error_msg

    async def _is_reply_to_bot(self, message: discord.Message) -> bool:
        if not message.reference:
            return False

        resolved = message.reference.resolved
        if isinstance(resolved, discord.Message):
            return resolved.author.id == self.bot.user.id

        if message.reference.message_id:
            try:
                replied = await message.channel.fetch_message(message.reference.message_id)
                return replied.author.id == self.bot.user.id
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                return False

        return False

    async def extract_message(self, message: discord.Message):
        if self.bot.user in message.mentions:
            content = message.content
            for mention in message.mentions:
                content = (
                    content.replace(f"<@{mention.id}>", "")
                    .replace(f"<@!{mention.id}>", "")
                    .strip()
                )
            return (content if content else None), "mention"

        for name in self.bot_names:
            if message.content.startswith(name):
                content = message.content[len(name):].strip()
                return (content if content else None), "name"

        if await self._is_reply_to_bot(message):
            content = message.content.strip()
            return (content if content else None), "reply"

        return None, None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if not message.guild:
            return

        if not self.is_enabled(message.guild.id):
            return

        user_message, trigger_type = await self.extract_message(message)

        if user_message is None and trigger_type in ("mention", "name", "reply"):
            async with message.channel.typing():
                await message.reply("네? 부르셨어요?", mention_author=False)
            return

        if user_message is not None:
            async with message.channel.typing():
                key = self._conv_key(message, trigger_type)
                reply_message = await message.reply("⏳ 생각하고 있어요...", mention_author=False)
                await self.get_response_realtime(
                    key,
                    user_message,
                    reply_message,
                    message.guild.id,
                    message.guild,
                    message.author
                )

    @commands.command()
    async def enable_ai(self, ctx):
        is_dev = self.is_developer(ctx.author.id)
        is_admin = ctx.author.guild_permissions.administrator
        is_dev_disabled = self.is_disabled_by_dev(ctx.guild.id)

        if is_dev_disabled and not is_dev:
            await ctx.send("❌ 개발자가 비활성화했습니다. 개발자만 활성화할 수 있어요!")
            return

        if not (is_dev or is_admin):
            await ctx.send("❌ 권한이 없습니다. 개발자 또는 관리자만 사용 가능해요!")
            return

        thinking = await ctx.send("생각하고 있어요..")
        self.toggle(ctx.guild.id, True, disabled_by_dev=False)
        await thinking.edit(content="✅ 챗봇을 활성화했어요!")

    @commands.command()
    async def disable_ai(self, ctx):
        is_dev = self.is_developer(ctx.author.id)
        is_admin = ctx.author.guild_permissions.administrator

        if not (is_dev or is_admin):
            await ctx.send("❌ 권한이 없습니다. 개발자 또는 관리자만 사용 가능해요!")
            return

        thinking = await ctx.send("생각하고 있어요..")
        self.toggle(ctx.guild.id, False, disabled_by_dev=is_dev)

        if is_dev:
            await thinking.edit(content="❌ 챗봇을 비활성화했어요! (개발자 비활성화 - 개발자만 활성화 가능)")
        else:
            await thinking.edit(content="❌ 챗봇을 비활성화했어요!")

    @commands.command()
    async def ai_status(self, ctx):
        thinking = await ctx.send("생각하고 있어요..")

        if self.is_enabled(ctx.guild.id):
            status = "✅ 활성화"
        elif self.is_disabled_by_dev(ctx.guild.id):
            status = "❌ 비활성화 (개발자 비활성화 - 개발자만 활성화 가능)"
        else:
            status = "❌ 비활성화"

        await thinking.edit(content=f"현재 상태: {status}")

    @commands.command(name="설정")
    async def settings(self, ctx):
        is_admin = ctx.author.guild_permissions.administrator
        is_dev = self.is_developer(ctx.author.id)

        if not (is_admin or is_dev):
            await ctx.send("❌ 권한이 없습니다. 관리자 또는 개발자만 사용 가능해요!")
            return

        embed = self.get_settings_embed(ctx.guild.id)
        view = SettingsView(self, ctx.guild.id)

        await ctx.send(embed=embed, view=view)

    @commands.command()
    async def reset_chat(self, ctx):
        keys_to_remove = [
            (ctx.guild.id, ctx.channel.id, ctx.author.id, "reply"),
            (ctx.guild.id, ctx.channel.id, ctx.author.id, "new"),
        ]
        for key in keys_to_remove:
            self.conversations.pop(key, None)
        await ctx.send("🧹 이 채널에서 회원님의 대화 기억을 초기화했어요!")


async def setup(bot):
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        raise ValueError("❌ OPENAI_API_KEY가 .env에 없습니다!")

    await bot.add_cog(ChatBot(bot))

    try:
        await bot.load_extension("server_manager")
    except Exception as e:
        print(f"⚠️ 서버 관리 기능 로드 실패: {e}")