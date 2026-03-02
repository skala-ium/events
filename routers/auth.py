import os
import ssl
import random
import string
import uuid
import bcrypt
import certifi
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from sqlalchemy.exc import IntegrityError
from dotenv import load_dotenv
from db import get_session
from models import Student

load_dotenv()

router = APIRouter()

_ssl_context = ssl.create_default_context(cafile=certifi.where())
slack_client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"), ssl=_ssl_context)

# 인메모리 임시 저장소
pending_verifications: dict = {}  # {slack_user_id: {"code": str, "expires_at": datetime}}
verified_tokens: dict = {}        # {temp_token: slack_user_id}


class SendCodeRequest(BaseModel):
    email: str


class VerifyCodeRequest(BaseModel):
    slack_user_id: str
    code: str


class SignupRequest(BaseModel):
    temp_token: str
    name: str
    password: str
    major: str | None = None
    class_id: uuid.UUID | None = None


@router.post("/auth/slack/send-code")
async def send_verification_code(req: SendCodeRequest):
    try:
        result = slack_client.users_lookupByEmail(email=req.email)
        user = result["user"]
        slack_user_id = user["id"]
    except SlackApiError:
        raise HTTPException(status_code=404, detail="해당 이메일로 가입된 Slack 계정을 찾을 수 없습니다.")

    if user.get("deleted"):
        raise HTTPException(status_code=400, detail="비활성화된 Slack 계정입니다.")

    code = "".join(random.choices(string.digits, k=6))
    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=5)
    pending_verifications[slack_user_id] = {"code": code, "expires_at": expires_at}

    try:
        slack_client.chat_postMessage(
            channel=slack_user_id,
            text=f"🔐 인증코드: *{code}*\n5분 내에 입력해주세요."
        )
    except SlackApiError:
        raise HTTPException(status_code=500, detail="DM 전송에 실패했습니다.")

    return {"message": "인증코드가 DM으로 전송되었습니다.", "slack_user_id": slack_user_id}


@router.post("/auth/slack/verify-code")
async def verify_code(req: VerifyCodeRequest):
    entry = pending_verifications.get(req.slack_user_id)
    if not entry:
        raise HTTPException(status_code=400, detail="인증코드를 먼저 요청해주세요.")

    if datetime.now(timezone.utc).replace(tzinfo=None) > entry["expires_at"]:
        del pending_verifications[req.slack_user_id]
        raise HTTPException(status_code=400, detail="인증코드가 만료되었습니다.")

    if entry["code"] != req.code:
        raise HTTPException(status_code=400, detail="인증코드가 일치하지 않습니다.")

    del pending_verifications[req.slack_user_id]

    temp_token = str(uuid.uuid4())
    verified_tokens[temp_token] = req.slack_user_id

    return {"message": "인증 성공", "temp_token": temp_token}


@router.post("/auth/signup")
async def signup(req: SignupRequest):
    slack_user_id = verified_tokens.get(req.temp_token)
    if not slack_user_id:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다. 인증을 다시 진행해주세요.")

    hashed_pw = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    student = Student(
        slack_user_id=slack_user_id,
        name=req.name,
        password=hashed_pw,
        major=req.major,
        class_id=req.class_id,
        created_at=now,
        updated_at=now,
    )

    async with get_session() as session:
        try:
            session.add(student)
            await session.commit()
            await session.refresh(student)
        except IntegrityError:
            await session.rollback()
            raise HTTPException(status_code=409, detail="이미 가입된 Slack 계정입니다.")

    del verified_tokens[req.temp_token]

    return {"student_id": str(student.student_id)}
