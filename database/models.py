"""
SQLAlchemy ORM models for the collaborative checksheet system.
"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, Boolean, LargeBinary
)
from sqlalchemy.orm import relationship

from database.connection import Base


class User(Base):
    """Team members and admins with role-based access control."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False, index=True)
    nik = Column(String(50), nullable=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default="operator")  # "admin" or "operator"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    checksheets = relationship("Checksheet", back_populates="assignee")


class Checksheet(Base):
    """Main checksheet master template record."""
    __tablename__ = "checksheets"

    id = Column(Integer, primary_key=True, index=True)
    part_number = Column(String(100), nullable=False, index=True)
    clean_part_number = Column(String(100), nullable=False, index=True)
    part_name = Column(String(255), default="")
    model = Column(String(100), default="-")
    customer = Column(String(100), default="PT. HPM")
    doc_number = Column(String(100), default="Form 1")
    template_type = Column(String(50), default="GENERIC")

    # Status: DRAFT, READY_FOR_SUBMIT, IN_QUEUE, SUBMITTED, TIDAK_ADA_PART
    status = Column(String(50), default="DRAFT", index=True)
    keterangan = Column(Text, default="")

    # Team assignment and concurrency locking
    assigned_to = Column(String(100), default="Unassigned", nullable=True, index=True)
    assigned_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    locked_by = Column(String(100), nullable=True)
    locked_at = Column(DateTime, nullable=True)

    # FactoryHub submission results
    factoryhub_id = Column(String(50), nullable=True)
    factoryhub_url = Column(String(255), nullable=True)
    raw_file_path = Column(String(255), default="")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    assignee = relationship("User", back_populates="checksheets")
    inspection_points = relationship("InspectionPoint", back_populates="checksheet", cascade="all, delete-orphan", order_by="InspectionPoint.order_index")
    images = relationship("PartImage", back_populates="checksheet", cascade="all, delete-orphan")
    submissions = relationship("SubmissionQueue", back_populates="checksheet", cascade="all, delete-orphan")


class InspectionPoint(Base):
    """Individual balloon inspection point for a checksheet."""
    __tablename__ = "inspection_points"

    id = Column(Integer, primary_key=True, index=True)
    checksheet_id = Column(Integer, ForeignKey("checksheets.id", ondelete="CASCADE"), nullable=False, index=True)
    item_no = Column(String(50), nullable=False)
    inspection_item = Column(String(255), nullable=False)
    standard = Column(Text, default="-")
    method = Column(String(100), default="Visual")
    master_data = Column(String(255), default="")
    order_index = Column(Integer, default=0)

    # Relationships
    checksheet = relationship("Checksheet", back_populates="inspection_points")


class PartImage(Base):
    """Reference sketch image attached to a checksheet."""
    __tablename__ = "part_images"

    id = Column(Integer, primary_key=True, index=True)
    checksheet_id = Column(Integer, ForeignKey("checksheets.id", ondelete="CASCADE"), nullable=False, index=True)
    image_path = Column(String(255), nullable=False)
    image_url = Column(String(255), default="")
    image_base64 = Column(Text, nullable=True)

    # Relationships
    checksheet = relationship("Checksheet", back_populates="images")


class SubmissionQueue(Base):
    """Queue and execution log for FactoryHub automation jobs."""
    __tablename__ = "submission_queue"

    id = Column(Integer, primary_key=True, index=True)
    checksheet_id = Column(Integer, ForeignKey("checksheets.id", ondelete="CASCADE"), nullable=False, index=True)
    operator_name = Column(String(100), default="Zul")
    status = Column(String(50), default="PENDING", index=True)  # PENDING, RUNNING, SUCCESS, FAILED
    log_output = Column(Text, default="")
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    checksheet = relationship("Checksheet", back_populates="submissions")


class ActivityLog(Base):
    """Audit and process log for checksheet actions, submissions, and updates."""
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    action = Column(String(100), nullable=False)
    part_number = Column(String(100), nullable=True, default="-")
    operator = Column(String(100), default="System")
    status = Column(String(50), default="SUCCESS")
    details = Column(Text, default="")
    link = Column(String(255), nullable=True)
