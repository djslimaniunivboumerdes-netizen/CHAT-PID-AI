"""
CHAT-PID-AI: Main FastAPI Application
=====================================
Automated AI Analysis Studio for P&IDs with Thermodynamic Safety Auditing

This module provides the FastAPI REST API for:
- P&ID document upload and processing
- AI-powered HAZOP analysis
- Engineering validation (API 520/521, ASME B31.3)
- Thermodynamic safety audits using NeqSim

Author: CHAT-PID-AI Development Team
License: Apache 2.0
"""

import os
import uuid
import json
import shutil
import networkx as nx
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, Depends, UploadFile, File, HTTPException, BackgroundTasks, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from config import settings
from database import engine, Base, get_db
from models import (
    Document,
    DocumentResponse,
    Entity,
    Connection,
    HazopSuggestion,
    InspectorAudit,
)
from ai_engine import ai_engine
from graph_engine import graph_engine
from rules_engine import rules_engine, thermodynamic_auditor
from export_engine import export_engine, DEXPIExportResult, PYDEXPI_AVAILABLE

# =============================================================================
# Database Initialization
# =============================================================================

Base.metadata.create_all(bind=engine)

# =============================================================================
# FastAPI Application Setup
# =============================================================================

app = FastAPI(
    title="CHAT-PID-AI",
    version="2.1.0",
    description=(
        "Automated AI Analysis Studio for P&IDs. Features include:\n"
        "- AI-powered HAZOP analysis with local LLM integration\n"
        "- Engineering validation (API 520/521, ASME B31.3)\n"
        "- Thermodynamic safety audits using NeqSim EOS\n"
        "- Multiphase flow and liquid dropout risk detection\n"
        "- ANSI class rating exceedance checks\n"
        "- DEXPI (Data Exchange in the Process Industry) XML export"
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static File Directories
app.mount("/static", StaticFiles(directory=settings.STATIC_DIR), name="static")
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")
app.mount("/exports", StaticFiles(directory=settings.EXPORT_DIR), name="exports")

# =============================================================================
# Pydantic Response Models
# =============================================================================

class ThermodynamicFindingResponse(BaseModel):
    """Response model for a single thermodynamic safety finding."""
    severity: str
    category: str
    title: str
    description: str
    recommendation: str
    technical_details: Dict[str, Any]
    detected_at: str


class ThermodynamicAuditResponse(BaseModel):
    """Response model for thermodynamic safety audit report."""
    audit_id: str
    pipe_node_id: str
    line_spec: str
    operating_pressure_bar: float
    operating_temperature_c: float
    findings: List[ThermodynamicFindingResponse]
    fluid_composition: Dict[str, float]
    thermodynamic_state: Dict[str, Any]
    audit_timestamp: str
    calculation_status: str
    error_message: Optional[str] = None
    has_critical_findings: bool
    has_warnings: bool

    class Config:
        from_attributes = True


class ThermodynamicBatchAuditResponse(BaseModel):
    """Response model for batch thermodynamic audit."""
    total_segments_audited: int
    critical_findings_count: int
    warning_count: int
    info_count: int
    reports: List[ThermodynamicAuditResponse]
    summary_timestamp: str


class NeqSimStatusResponse(BaseModel):
    """Response model for NeqSim library status check."""
    neqsim_available: bool
    status: str
    supported_eos_models: List[str]
    default_composition: Dict[str, float]
    ansi_class_limits: Dict[str, float]


class GraphNodeInput(BaseModel):
    """Input model for graph node data."""
    id: str
    tag: Optional[str] = None
    type: Optional[str] = None
    spec: Optional[str] = None
    line_spec: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None


class GraphEdgeInput(BaseModel):
    """Input model for graph edge data."""
    source: str
    target: str
    spec: Optional[str] = None
    flow: Optional[str] = None


class GraphInput(BaseModel):
    """Input model for serialized NetworkX graph."""
    nodes: List[GraphNodeInput]
    edges: List[GraphEdgeInput]


# =============================================================================
# DEXPI Export Response Models
# =============================================================================

class DEXPIExportStatusResponse(BaseModel):
    """Response model for DEXPI library status check."""
    dexpi_available: bool
    python_version_supported: bool
    status: str
    supported_dexpi_version: str = "1.3"


class DEXPIExportResultResponse(BaseModel):
    """Response model for DEXPI export operation."""
    success: bool
    output_path: Optional[str] = None
    error_message: Optional[str] = None
    nodes_exported: int = 0
    edges_exported: int = 0
    warnings: List[str] = []
    exported_objects: Dict[str, str] = {}


class DEXPIExportRequest(BaseModel):
    """Request model for direct DEXPI export without database."""
    graph_data: GraphInput
    project_name: str = Field(default="CHAT-PID-AI Export", description="Project name for DEXPI metadata")
    author: str = Field(default="CHAT-PID-AI", description="Author name for DEXPI metadata")
    strict_mapping: bool = Field(default=False, description="Fail on unrecognized node types")


# =============================================================================
# Utility Functions
# =============================================================================

def serialize_networkx_graph(graph: nx.DiGraph) -> Dict[str, Any]:
    """Serialize a NetworkX graph to a dictionary for JSON transport."""
    return nx.node_link_data(graph)


def deserialize_networkx_graph(data: Dict[str, Any]) -> nx.DiGraph:
    """Deserialize a dictionary to a NetworkX DiGraph."""
    return nx.node_link_graph(data, directed=True)


# =============================================================================
# Root Endpoint
# =============================================================================

@app.get("/", response_class=FileResponse)
async def serve_index():
    """Serve the main interactive single-page studio web application."""
    return os.path.join(settings.STATIC_DIR, "index.html")


# =============================================================================
# Document Management Endpoints
# =============================================================================

@app.post("/api/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    STEP 1: Upload PDF or Image containing P&ID.

    Accepts PDF, PNG, JPG, JPEG, or TIFF file formats.
    Returns a DocumentResponse with the created document record.
    """
    doc_id = str(uuid.uuid4())
    ext = file.filename.split(".")[-1].lower()

    if ext not in ["pdf", "png", "jpg", "jpeg", "tiff"]:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported file format. Please upload PDF, PNG, JPG, JPEG, or TIFF."
            ),
        )

    save_path = os.path.join(settings.UPLOAD_DIR, f"{doc_id}.{ext}")

    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Create Database Record
    doc = Document(
        id=doc_id,
        filename=file.filename,
        filepath=save_path,
        status="uploaded",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return doc


def run_background_processing(doc_id: str, db: Session):
    """Background task executing the complete AI Processing Engine workflow."""
    try:
        # Step 1 & 2: Symbol Recognition & ADE/OCR
        ai_engine.process_document(doc_id, db)

        # Step 3: Smart Map Line Tracing & Graph Construction
        graph = graph_engine.build_connectivity_graph(doc_id, db)

        # Step 4: AI HAZOP Assistant & AI Inspector Validation
        rules_engine.run_hazop_analysis(doc_id, graph, db)
        rules_engine.run_ai_inspector(doc_id, graph, db)

        # Mark completed
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            doc.status = "completed"
            db.commit()

    except Exception as e:
        print(f"Background processing failure for {doc_id}: {e}")
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            doc.status = "error"
            db.commit()


@app.post("/api/process/{doc_id}")
async def start_processing(
    doc_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    STEP 3: Trigger AI Processing Engine background worker.

    This endpoint initiates the complete P&ID analysis pipeline:
    1. Symbol recognition and OCR
    2. Connectivity graph construction
    3. HAZOP analysis
    4. Engineering validation
    """
    document = db.query(Document).filter(Document.id == doc_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")

    background_tasks.add_task(run_background_processing, doc_id, db)
    return {"status": "processing_started", "document_id": doc_id}


@app.get("/api/document/{doc_id}", response_model=DocumentResponse)
async def get_document_results(doc_id: str, db: Session = Depends(get_db)):
    """
    STEP 4: Fetch full digital twin inventory and analytics results.

    Returns comprehensive document data including:
    - Entities (equipment, valves, instruments)
    - Connections (pipeline specifications)
    - HAZOP suggestions
    - Inspector audits
    """
    document = db.query(Document).filter(Document.id == doc_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")

    entities = db.query(Entity).filter(Entity.document_id == doc_id).all()
    connections = db.query(Connection).filter(Connection.document_id == doc_id).all()
    hazop = db.query(HazopSuggestion).filter(HazopSuggestion.document_id == doc_id).all()
    audits = db.query(InspectorAudit).filter(InspectorAudit.document_id == doc_id).all()

    # Enrich connections with tag numbers for clean UI rendering
    ent_map = {e.id: e.tag_number for e in entities}
    conn_list = []
    for c in connections:
        conn_list.append({
            "id": c.id,
            "source_id": c.source_id,
            "target_id": c.target_id,
            "line_spec": c.line_spec,
            "flow_direction": c.flow_direction,
            "source_tag": ent_map.get(c.source_id, "Unknown"),
            "target_tag": ent_map.get(c.target_id, "Unknown"),
        })

    return {
        "id": document.id,
        "filename": document.filename,
        "status": document.status,
        "upload_date": document.upload_date,
        "image_url": document.image_path,
        "entities": entities,
        "connections": conn_list,
        "hazop_suggestions": hazop,
        "inspector_audits": audits,
    }


# =============================================================================
# Thermodynamic Safety Audit Endpoints (NEW)
# =============================================================================

@app.get(
    "/api/audit/thermodynamic/status",
    response_model=NeqSimStatusResponse,
    tags=["Thermodynamic Safety Audit"],
)
async def get_neqsim_status():
    """
    Check NeqSim library availability and configuration.

    Returns:
        - Whether NeqSim is installed and working
        - Supported equation of state models
        - Default fluid composition
        - ANSI class pressure limits
    """
    return {
        "neqsim_available": thermodynamic_auditor.neqsim_available,
        "status": "operational" if thermodynamic_auditor.neqsim_available else "unavailable",
        "supported_eos_models": [
            "SRK (Soave-Redlich-Kwong)",
            "PR (Peng-Robinson)",
            "CPA (Cubic Plus Association)",
            "GERG-2008",
        ],
        "default_composition": thermodynamic_auditor.DEFAULT_COMPOSITION,
        "ansi_class_limits": thermodynamic_auditor.ANSI_CLASS_LIMITS,
    }


@app.post(
    "/api/audit/thermodynamic/single",
    response_model=ThermodynamicAuditResponse,
    tags=["Thermodynamic Safety Audit"],
)
async def audit_single_pipe(
    pipe_node_data: Dict[str, Any] = Body(...,
        example={
            "id": "pipe-001",
            "tag_number": "PIPE-101",
            "line_spec": '4"-CS-150#',
            "attributes": {"material": "CS", " insulation": "none"},
        }
    ),
    operating_pressure_bar: float = Body(..., gt=0, le=1000,
        example=25.0,
        description="Operating pressure in bara"
    ),
    operating_temperature_c: float = Body(...,
        ge=-200, le=1000,
        example=80.0,
        description="Operating temperature in Celsius"
    ),
    fluid_composition: Optional[Dict[str, float]] = Body(None,
        example={"methane": 0.85, "ethane": 0.10, "propane": 0.05},
        description="Optional fluid composition (mole fractions)"
    ),
):
    """
    Perform thermodynamic safety audit on a single pipe segment.

    This endpoint performs physics-aware safety auditing using NeqSim:

    **Checks performed:**
    1. **Multiphase Dropout Detection**: Uses SRK EOS TPflash to detect
       dangerous two-phase conditions (0.0 < vapor fraction < 0.95)
       that could cause liquid slugging or water hammer.

    2. **ANSI Class Rating Check**: Verifies that operating pressure does not
       exceed the maximum allowable pressure for the specified ANSI class rating.

    **Parameters:**
    - `pipe_node_data`: Dictionary containing pipe node information
    - `operating_pressure_bar`: Operating pressure in bara (1-1000 bar)
    - `operating_temperature_c`: Operating temperature in °C (-200 to 1000°C)
    - `fluid_composition`: Optional custom fluid composition (mole fractions)

    **Returns:**
    - Comprehensive audit report with findings
    - Vapor-liquid equilibrium state from NeqSim
    - Safety recommendations
    """
    report = rules_engine.run_thermodynamic_audit(
        pipe_node_data=pipe_node_data,
        operating_pressure_bar=operating_pressure_bar,
        operating_temperature_c=operating_temperature_c,
        fluid_composition=fluid_composition,
    )

    return ThermodynamicAuditResponse(
        audit_id=report.audit_id,
        pipe_node_id=report.pipe_node_id,
        line_spec=report.line_spec,
        operating_pressure_bar=report.operating_pressure_bar,
        operating_temperature_c=report.operating_temperature_c,
        findings=[
            ThermodynamicFindingResponse(
                severity=f.severity.value,
                category=f.category.value,
                title=f.title,
                description=f.description,
                recommendation=f.recommendation,
                technical_details=f.technical_details,
                detected_at=f.detected_at,
            )
            for f in report.findings
        ],
        fluid_composition=report.fluid_composition,
        thermodynamic_state=report.thermodynamic_state,
        audit_timestamp=report.audit_timestamp,
        calculation_status=report.calculation_status,
        error_message=report.error_message,
        has_critical_findings=report.has_critical_findings,
        has_warnings=report.has_warnings,
    )


@app.post(
    "/api/audit/thermodynamic/batch",
    response_model=ThermodynamicBatchAuditResponse,
    tags=["Thermodynamic Safety Audit"],
)
async def audit_pipeline_batch(
    graph_data: GraphInput,
    operating_pressure_bar: float = Body(..., gt=0, le=1000,
        example=25.0,
        description="Operating pressure in bara"
    ),
    operating_temperature_c: float = Body(...,
        ge=-200, le=1000,
        example=80.0,
        description="Operating temperature in Celsius"
    ),
    fluid_composition: Optional[Dict[str, float]] = Body(None,
        description="Optional fluid composition override"
    ),
):
    """
    Perform batch thermodynamic safety audit on multiple pipeline segments.

    Accepts a serialized NetworkX graph and audits all pipe/line nodes.

    **Request Body:**
    - `graph_data`: Serialized graph with nodes and edges
    - `operating_pressure_bar`: Uniform operating pressure for all segments
    - `operating_temperature_c`: Uniform operating temperature for all segments
    - `fluid_composition`: Optional fluid composition override

    **Returns:**
    - Summary statistics (critical/warning counts)
    - Individual audit reports for each pipe segment
    """
    # Convert Pydantic model to dict for processing
    graph_dict = {
        "nodes": [n.model_dump() for n in graph_data.nodes],
        "edges": [e.model_dump() for e in graph_data.edges],
    }

    # Create NetworkX graph from serialized data
    G = nx.DiGraph()

    # Add nodes
    for node in graph_dict["nodes"]:
        G.add_node(
            node["id"],
            tag=node.get("tag", f"PIPE-{node['id'][:8]}"),
            type=node.get("type", "Pipeline"),
            spec=node.get("spec", node.get("line_spec", '4"-CS-150#')),
            attributes=node.get("attributes", {}),
        )

    # Add edges
    for edge in graph_dict["edges"]:
        G.add_edge(
            edge["source"],
            edge["target"],
            spec=edge.get("spec", '4"-CS-150#'),
            flow=edge.get("flow", "forward"),
        )

    # Run batch audit
    reports = thermodynamic_auditor.batch_audit_pipeline(
        graph=G,
        operating_pressure_bar=operating_pressure_bar,
        operating_temperature_c=operating_temperature_c,
        fluid_composition=fluid_composition,
    )

    # Convert reports to response format
    report_responses = []
    critical_count = 0
    warning_count = 0
    info_count = 0

    for report in reports:
        for finding in report.findings:
            if finding.severity.value == "Critical":
                critical_count += 1
            elif finding.severity.value == "Warning":
                warning_count += 1
            elif finding.severity.value == "Info":
                info_count += 1

        report_responses.append(ThermodynamicAuditResponse(
            audit_id=report.audit_id,
            pipe_node_id=report.pipe_node_id,
            line_spec=report.line_spec,
            operating_pressure_bar=report.operating_pressure_bar,
            operating_temperature_c=report.operating_temperature_c,
            findings=[
                ThermodynamicFindingResponse(
                    severity=f.severity.value,
                    category=f.category.value,
                    title=f.title,
                    description=f.description,
                    recommendation=f.recommendation,
                    technical_details=f.technical_details,
                    detected_at=f.detected_at,
                )
                for f in report.findings
            ],
            fluid_composition=report.fluid_composition,
            thermodynamic_state=report.thermodynamic_state,
            audit_timestamp=report.audit_timestamp,
            calculation_status=report.calculation_status,
            error_message=report.error_message,
            has_critical_findings=report.has_critical_findings,
            has_warnings=report.has_warnings,
        ))

    return ThermodynamicBatchAuditResponse(
        total_segments_audited=len(reports),
        critical_findings_count=critical_count,
        warning_count=warning_count,
        info_count=info_count,
        reports=report_responses,
        summary_timestamp=datetime.utcnow().isoformat(),
    )


@app.get(
    "/api/audit/thermodynamic/pipeline/{doc_id}",
    response_model=ThermodynamicBatchAuditResponse,
    tags=["Thermodynamic Safety Audit"],
)
async def audit_document_pipeline(
    doc_id: str,
    operating_pressure_bar: float = Query(..., gt=0, le=1000,
        description="Operating pressure in bara"
    ),
    operating_temperature_c: float = Query(...,
        ge=-200, le=1000,
        description="Operating temperature in Celsius"
    ),
    fluid_composition: Optional[str] = Query(None,
        description="JSON string of fluid composition (mole fractions)"
    ),
    db: Session = Depends(get_db),
):
    """
    Audit all pipeline segments from a processed P&ID document.

    This endpoint retrieves the connectivity graph from a processed document
    and performs thermodynamic safety audits on all identified pipe segments.

    **Parameters:**
    - `doc_id`: Document ID from a previously processed P&ID
    - `operating_pressure_bar`: Operating pressure in bara
    - `operating_temperature_c`: Operating temperature in °C
    - `fluid_composition`: Optional JSON string of custom fluid composition

    **Returns:**
    - Batch audit results for all pipeline segments in the document
    """
    document = db.query(Document).filter(Document.id == doc_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")

    if document.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Document not ready for audit. Current status: {document.status}",
        )

    # Build connectivity graph
    graph = graph_engine.build_connectivity_graph(doc_id, db)

    # Parse fluid composition if provided
    composition = None
    if fluid_composition:
        try:
            composition = json.loads(fluid_composition)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail="Invalid fluid_composition JSON string",
            )

    # Run batch audit
    reports = thermodynamic_auditor.batch_audit_pipeline(
        graph=graph,
        operating_pressure_bar=operating_pressure_bar,
        operating_temperature_c=operating_temperature_c,
        fluid_composition=composition,
    )

    # Convert reports to response format
    report_responses = []
    critical_count = 0
    warning_count = 0
    info_count = 0

    for report in reports:
        for finding in report.findings:
            if finding.severity.value == "Critical":
                critical_count += 1
            elif finding.severity.value == "Warning":
                warning_count += 1
            elif finding.severity.value == "Info":
                info_count += 1

        report_responses.append(ThermodynamicAuditResponse(
            audit_id=report.audit_id,
            pipe_node_id=report.pipe_node_id,
            line_spec=report.line_spec,
            operating_pressure_bar=report.operating_pressure_bar,
            operating_temperature_c=report.operating_temperature_c,
            findings=[
                ThermodynamicFindingResponse(
                    severity=f.severity.value,
                    category=f.category.value,
                    title=f.title,
                    description=f.description,
                    recommendation=f.recommendation,
                    technical_details=f.technical_details,
                    detected_at=f.detected_at,
                )
                for f in report.findings
            ],
            fluid_composition=report.fluid_composition,
            thermodynamic_state=report.thermodynamic_state,
            audit_timestamp=report.audit_timestamp,
            calculation_status=report.calculation_status,
            error_message=report.error_message,
            has_critical_findings=report.has_critical_findings,
            has_warnings=report.has_warnings,
        ))

    return ThermodynamicBatchAuditResponse(
        total_segments_audited=len(reports),
        critical_findings_count=critical_count,
        warning_count=warning_count,
        info_count=info_count,
        reports=report_responses,
        summary_timestamp=datetime.utcnow().isoformat(),
    )


# =============================================================================
# Export Endpoints
# =============================================================================

@app.get("/api/export/excel/{doc_id}", response_class=FileResponse)
async def get_excel_export(doc_id: str, db: Session = Depends(get_db)):
    """Export structured multi-tab Excel model."""
    excel_path = export_engine.export_excel(doc_id, db)
    return FileResponse(
        excel_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"PID_Structured_Model_{doc_id[:8]}.xlsx",
    )


@app.get("/api/export/pdf-report/{doc_id}", response_class=FileResponse)
async def get_pdf_report_export(doc_id: str, db: Session = Depends(get_db)):
    """Export professional executive PDF drawing report (Tables & text)."""
    pdf_path = export_engine.export_pdf(doc_id, db)
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"PID_Executive_Report_{doc_id[:8]}.pdf",
    )


@app.get("/api/export/pdf-drawing/{doc_id}", response_class=FileResponse)
async def get_pdf_drawing_export(
    doc_id: str,
    tag: str = None,
    rule: str = None,
    db: Session = Depends(get_db),
):
    """Export original P&ID PDF drawing with extra coloring/highlights."""
    pdf_path = export_engine.export_enhanced_pdf(doc_id, db, target_tag=tag, color_rule=rule)
    filename_suffix = f"_{tag or rule or 'master'}"
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"PID_Enhanced_Drawing_{doc_id[:8]}{filename_suffix}.pdf",
    )


# =============================================================================
# DEXPI Export Endpoints
# =============================================================================

@app.get(
    "/api/export/dexpi/status",
    response_model=DEXPIExportStatusResponse,
    tags=["DEXPI Export"],
)
async def get_dexpi_status():
    """
    Check pyDEXPI library availability and DEXPI export capabilities.

    Returns:
        - Whether pyDEXPI is installed
        - Python version compatibility
        - Supported DEXPI version
    """
    import sys

    python_version_ok = sys.version_info >= (3, 12)

    return {
        "dexpi_available": PYDEXPI_AVAILABLE,
        "python_version_supported": python_version_ok,
        "status": "operational" if (PYDEXPI_AVAILABLE and python_version_ok) else "unavailable",
        "supported_dexpi_version": "1.3",
    }


@app.post(
    "/api/export/dexpi/{doc_id}",
    response_model=DEXPIExportResultResponse,
    tags=["DEXPI Export"],
)
async def export_document_to_dexpi(
    doc_id: str,
    db: Session = Depends(get_db),
):
    """
    Export a processed P&ID document to DEXPI Proteus XML format.

    This endpoint converts the detected P&ID entities and connections into
    official DEXPI (Data Exchange in the Process Industry) format.

    **DEXPI Node Type Mappings:**
    - Vessel/Tank/Drum → DEXPI Vessel
    - Pump → DEXPI CentrifugalPump
    - HeatExchanger → DEXPI ShellAndTubeHeatExchanger
    - Valve → DEXPI GateValve
    - Pipeline/Pipe/Line → DEXPI PipingNetworkSegment
    - Instrument → DEXPI ProcessInstrumentationFunction

    **Parameters:**
    - `doc_id`: Document ID from a previously processed P&ID

    **Returns:**
    - Export result with statistics
    - Path to generated XML file
    """
    if not PYDEXPI_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail=(
                "pyDEXPI library not available. "
                "Install with: pip install pydexpi "
                "(requires Python >= 3.12)"
            ),
        )

    document = db.query(Document).filter(Document.id == doc_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Export to DEXPI
    try:
        output_path, result = export_engine.export_dexpi_xml(doc_id, db)
        return DEXPIExportResultResponse(
            success=result.success,
            output_path=result.output_path,
            error_message=result.error_message,
            nodes_exported=result.nodes_exported,
            edges_exported=result.edges_exported,
            warnings=result.warnings,
            exported_objects=result.exported_objects,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"DEXPI export failed: {str(e)}",
        )


@app.post(
    "/api/export/dexpi/direct",
    response_model=DEXPIExportResultResponse,
    tags=["DEXPI Export"],
)
async def export_graph_to_dexpi(
    request: DEXPIExportRequest,
):
    """
    Export a NetworkX graph directly to DEXPI Proteus XML format.

    This endpoint accepts a serialized graph and exports it to DEXPI format
    without requiring a stored document in the database.

    **Request Body:**
    - `graph_data`: Serialized NetworkX graph with nodes and edges
    - `project_name`: Optional project name for DEXPI metadata
    - `author`: Optional author name for DEXPI metadata
    - `strict_mapping`: If true, fail on unrecognized node types

    **Returns:**
    - Export result with statistics
    """
    if not PYDEXPI_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail=(
                "pyDEXPI library not available. "
                "Install with: pip install pydexpi "
                "(requires Python >= 3.12)"
            ),
        )

    # Convert Pydantic model to NetworkX graph
    G = nx.DiGraph()

    # Add nodes
    for node in request.graph_data.nodes:
        G.add_node(
            node.id,
            tag=node.tag or f"NODE-{node.id[:8]}",
            type=node.type or "Unknown",
            spec=node.spec or node.line_spec or "",
            attributes=node.attributes or {},
        )

    # Add edges
    for edge in request.graph_data.edges:
        G.add_edge(
            edge.source,
            edge.target,
            spec=edge.spec or "",
            flow=edge.flow or "forward",
        )

    # Determine output path
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(settings.EXPORT_DIR, f"dexpi_export_{timestamp}.xml")

    # Export options
    from export_engine import DEXPIExportOptions

    options = DEXPIExportOptions(
        project_name=request.project_name,
        author=request.author,
        strict_mapping=request.strict_mapping,
    )

    # Perform export
    try:
        from export_engine import export_graph_to_dexpi_xml as dexpi_export_func

        result = dexpi_export_func(G, output_path, options)

        return DEXPIExportResultResponse(
            success=result.success,
            output_path=result.output_path,
            error_message=result.error_message,
            nodes_exported=result.nodes_exported,
            edges_exported=result.edges_exported,
            warnings=result.warnings,
            exported_objects=result.exported_objects,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"DEXPI export failed: {str(e)}",
        )


@app.get(
    "/api/export/dexpi/download/{doc_id}",
    response_class=FileResponse,
    tags=["DEXPI Export"],
)
async def download_dexpi_export(
    doc_id: str,
    db: Session = Depends(get_db),
):
    """
    Generate and download a DEXPI Proteus XML file for a processed document.

    This endpoint combines export and download in one step.
    """
    if not PYDEXPI_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail=(
                "pyDEXPI library not available. "
                "Install with: pip install pydexpi"
            ),
        )

    document = db.query(Document).filter(Document.id == doc_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")

    try:
        output_path, result = export_engine.export_dexpi_xml(doc_id, db)

        if not result.success:
            raise HTTPException(
                status_code=500,
                detail=f"DEXPI export failed: {result.error_message}",
            )

        return FileResponse(
            output_path,
            media_type="application/xml",
            filename=f"PID_DEXPI_{doc_id[:8]}.xml",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"DEXPI export failed: {str(e)}",
        )


# =============================================================================
# Application Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=7860,
        reload=settings.DEBUG,
    )
