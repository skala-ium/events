import uuid
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, DateTime, Integer
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


class Class(Base):
    __tablename__ = "class"

    class_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    class_name: Mapped[str] = mapped_column(String(100))
    generation: Mapped[int | None] = mapped_column(Integer)
    class_group: Mapped[str] = mapped_column(String(20))
    slack_channel_id: Mapped[str | None] = mapped_column(String(100), unique=True)


class Student(Base):
    __tablename__ = "student"

    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(50))
    slack_user_id: Mapped[str] = mapped_column(String(50), unique=True)
    password: Mapped[str | None] = mapped_column(String(255))
    class_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("class.class_id", ondelete="SET NULL"))


class Assignment(Base):
    __tablename__ = "assignment"

    assignment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    class_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("class.class_id"))
    professor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("professor.professor_id"))
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str | None] = mapped_column(Text)
    topic: Mapped[str | None] = mapped_column(String(100))
    deadline: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    slack_post_ts: Mapped[str | None] = mapped_column(String(100))


class AssignmentRequirement(Base):
    __tablename__ = "assignment_requirement"

    requirement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assignment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assignment.assignment_id", ondelete="CASCADE"))
    content: Mapped[str] = mapped_column(String(500))


class Submission(Base):
    __tablename__ = "submission"

    submission_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("student.student_id", ondelete="CASCADE"))
    assignment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assignment.assignment_id", ondelete="CASCADE"))
    content_text: Mapped[str | None] = mapped_column(Text)
    file_url: Mapped[str | None] = mapped_column(Text)
    file_name: Mapped[str | None] = mapped_column(String(255))
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(20), default="COMPLETED")
    slack_thread_ts: Mapped[str | None] = mapped_column(String(100))
