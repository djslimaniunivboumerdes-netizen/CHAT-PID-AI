import os
import uuid
import shutil
from fastapi import FastAPI, Depends, UploadFile, File, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from config import settings
from database import engine, Base, get_db
from models import Document, DocumentResponse, Entity, Connection, HazopSuggestion, InspectorAudit
from ai_engine import ai_engine
from graph_engine import graph_engine
from rules_engine import rules_engine
from export_engine import export_engine

# Initialize Database Tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI Application
app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, description="Automated AI Analysis Studio for P&IDs")

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

@app.get("/", response_class=FileResponse)
async def serve_index():
    """Serve the main interactive single-page studio web application."""
    return os.path.join(settings.STATIC_DIR, "index.html")

@app.post("/api/upload", response_model=DocumentResponse)
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """STEP 1: Upload PDF or Image containing P&ID."""
    doc_id = str(uuid.uuid4())
    ext = file.filename.split('.')[-1].lower()
    if ext not in ["pdf", "png", "jpg", "jpeg", "tiff"]:
        raise HTTPException(status_code=400, detail="Unsupported file format. Please upload PDF, PNG, JPG, or TIFF.")

    save_path = os.path.join(settings.UPLOAD_DIR, f"{doc_id}.{ext}")
    
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Create Database Record
    doc = Document(id=doc_id, filename=file.filename, filepath=save_path, status="uploaded")
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
async def start_processing(doc_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """STEP 3: Trigger AI Processing Engine background worker."""
    document = db.query(Document).filter(Document.id == doc_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")

    background_tasks.add_task(run_background_processing, doc_id, db)
    return {"status": "processing_started", "document_id": doc_id}

@app.get("/api/document/{doc_id}", response_model=DocumentResponse)
async def get_document_results(doc_id: str, db: Session = Depends(get_db)):
    """STEP 4: Fetch full digital twin inventory and analytics results."""
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
            "target_tag": ent_map.get(c.target_id, "Unknown")
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
        "inspector_audits": audits
    }

@app.get("/api/export/excel/{doc_id}", response_class=FileResponse)
async def get_excel_export(doc_id: str, db: Session = Depends(get_db)):
    """Export structured multi-tab Excel model."""
    excel_path = export_engine.export_excel(doc_id, db)
    return FileResponse(excel_path, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=f"PID_Structured_Model_{doc_id[:8]}.xlsx")

@app.get("/api/export/pdf-report/{doc_id}", response_class=FileResponse)
async def get_pdf_report_export(doc_id: str, db: Session = Depends(get_db)):
    """Export professional executive PDF drawing report (Tables & text)."""
    pdf_path = export_engine.export_pdf(doc_id, db)
    return FileResponse(pdf_path, media_type="application/pdf", filename=f"PID_Executive_Report_{doc_id[:8]}.pdf")

@app.get("/api/export/pdf-drawing/{doc_id}", response_class=FileResponse)
async def get_pdf_drawing_export(doc_id: str, tag: str = None, rule: str = None, db: Session = Depends(get_db)):
    """Export original P&ID PDF drawing with extra coloring/highlights over specific equipment or components."""
    pdf_path = export_engine.export_enhanced_pdf(doc_id, db, target_tag=tag, color_rule=rule)
    filename_suffix = f"_{tag or rule or 'master'}"
    return FileResponse(pdf_path, media_type="application/pdf", filename=f"PID_Enhanced_Drawing_{doc_id[:8]}{filename_suffix}.pdf")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=7860, reload=True)
