from sqlalchemy import Column, String, Float, ForeignKey, DateTime, Integer, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

# ==========================================
# SQLAlchemy ORM Models (Database Tables)
# ==========================================

class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    filepath = Column(String, nullable=False)
    upload_date = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="uploaded") # uploaded, processing, completed, error
    image_path = Column(String, nullable=True)  # path to converted PNG for canvas display

    entities = relationship("Entity", back_populates="document", cascade="all, delete-orphan")
    connections = relationship("Connection", back_populates="document", cascade="all, delete-orphan")
    hazop_suggestions = relationship("HazopSuggestion", back_populates="document", cascade="all, delete-orphan")
    inspector_audits = relationship("InspectorAudit", back_populates="document", cascade="all, delete-orphan")


class Entity(Base):
    __tablename__ = "entities"

    id = Column(String, primary_key=True, index=True)
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    tag_number = Column(String, nullable=False, index=True)
    entity_type = Column(String, nullable=False) # Equipment, Valve, Instrument, Pipeline
    bbox = Column(JSON, nullable=False)          # {"x": int, "y": int, "w": int, "h": int}
    attributes = Column(JSON, nullable=True)     # {"spec": str, "rating": str, "status": str}

    document = relationship("Document", back_populates="entities")


class Connection(Base):
    __tablename__ = "connections"

    id = Column(String, primary_key=True, index=True)
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    source_id = Column(String, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    target_id = Column(String, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    line_spec = Column(String, nullable=False)
    flow_direction = Column(String, default="forward")

    document = relationship("Document", back_populates="connections")
    source_entity = relationship("Entity", foreign_keys=[source_id])
    target_entity = relationship("Entity", foreign_keys=[target_id])


class HazopSuggestion(Base):
    __tablename__ = "hazop_suggestions"

    id = Column(String, primary_key=True, index=True)
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    deviation = Column(String, nullable=False) # No Flow, More Pressure, etc.
    description = Column(String, nullable=False)
    target_tag = Column(String, nullable=False)

    document = relationship("Document", back_populates="hazop_suggestions")


class InspectorAudit(Base):
    __tablename__ = "inspector_audits"

    id = Column(String, primary_key=True, index=True)
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    category = Column(String, nullable=False) # Spec Mismatch, Safety Relief Omission
    severity = Column(String, nullable=False) # Warning, Flag, Critical
    description = Column(String, nullable=False)
    target_tag = Column(String, nullable=False)

    document = relationship("Document", back_populates="inspector_audits")


# ==========================================
# Pydantic Schemas (API Data Validation)
# ==========================================

class EntitySchema(BaseModel):
    id: str
    tag_number: str
    entity_type: str
    bbox: Dict[str, float]
    attributes: Dict[str, Any]

    class Config:
        from_attributes = True


class ConnectionSchema(BaseModel):
    id: str
    source_id: str
    target_id: str
    line_spec: str
    flow_direction: str
    source_tag: Optional[str] = None
    target_tag: Optional[str] = None

    class Config:
        from_attributes = True


class HazopSchema(BaseModel):
    id: str
    deviation: str
    description: str
    target_tag: str

    class Config:
        from_attributes = True


class InspectorSchema(BaseModel):
    id: str
    category: str
    severity: str
    description: str
    target_tag: str

    class Config:
        from_attributes = True


class DocumentResponse(BaseModel):
    id: str
    filename: str
    status: str
    upload_date: datetime
    image_url: Optional[str] = None
    entities: List[EntitySchema] = []
    connections: List[ConnectionSchema] = []
    hazop_suggestions: List[HazopSchema] = []
    inspector_audits: List[InspectorSchema] = []

    class Config:
        from_attributes = True
