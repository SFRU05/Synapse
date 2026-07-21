# 다재다능한 디스코드 봇, Synapse

> 서버 관리, 로그 추적, 유저 정보 조회, 주가 확인까지 가능한 디스코드 봇

## ✨ 주요 기능
[ 관리 기능 ]
- 추방
- 차단
- 타임아웃
- 경고 (자동 중재 기능)

[ 주가 확인 ]
- 현재 주가 확인
- 관심종목 확인 기능

[ 정보 확인 ]
- 봇 정보 확인
- 서버 덩보 확인
- 유저 정보 확인
- 아바타 불러오기

[ 로그 기능 ]
- 메시지 삭제 / 수정
- 유저 입 / 퇴장
- 역할 정보, 권한변경
- 채널 생성 / 수정 / 삭제
- 역할 지급 / 회수

[ 기타 명령어 ]
- 점보 이모지 (단일 이모지를 전송했을 때 확대해주는 기능)
- Giveaways 기능
- 랜덤 추첨 기능

## 📌 안내 사항 (필독)

> 봇의 소스코드를 전체가 아니라 일부만 사용하실 경우에도  
> **반드시 출처를 표기**해 주세요.

---

## 🚀 사용 방법

### 1) `.env` 파일 생성
프로젝트 폴더에 `.env` 파일을 만든 뒤 아래 내용을 입력하세요.

```env
DISCORD_TOKEN=Your_Bot_TOKEN
```

- `Your_Bot_TOKEN` 부분에 본인의 Discord Bot 토큰을 넣어주세요.

### 2) Discord Developer Portal 설정
아래 링크의 **Bot 탭**에서 다음 Intent를 활성화해야 합니다.

- ✅ Server Members Intent
- ✅ Presence Intent
- ✅ Message Content Intent

🔗 [Discord Developer Portal](https://discord.com/developers/applications/943838140316155974/bot)

---

## 🧩 참고

- Node.js 및 패키지 설치 후 실행하세요.
- 운영 서버에서는 토큰 유출 방지를 위해 `.env` 파일을 외부에 공개하지 마세요.

---

## 📄 License / Credits

사용 또는 수정 시 출처 표기를 부탁드립니다.
