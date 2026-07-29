from sqlalchemy import String, Text, DateTime, ForeignKey, Integer, Float, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database import Base
from datetime import datetime
import uuid


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)

    # File info
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)

    # Video metadata
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    codec: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bitrate: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Processing
    status: Mapped[str] = mapped_column(String(50), default="uploaded", nullable=False)  # uploaded, processing, completed, failed
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    output_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # AI Analysis
    ai_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    ai_suggestions: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    ai_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ai_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="videos")
    project: Mapped["Project | None"] = relationship("Project", back_populates="videos")
    transcripts: Mapped[list["Transcript"]] = relationship("Transcript", back_populates="video", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="video", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_videos_status", "status"),
        Index("ix_videos_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Video(id={self.id}, filename={self.original_filename}, status={self.status})>"
