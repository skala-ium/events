import uuid
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, DateTime, Integer, BigInteger, Boolean, Identity
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID


class Base(DeclarativeBase):
    pass


class Professor(Base):
    __tablename__ = "professor"

    professor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(30))
    slack_user_id: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str | None] = mapped_column(String(100), unique=True)
    password: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))


class Class(Base):
    __tablename__ = "classes"

    class_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    class_name: Mapped[str] = mapped_column(String(100))
    generation: Mapped[int | None] = mapped_column(Integer)
    class_group: Mapped[str] = mapped_column(String(20))
    slack_channel_id: Mapped[str | None] = mapped_column(String(50), unique=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))


class Student(Base):
    __tablename__ = "student"

    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(50))
    slack_user_id: Mapped[str] = mapped_column(String(50), unique=True)
    password: Mapped[str | None] = mapped_column(String(255))
    major: Mapped[str | None] = mapped_column(String(50))
    class_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("classes.class_id"))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))


class Assignment(Base):
    __tablename__ = "assignment"

    assignment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    class_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("classes.class_id"))
    professor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("professor.professor_id"))
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str | None] = mapped_column(Text)
    topic: Mapped[str | None] = mapped_column(String(100))
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    slack_post_ts: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))


class AssignmentRequirement(Base):
    __tablename__ = "assignment_requirement"

    requirement_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    assignment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("assignment.assignment_id"))
    content: Mapped[str] = mapped_column(String(500))


class Submission(Base):
    __tablename__ = "submission"

    submission_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    student_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("student.student_id"))
    assignment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("assignment.assignment_id"))
    content_text: Mapped[str | None] = mapped_column(Text)
    file_url: Mapped[str | None] = mapped_column(Text)
    file_name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str | None] = mapped_column(String(20))
    slack_thread_ts: Mapped[str | None] = mapped_column(String(100))
    is_met_requirements: Mapped[bool | None] = mapped_column(Boolean)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))


class VerificationResult(Base):
    __tablename__ = "verification_result"

    verification_result_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    requirement_id: Mapped[int] = mapped_column(BigInteger)
    submission_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    is_met: Mapped[bool] = mapped_column(Boolean)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    feedback: Mapped[str | None] = mapped_column(Text)
