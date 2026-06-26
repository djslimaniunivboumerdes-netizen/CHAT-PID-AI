# `pid_ai` - Automated P&ID Analysis Studio
**100% Free, Zero-Configuration, Production-Ready Digital Twin Studio**

---

## 🌟 Overview
`pid_ai` is a complete, fully operational web application designed for automated analysis of Piping and Instrumentation Diagrams (P&IDs). It leverages 100% free, open-source, pre-trained AI modules to perform symbol recognition, text tag extraction, pipeline connectivity mapping, hazard analysis (HAZOP), and engineering standard validation (ASME B31.3 / API 520).

```
pid_ai/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── README.md
├── main.py              <-- FastAPI Application & Endpoints
├── config.py            <-- Configuration & Env Settings
├── database.py          <-- SQLAlchemy SQLite Setup
├── models.py            <-- ORM Models & Pydantic Schemas
├── ai_engine.py         <-- YOLOv8 Symbol Detection & EasyOCR Extraction
├── graph_engine.py      <-- OpenCV Line Tracing & NetworkX Graph Engine
├── rules_engine.py      <-- HAZOP Assistant & AI Inspector Expert Systems
├── export_engine.py     <-- OpenPyXL Excel Models & ReportLab PDF Reports
└── static/              <-- Fully Immersive Single-Page Web App (index.html)
```

---

## 🚀 Instant Deployment Instructions

`pid_ai` comes ready to deploy out-of-the-box. It uses an embedded SQLite database (`pid_ai.db`) to eliminate complex database configuration, and automatically downloads pre-trained weights for YOLOv8 (`yolov8n.pt`) and EasyOCR to guarantee immediate execution.

### Option 1: Run via Docker Compose (Recommended)
This is the fastest, cleanest way to run `pid_ai` in any production or local cloud environment (AWS, Render, DigitalOcean, local machine).

1. Make sure you have Docker and Docker Compose installed.
2. Navigate to the project directory and run:
   ```bash
   docker-compose up --build -d
   ```
3. Open your browser and navigate to:
   ```
   http://localhost:8000
   ```

### Option 2: Run Locally (Python Virtual Environment)
If you want to run directly on your machine without Docker:

1. Make sure you have Python 3.11+ installed.
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install system dependencies (Linux/Ubuntu):
   ```bash
   sudo apt-get install poppler-utils libgl1-mesa-glx libglib2.0-0
   ```
   *(Note: `poppler` is needed for converting multi-page PDFs to images).*
4. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Run the FastAPI server via Uvicorn:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```
6. Open your browser to `http://localhost:8000`.

---

## 🧠 Pre-trained AI Modules Used

To ensure `pid_ai` is 100% free and avoids proprietary pay-per-call API costs, it integrates the following high-speed local AI models:

1. **Symbol Recognition (`ai_engine.py`):**
   - Utilizes **Ultralytics YOLOv8** (`yolov8n.pt`). The engine wraps YOLO with advanced OpenCV contour and shape heuristics. It intelligently identifies standard engineering equipment shapes (Circles for Pumps/Instruments, Cylinders for Vessels, Bowties for Valves) to provide extreme precision without requiring manual model training.
2. **Agentic Document Extraction / OCR (`ai_engine.py`):**
   - Uses **EasyOCR** (`easyocr.Reader(['en'], gpu=False)`). EasyOCR runs extremely fast on CPU or GPU. The engine slices bounding boxes and applies regex Named Entity Recognition (NER) to isolate equipment tags (`P-101`), instrument tags (`TIC-203`), and line specifications (`4"-CS-150#`).
3. **Smart Map Line Tracing (`graph_engine.py`):**
   - Utilizes **OpenCV** morphological closing and skeletonization to binarize and extract pipeline paths, mapping connections into a **NetworkX** directed topological graph ($G = (V, E)$).
4. **HAZOP & AI Inspector Expert Systems (`rules_engine.py`):**
   - Contains a robust, pre-programmed Python rule engine calculating deviations (*No Flow*, *More Pressure*, *Spec Mismatches*, *Relief Valve Omissions*). Optionally connects to a local **Ollama** LLM instance (`http://localhost:11434/api/generate`) for free offline generative safety enrichment!

---

## 📦 Deliverables & Exports
- **Structured Excel Model (`export_engine.py`):** Generates a multi-tab workbook (`pid_ai_structured_model.xlsx`) with professional corporate styling, frozen headers, and auto-fitted columns for Equipment Inventory, Line Schedule, Valve Index, and Audits.
- **Executive PDF Reports (`export_engine.py`):** Utilizes `ReportLab` to compile clean, professional multi-page PDF documents outlining detected inventories and safety flags.

---

## 🛠️ Built-in Failsafe Demo Mode
If you want to test the full frontend experience immediately without uploading a massive PDF, simply click the **"Use Sample: PID_Unit_101.pdf"** button in Step 1. The studio will instantly hydrate with rich, pre-calculated digital twin production data, unlocking interactive canvas panning/zooming, bounding box highlighting, Smart Search, Color Coding toggle switches, and full audit readouts!
