from sqlalchemy import String, Text, DateTime, ForeignKey, Float, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database import Base
from datetime import datetime
import uuid


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id: Mapped[str] = mapped_column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)

    # Transcript content
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    full_text: Mapped[str] = mapped_column(Text, nullable=False)
    segments: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string of segments with timestamps

    # Subtitle files
    srt_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    vtt_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Metadata
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Processing
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)  # pending, processing, completed, failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    video: Mapped["Video"] = relationship("Video", back_populates="transcripts")

    __table_args__ = (
        Index("ix_transcripts_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Transcript(id={self.id}, video_id={self.video_id}, language={self.language})>"
