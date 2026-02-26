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

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from dotenv import load_dotenv
from sqlalchemy import text
from db import engine
from llm import parse_announcement
from processor import save_announcement
from routers.auth import router as auth_router
import json
import os
import hmac
import hashlib
import time
from datetime import datetime, timedelta

load_dotenv()

SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    print("[DB] 연결 성공")
    yield
    await engine.dispose()
    print("[DB] 연결 종료")


app = FastAPI(lifespan=lifespan)
app.include_router(auth_router)


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
    print("body: ", body)

    if body.get("type") == "url_verification":
        return {"challenge": body.get("challenge")}

    if body.get("type") != "event_callback":
        return {"ok": True}

    event = body.get("event", {})

    if event.get("type") != "message":
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

    is_announcement = not event.get("thread_ts")
    print("판단          :", "교수님 공지" if is_announcement else "학생 제출")
    print("="*50 + "\n")

    if is_announcement and event.get("text"):
        try:
            parsed = await parse_announcement(event.get("text"))
            if not parsed.get('deadline'):
                ts_value = float(event.get("ts")) 
                base_date = datetime.fromtimestamp(ts_value)
                calculated_deadline = (base_date + timedelta(days=7)).strftime('%Y-%m-%d')
                parsed['deadline'] = calculated_deadline

            print("[LLM 파싱 결과]")
            print(f"  제목        : {parsed.get('title')}")
            print(f"  주제        : {parsed.get('topic')}")
            print(f"  마감일      : {parsed.get('deadline')}")
            print(f"  요구사항    : {parsed.get('requirements')}")
            print()
            await save_announcement(event, parsed)
        except Exception as e:
            print(f"[처리 실패] {e}")

    return {"ok": True}

