from typing import Optional
import discord
from discord import app_commands
from discord.ui import Button, Select, View

COMMAND_GROUPS = {
    "음악": {
        "emoji": "🎵",
        "content": "준비 중이에요. 잠시만 기다려 주세요!"
    },
    "정보": {
        "emoji": "👤",
        "content": "</아바타:1504866630000443520> - 다른 사람이나 본인의 프로필 사진을 불러올 수 있어요!\n> </아바타:1504866630000443520> [대상: 선택 사항]\n-# 대상을 지정하지 않으면 자신의 정보를 불러와요.\n\n</유저정보:1504866630352769046> - 다른 사람이나 본인의 정보를 불러올 수 있어요!\n> </유저정보:1504866630352769046> [대상: 선택 사항]\n-# 대상을 지정하지 않으면 자신의 정보를 불러와요.\n\n</봇정보:1504866630352769044> - 봇에 대해 알아볼 수 있어요.\n✨ 저에 대해 알아보실 수 있는 정보에요. **업타임, 지연 속도, 제가 몇 명과 놀고 있는지** 볼 수 있어요!\n\n</서버정보:1504866630352769045> - 지금 보고 있는 서버의 정보를 볼 수 있어요.\n-# 다른 궁긍한 것이 있나요? 아래의 선택 상자에서 골라보세요!"
    },
    "경고": {
        "emoji": "⚠️",
        "content": "</경고 부여:1506238477975420969> - 대상에게 경고를 부여해요.\n> </경고 부여:1506238477975420969> [사유: 선택 사항]\n\n</경고 관리:1506238477975420969> - 대상의 경고를 관리할 수 있어요.\n대상의 경고 시기, 경고 이유, 경고 삭제 등을 진행할 수 있어요.\n\n</경고 설정:1506238477975420969> - 서버의 자동 제재 시스템을 관리할 수 있어요.\n경고 누적에 따른 **서버의 자동 제재 시스템**을 사용할 수 있어요.\n타임아웃과 차단 자동 제재를 지원하고, 비활성화도 가능해요.\n\n⚠️ **관리자 권한**이 있는 유저만 사용할 수 있는 명령어에요.\n-# 다른 궁긍한 것이 있나요? 아래의 선택 상자에서 골라보세요!"
    },
    "관리": {
        "emoji": "🔨",
        "content": "</타임아웃:1504866630000443517> - 대상을 타임아웃 할 수 있어요.\n> </타임아웃:1504866630000443517> [대상] [1d2h20m의 형식으로 시간 입력] [사유: 선택 사항]\n-# **최대 7일까지 적용할 수 있어요.**\n\n</차단:1504866630000443519> - 대상을 서버에서 차단할 수 있어요.\n> </차단:1504866630000443519> [대상] [사유: 선택 사항]\n\n</추방:1504866630000443518> - 대상을 서버에서 추방할 수 있어요.\n> </추방:1504866630000443518> [대상] [사유: 선택 사항]\n\n⚠️ **관리자 권한**이 있는 유저만 사용할 수 있는 명령어에요.\n-# 다른 궁긍한 것이 있나요? 아래의 선택 상자에서 골라보세요!"
    },
    "청소": {
        "emoji": "🧹",
        "content": "청소 명령어는 두 가지 방법으로 실행할 수 있어요.\n### 슬래시 커맨드로 실행하기\n> </청소:1528774219624743033> [ 삭제할 메시지 개수 ]\n### 컨텍스트 메뉴 이용하기 __(구간 삭제 지원)__\n1. 메시지를 우클릭하면 **\"앱\"** 표시가 있어요. 거기에서 **여기부터/여기까지 청소**를 눌러주세요.\n2. 시작 지점이나 끝 지점이 설정되었을 거에요. 60초 안에 **1번**과 똑같이 시작/끝 지점을 설정해주세요.\n-# 혹은 \"이 메시지부터 아래까지 모두 청소\" 버튼을 통해서 최하단 메시지까지 바로 지울 수 있어요.\n\n아 참! 메시지는 **1회 최대 100개** 까지 삭제할 수 있고, 14일이 지난 메시지는 삭제할 수 없어요.\n-# 다른 궁긍한 것이 있나요? 아래의 선택 상자에서 골라보세요!"
    },
    "이모지 크게 보기": {
        "emoji": "😀",
        "content": "</점보이모지:1528409935895986246> - 제가 이모지를 크게 키워드려요!\n✌️ 저는 **커스텀 이모지** 뿐만 아니라 **기본 이모지**도 키워드릴 수 있어요!\n기본 세팅은 두개 옵션 다 **\"꺼짐\"**으로 되어 있어요.\n-# **이모지 단일로 보내신 경우에만 자동으로 켜져요!**\n\n⚠️ **관리자 권한**이 있는 유저만 사용할 수 있는 명령어에요.\n-# 다른 궁긍한 것이 있나요? 아래의 선택 상자에서 골라보세요!"
    },
    "주식": {
        "emoji": "📈",
        "content": "</주식:1504866630000443514> - 주식 종목 검색기능\n> </주식:1504866630000443514> [티거/종목명] [간격] 으로 검색할 수 있어요.\n**한국증권거래소, 미국증권거래소 상장 종목**에서 검색할 수 있어요.\n검색 후 `⭐ 관심종목 추가하기` 버튼을 눌러 관심 종목에 추가할 수 있어요.\n\n이제 관심 종목 검색 방법을 알려드릴게요!\n</관심종목:1504866630000443515> 을 입력하시면 지금까지 등록하신 관심 종목들을 열람하실 수 있어요.\n-# 다른 궁긍한 것이 있나요? 아래의 선택 상자에서 골라보세요!"
    },
    "TTS (Text-to-Speech)": {
        "emoji": "🔊",
        "content": "</tts 열기:1529131037073084486> - TTS 기능을 설정하고 실행할 수 있어요.\n>  **설정 가능한 옵션:** 언어 설정, 빠르기 설정\n💦 아직까지는 음성채널 옆에 있는 **채팅 열기**를 통해 나타나는 음성채널 채팅에서만 사용할 수 있어요.\n곧 채널을 지정할 수 있는 기능과 TTS 모델이 바뀔 예정이니, 기다려 주시면 감사할 것 같아요!\n-# 음성 채널에 아무도 들어와 있지 않으면 자동으로 나가요.\n\n</tts 열기:1529131037073084486> - TTS 기능을 종료하고 음성 채팅에서 나가요.\n-# 다른 궁긍한 것이 있나요? 아래의 선택 상자에서 골라보세요!"
    }
}

MUSIC_COMMANDS = {
    "재생": [
        (
            "### 재생 기능\n</재생 시작:1504866750057943137> - 유튜브에서 음악을 찾아서 틀어드려요.\n> </재생 시작:1504866750057943137> [Youtube URL이나 곡의 이름, 혹은 작곡가 이름]\n\n</재생 정지:1504866750057943137> - 틀고 있던 음악을 정지하고 채널에서 나가요.\n-# :warning: **이 기능을 사용하면 대기열이 초기화돼요. 주의해서 사용해주세요!**\n\n</재생 반복:1504866750057943137> - 음악을 반복 재생해요.\n> 1곡 반복, 대기열 전체 반복 기능이 있어요.\n\n</재생 일시정지:1504866750057943137> - 음악을 잠깐 멈춰요.\n\n</재생 다음:1504866750057943137> - 대기열에 있는 다음 음악을 틀어요.\n-# 음악이 없으면 자동으로 정지돼요.\n\n</재생 나가:1504866750057943137> - 음성 채널에서 나가요.\n-# 다른 궁긍한 것이 있나요? 아래의 선택 상자에서 골라보세요!\n-# 혹은 음악 명령어에 대해서 더 궁금하다면 아래 페이지 이동 바튼을 눌러보세요!",
        )
    ],
    "대기열": [
        (
            "### 대기열 기능\n</대기열 확인:1504866750057943138> - 현재 대기열을 확인해요.\n\n</대기열 셔플:1504866750057943138> - 대기열 안에 있는 곡들을 무작위로 섞어요.\n\n</대기열 삭제:1504866750057943138> - 대기열 안 특정 곡을 삭제할 수 있어요.\n> </대기열 삭제:1504866750057943138> [삭제할 곡 번호]\n\n</대기열 초기화:1504866750057943138> - 대기열 안에 있는 모든 곡들을 삭제해요.\n-# 다른 궁긍한 것이 있나요? 아래의 선택 상자에서 골라보세요!\n-# 혹은 음악 명령어에 대해서 더 궁금하다면 아래 페이지 이동 바튼을 눌러보세요!",
        )
    ],
    "볼륨": [
        (
            "### 볼륨 기능\n</볼륨 설정:1504866750057943139> - 볼륨을 설정해요.\n> </볼륨 설정:1504866750057943139> [0% ~ 100%]\n\n</볼륨 확인:1504866750057943139> - 현재 볼륨을 확인해요.\n-# 다른 궁긍한 것이 있나요? 아래의 선택 상자에서 골라보세요!\n-# 혹은 음악 명령어에 대해서 더 궁금하다면 아래 페이지 이동 바튼을 눌러보세요!",
        )
    ],
}


def get_music_command_page(page: int):
    categories = ["재생", "대기열", "볼륨"]
    total_pages = len(categories)

    page = max(0, min(page, total_pages - 1))
    target_category = categories[page]
    page_commands = MUSIC_COMMANDS.get(target_category, [])

    return page_commands, page, total_pages


def format_music_commands(page_commands):
    content = ""
    for item in page_commands:
        if len(item) == 1:
            content += f"{item[0]}\n"
        elif len(item) == 3:
            name, emoji, description = item
            content += f"{emoji} **{name}** - {description}\n"
        else:
            content += f"{item[0]}\n"
    return content.strip()


class CommandSelect(Select):

    def __init__(self):
        options = [
            discord.SelectOption(
                label=group_name,
                value=group_name,
                emoji=group_info["emoji"],
            )
            for group_name, group_info in COMMAND_GROUPS.items()
        ]

        super().__init__(
            placeholder="어떤 것을 찾아보실래요?",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        group_name = self.values[0]

        if group_name == "음악 재생":
            page_commands, current_page, total_pages = get_music_command_page(0)
            content = (
                f"# 🎵 {group_name}\n\n{format_music_commands(page_commands)}"
            )
            content += f"\n-# 페이지 {current_page + 1} / {total_pages}"

            view = MusicHelpView(current_page, total_pages)
        else:
            group_info = COMMAND_GROUPS[group_name]
            emoji = group_info["emoji"]
            content_text = group_info["content"]
            content = f"# {emoji} {group_name}\n\n{content_text}"
            view = HelpView()

        await interaction.response.edit_message(content=content, view=view)


class PaginationButton(Button):
    def __init__(self, label: str, emoji: str, is_previous: bool):
        super().__init__(
            label=label, emoji=emoji, style=discord.ButtonStyle.blurple
        )
        self.is_previous = is_previous

    async def callback(self, interaction: discord.Interaction):
        view: MusicHelpView = self.view

        if self.is_previous:
            view.current_page = max(0, view.current_page - 1)
        else:
            view.current_page = min(
                view.total_pages - 1, view.current_page + 1
            )

        page_commands, current_page, total_pages = get_music_command_page(
            view.current_page
        )
        content = f"# 🎵 음악 재생\n\n{format_music_commands(page_commands)}"
        content += f"\n-# 페이지 {current_page + 1} / {total_pages}"
        view.update_buttons()

        await interaction.response.edit_message(content=content, view=view)


class MusicHelpView(View):
    def __init__(self, current_page: int = 0, total_pages: int = 3):
        super().__init__(timeout=180.0)
        self.current_page = current_page
        self.total_pages = total_pages
        self.add_item(CommandSelect())

        self.prev_button = PaginationButton("이전", "⬅️", is_previous=True)
        self.add_item(self.prev_button)

        self.next_button = PaginationButton("다음", "➡️", is_previous=False)
        self.add_item(self.next_button)

        self.update_buttons()

    def update_buttons(self):
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == self.total_pages - 1


class HelpView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=180.0)
        self.add_item(CommandSelect())


@app_commands.command(name="도움말", description="Synapse 봇 도움말 확인")
async def help_slash(interaction: discord.Interaction):
    content = (
        "# ✨ Synapse 도움말\n도움말을 열어주셨네요!\n안녕하세요! Synapse에요. TTS, 서버"
        " 관리 기능, 챗봇 기능을 써보시지 않으실래요?\n\n도움이 필요하세요?"
        " [공식 서포트 서버](<https://discord.gg/yE8jvq2BBR>)나 저의 DM으로"
        " 모실게요!\n-# 아래 선택 박스에서 명령어를 찾아볼 수 있어요!\n-# 그리고 저의"
        " 다른 이름을 아시나요...? 바로 설탕이에요! ✌️"
    )

    await interaction.response.send_message(
        content=content, view=HelpView(), ephemeral=True
    )