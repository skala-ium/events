import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from db import get_session

load_dotenv()

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID")

async def process_pending_events():
    pool = await get_session()
    async with pool.acquire() as conn:

        # 아직 처리 안 된 이벤트만 가져옴
        rows = await conn.fetch("""
            SELECT * FROM slack_events
            WHERE processed = FALSE
            ORDER BY event_time ASC
        """)

        for row in rows:
            try:
                if row["thread_ts"] is None:
                    await _handle_announcement(conn, row)
                else:
                    await _handle_submission(conn, row)

                # 처리 완료 표시
                await conn.execute("""
                    UPDATE slack_events SET processed = TRUE WHERE id = $1
                """, row["id"])

            except Exception as e:
                print(f"[처리 실패] event_id={row['event_id']} / 이유: {e}")


async def _handle_announcement(conn, row):
    """
    thread_ts 없음 → 교수님 공지
    assignment 테이블에 삽입. title/deadline은 LLM 붙이기 전까지 임시값.
    """
    # 이미 등록된 공지인지 확인 (ts 기준)
    existing = await conn.fetchrow("""
        SELECT assignment_id FROM assignment WHERE slack_post_ts = $1
    """, row["ts"])

    if existing:
        print(f"[공지 중복 스킵] ts={row['ts']}")
        return

    await conn.execute("""
        INSERT INTO assignment (
            class_id, professor_id,
            title, content,
            deadline, slack_post_ts
        ) VALUES (
            NULL, NULL,
            $1, $2,
            NOW() + INTERVAL '7 days',
            $3
        )
    """,
        f"[미분류] {row['text'][:50] if row['text'] else '제목없음'}",
        row["text"],
        row["ts"]
    )
    print(f"[공지 저장] ts={row['ts']}")


async def _handle_submission(conn, row):
    """
    thread_ts 있음 → 학생 제출
    1. thread_ts로 assignment 조회
    2. user_id로 student 조회 (없으면 자동 등록)
    3. submission 삽입
    """
    # 어떤 과제에 대한 제출인지 찾기
    assignment = await conn.fetchrow("""
        SELECT assignment_id FROM assignment WHERE slack_post_ts = $1
    """, row["thread_ts"])

    if not assignment:
        print(f"[과제 없음 스킵] thread_ts={row['thread_ts']} - 공지가 아직 처리 안 됐거나 없는 공지")
        return

    # 학생 조회 또는 자동 등록
    student = await conn.fetchrow("""
        SELECT student_id FROM student WHERE slack_user_id = $1
    """, row["user_id"])

    if not student:
        student = await conn.fetchrow("""
            INSERT INTO student (name, slack_user_id, password, class_id)
            VALUES ($1, $2, 'TEMP', NULL)
            RETURNING student_id
        """, f"미등록_{row['user_id']}", row["user_id"])
        print(f"[학생 자동 등록] slack_user_id={row['user_id']}")

    # 중복 제출 확인
    existing = await conn.fetchrow("""
        SELECT submission_id FROM submission
        WHERE student_id = $1 AND assignment_id = $2
    """, student["student_id"], assignment["assignment_id"])

    if existing:
        print(f"[제출 중복 스킵] student={row['user_id']}")
        return

    # 파일 URL 중 첫 번째 파일 사용 (여러 파일이면 나중에 확장)
    file_url = row["file_1_url"]
    file_name = row["file_1_name"]

    await conn.execute("""
        INSERT INTO submission (
            student_id, assignment_id,
            content_text, file_url, file_name,
            status, slack_thread_ts
        ) VALUES ($1, $2, $3, $4, $5, 'COMPLETED', $6)
    """,
        student["student_id"],
        assignment["assignment_id"],
        row["text"],
        file_url,
        file_name,
        row["thread_ts"]
    )
    print(f"[제출 저장] student={row['user_id']} / assignment={assignment['assignment_id']}")


async def save_announcement(event: dict, parsed: dict):
    from db import get_session
    from models import Professor, Class, Assignment, AssignmentRequirement
    from sqlalchemy import select

    async with get_session() as session:

        # 중복 체크
        existing = await session.scalar(
            select(Assignment).where(Assignment.slack_post_ts == event.get("ts"))
        )
        if existing:
            print(f"[공지 중복 스킵] ts={event.get('ts')}")
            return

        # professor 조회
        professor = await session.scalar(
            select(Professor).where(Professor.slack_user_id == event.get("user"))
        )
        if not professor:
            print(f"[경고] professor 없음: slack_user_id={event.get('user')}")

        # class 조회
        class_row = await session.scalar(
            select(Class).where(Class.slack_channel_id == event.get("channel"))
        )

        # deadline 문자열 → datetime
        deadline = datetime.fromisoformat(parsed["deadline"])

        # assignment INSERT
        assignment = Assignment(
            class_id=class_row.class_id if class_row else None,
            professor_id=professor.professor_id if professor else None,
            title=parsed.get("title"),
            content=parsed.get("content"),
            topic=parsed.get("topic"),
            deadline=deadline,
            slack_post_ts=event.get("ts"),
        )
        session.add(assignment)
        await session.flush()  # assignment_id 확보
        print(f"[과제 저장] assignment_id={assignment.assignment_id}")

        # requirements INSERT
        requirements = [
            AssignmentRequirement(assignment_id=assignment.assignment_id, content=req)
            for req in parsed.get("requirements", [])
        ]
        session.add_all(requirements)
        await session.commit()
        print(f"[요구사항 저장] {len(requirements)}개")


if __name__ == "__main__":
    asyncio.run(process_pending_events())