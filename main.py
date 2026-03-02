# from fastapi import FastAPI, Request, HTTPException
# from dotenv import load_dotenv
# from db import get_pool
# from processor import process_pending_events
# import json
# import os
# import hmac
# import hashlib
# import time

# load_dotenv()

# SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")

# app = FastAPI()


# def verify_slack_signature(body: bytes, timestamp: str, signature: str) -> bool:
#     # 재전송 공격 방지: 5분 이상 된 요청은 거부
#     if abs(time.time() - int(timestamp)) > 60 * 5:
#         return False

#     base_string = f"v0:{timestamp}:{body.decode('utf-8')}"
#     expected = "v0=" + hmac.new(
#         SLACK_SIGNING_SECRET.encode(),
#         base_string.encode(),
#         hashlib.sha256
#     ).hexdigest()

#     return hmac.compare_digest(expected, signature)


# @app.get("/")
# async def health_check():
#     return {"status": "ok"}


# @app.post("/slack/events")
# async def handle_slack_events(request: Request):
#     if request.headers.get("x-slack-retry-num"):
#         return {"ok": True}

#     # 서명 검증
#     body_bytes = await request.body()
#     timestamp = request.headers.get("x-slack-request-timestamp", "")
#     signature = request.headers.get("x-slack-signature", "")

#     if not verify_slack_signature(body_bytes, timestamp, signature):
#         raise HTTPException(status_code=403, detail="Invalid signature")

#     body = json.loads(body_bytes)

#     if body.get("type") == "url_verification":
#         return {"challenge": body.get("challenge")}

#     if body.get("type") != "event_callback":
#         return {"ok": True}

#     event = body.get("event", {})

#     if event.get("type") != "message":
#         return {"ok": True}

#     pool = await get_pool()
#     async with pool.acquire() as conn:
#         await conn.execute("""
#             INSERT INTO slack_events (
#                 event_id, event_type, event_subtype,
#                 team_id, channel_id, user_id,
#                 text, ts, thread_ts, event_time,
#                 file_1_id, file_1_name, file_1_mimetype, file_1_url,
#                 file_2_id, file_2_name, file_2_mimetype, file_2_url,
#                 file_3_id, file_3_name, file_3_mimetype, file_3_url,
#                 file_4_id, file_4_name, file_4_mimetype, file_4_url,
#                 file_5_id, file_5_name, file_5_mimetype, file_5_url,
#                 raw_payload
#             ) VALUES (
#                 $1, $2, $3,
#                 $4, $5, $6,
#                 $7, $8, $9, $10,
#                 $11, $12, $13, $14,
#                 $15, $16, $17, $18,
#                 $19, $20, $21, $22,
#                 $23, $24, $25, $26,
#                 $27, $28, $29, $30,
#                 $31
#             )
#             ON CONFLICT (event_id) DO NOTHING
#         """,
#             body.get("event_id"),
#             event.get("type"),
#             event.get("subtype"),
#             body.get("team_id"),
#             event.get("channel"),
#             event.get("user"),
#             event.get("text"),
#             event.get("ts"),
#             event.get("thread_ts"),
#             body.get("event_time"),
#             *_extract_files(event.get("files", [])),
#             json.dumps(body)
#         )

#     await process_pending_events()

#     return {"ok": True}


# def _extract_files(files: list) -> list:
#     result = []
#     for i in range(5):
#         if i < len(files):
#             f = files[i]
#             result += [f.get("id"), f.get("name"), f.get("mimetype"), f.get("url_private")]
#         else:
#             result += [None, None, None, None]
#     return result

from fastapi import FastAPI, Request, HTTPException
from dotenv import load_dotenv
import json
import os
import hmac
import hashlib
import time
import httpx

load_dotenv()

SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")

app = FastAPI()


def verify_slack_signature(body: bytes, timestamp: str, signature: str) -> bool:
    if abs(time.time() - int(timestamp)) > 60 * 5:
        return False
    base_string = f"v0:{timestamp}:{body.decode('utf-8')}"
    expected = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET.encode(),
        base_string.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@app.get("/")
async def health_check():
    return {"status": "ok"}


async def get_channel_members_info(channel_id: str) -> str:
    """채널 멤버 목록 조회 및 정보 반환"""
    headers = {
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient() as client:
            # 1. 채널 멤버 목록 조회
            members_response = await client.get(
                "https://slack.com/api/conversations.members",
                headers=headers,
                params={"channel": channel_id}
            )
            members_data = members_response.json()

            if not members_data.get("ok"):
                error_msg = f"❌ 멤버 목록 조회 실패: {members_data.get('error')}"
                print(error_msg)
                return error_msg

            member_ids = members_data.get("members", [])

            print("\n" + "="*50)
            print(f"채널 ID       : {channel_id}")
            print(f"전체 멤버 수  : {len(member_ids)}")
            print("="*50)

            # 2. 각 멤버의 상세 정보 조회
            human_members = []
            for user_id in member_ids:
                user_response = await client.get(
                    "https://slack.com/api/users.info",
                    headers=headers,
                    params={"user": user_id}
                )
                user_data = user_response.json()

                if not user_data.get("ok"):
                    print(f"⚠️  유저 정보 조회 실패 ({user_id}): {user_data.get('error')}")
                    continue

                user = user_data.get("user", {})

                # 봇/앱 제외
                if user.get("is_bot") or user.get("is_app_user"):
                    continue

                human_members.append(user)

            print(f"\n사람 멤버 수  : {len(human_members)}")
            print("-"*50)

            # 3. 콘솔 출력
            result_lines = [f"📋 채널 멤버 목록 (총 {len(human_members)}명)\n"]

            for idx, user in enumerate(human_members, 1):
                real_name = user.get('real_name', user.get('name', 'Unknown'))
                username = user.get('name')
                email = user.get('profile', {}).get('email', 'N/A')

                print(f"\n[{idx}] {real_name}")
                print(f"    ID         : {user.get('id')}")
                print(f"    Username   : {username}")
                print(f"    Email      : {email}")
                print(f"    Display    : {user.get('profile', {}).get('display_name', 'N/A')}")
                print(f"    Status     : {user.get('profile', {}).get('status_text', '')}")
                print(f"    Deleted    : {user.get('deleted', False)}")

                # Slack 응답용 텍스트
                result_lines.append(f"{idx}. *{real_name}* (@{username})")
                result_lines.append(f"   Email: {email}\n")

            print("\n" + "="*50 + "\n")

            return "\n".join(result_lines)

    except Exception as e:
        error_msg = f"❌ 에러 발생: {str(e)}"
        print(error_msg)
        return error_msg


@app.post("/slack/command")
async def handle_slack_commands(request: Request):
    """Slack Slash Command 처리"""
    form_data = await request.form()

    command = form_data.get("command")
    channel_id = form_data.get("channel_id")
    user_id = form_data.get("user_id")

    print("\n" + "="*50)
    print(f"Slash Command : {command}")
    print(f"채널 ID       : {channel_id}")
    print(f"실행자 ID     : {user_id}")
    print("="*50)

    if command == "/userlist":
        result_text = await get_channel_members_info(channel_id)

        return {
            "response_type": "ephemeral",  # 본인만 보임
            "text": result_text
        }

    return {
        "response_type": "ephemeral",
        "text": "알 수 없는 명령어입니다."
    }


@app.post("/slack/events")
async def handle_slack_events(request: Request):
    if request.headers.get("x-slack-retry-num"):
        return {"ok": True}

    body_bytes = await request.body()
    timestamp = request.headers.get("x-slack-request-timestamp", "")
    signature = request.headers.get("x-slack-signature", "")

    if not verify_slack_signature(body_bytes, timestamp, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    body = json.loads(body_bytes)

    if body.get("type") == "url_verification":
        return {"challenge": body.get("challenge")}

    if body.get("type") != "event_callback":
        return {"ok": True}

    event = body.get("event", {})
    event_type = event.get("type")

    # message 이벤트 처리 (기존 로직)
    if event_type != "message":
        return {"ok": True}

    # DB 없이 일단 콘솔에 출력
    print("\n" + "="*50)
    print(f"이벤트 ID     : {body.get('event_id')}")
    print(f"채널          : {event.get('channel')}")
    print(f"발신자 ID     : {event.get('user')}")
    print(f"메시지 내용   : {event.get('text')}")
    print(f"ts            : {event.get('ts')}")
    print(f"thread_ts     : {event.get('thread_ts')}")
    print(f"subtype       : {event.get('subtype')}")

    files = event.get("files", [])
    if files:
        print(f"첨부 파일 수  : {len(files)}")
        for f in files:
            print(f"  - {f.get('name')} ({f.get('mimetype')})")

    print("판단          :", "학생 제출" if event.get("thread_ts") else "교수님 공지")
    print("="*50 + "\n")

    return {"ok": True}

