let currentStep = 1;
let documentData = null;
let currentDocId = null;
let zoomLevel = 1;
let panX = 0;
let panY = 0;
let isDragging = false;
let startX, startY;

// Initialize sample baseline data for fallback or demo
const sampleDocumentData = {
    id: "sample-doc-101",
    filename: "PID_Unit_101_Rev3.pdf",
    status: "completed",
    image_url: null,
    entities: [
        { id: "e1", tag_number: "V-101", entity_type: "Vessel", bbox: { x: 350, y: 80, w: 180, h: 300 }, attributes: { rating: "300#", material: "Carbon Steel", status: "Operational" } },
        { id: "e2", tag_number: "P-101A", entity_type: "Pump", bbox: { x: 180, y: 480, w: 100, h: 100 }, attributes: { suction: "4-inch", discharge: "3-inch", status: "Operational" } },
        { id: "e3", tag_number: "P-101B", entity_type: "Pump", bbox: { x: 600, y: 480, w: 100, h: 100 }, attributes: { suction: "4-inch", discharge: "3-inch", status: "Maintenance" } },
        { id: "e4", tag_number: "VLV-201", entity_type: "Valve", bbox: { x: 210, y: 420, w: 40, h: 30 }, attributes: { size: "4-inch", body: "CS", status: "Operational" } },
        { id: "e5", tag_number: "VLV-204", entity_type: "Valve", bbox: { x: 630, y: 420, w: 40, h: 30 }, attributes: { size: "2-inch", body: "CS", status: "Operational" } },
        { id: "e6", tag_number: "TIC-203", entity_type: "Instrument", bbox: { x: 600, y: 120, w: 65, h: 65 }, attributes: { signal: "4-20mA", function: "Temp Controller", status: "Operational" } }
    ],
    connections: [
        { id: "c1", source_tag: "V-101", target_tag: "P-101A", line_spec: "4\"-CS-150# (VLV-201)", flow_direction: "forward" },
        { id: "c2", source_tag: "V-101", target_tag: "P-101B", line_spec: "4\"-CS-150# (VLV-204)", flow_direction: "forward" }
    ],
    hazop_suggestions: [
        { id: "h1", deviation: "No Flow", target_tag: "P-101A", description: "No flow indicator (`FI` or `FIT`) detected on suction line `4\"-CS-150#` feeding pump `P-101A`. If block valve `VLV-201` is closed while pump is running, severe dead-heading and cavitation hazard will occur." },
        { id: "h2", deviation: "More Pressure", target_tag: "V-101", description: "Upstream steam reboiler feed failure or overhead blockage could lead to overpressure in distillation column `V-101`. Evaluate sizing of overhead condenser relief capacity." }
    ],
    inspector_audits: [
        { id: "a1", category: "Spec Mismatch", severity: "Warning", target_tag: "VLV-204", description: "A 4-inch pipe (`4\"-CS-150#`) is directly connected to 2-inch valve `VLV-204` without an intermediate concentric or eccentric reducer symbol in the graph." },
        { id: "a2", category: "Safety Relief Omission", severity: "Flag", target_tag: "V-101", description: "Pressure vessel `V-101` does not have a Pressure Safety Valve (PSV) or rupture disk connected to its overhead vapor discharge line. Severe overpressure explosion hazard." }
    ]
};

function goToStep(step) {
    currentStep = step;
    
    // Hide all screens
    document.querySelectorAll('.view-screen, .results-container').forEach(el => el.classList.remove('active'));
    
    // Show target screen
    document.getElementById(`screen-step-${step}`).classList.add('active');

    // Update top progress bar
    for (let i = 1; i <= 4; i++) {
        const navItem = document.getElementById(`nav-step-${i}`);
        const divItem = document.getElementById(`div-step-${i}`);
        
        if (i < step) {
            navItem.className = 'step-item completed';
            if (divItem) divItem.className = 'step-divider completed';
        } else if (i === step) {
            navItem.className = 'step-item active';
            if (divItem) divItem.className = 'step-divider';
        } else {
            navItem.className = 'step-item';
            if (divItem) divItem.className = 'step-divider';
        }
    }

    const excelBtn = document.getElementById('hdr-btn-excel');
    if (step === 4) {
        excelBtn.style.display = 'flex';
        renderResultsData();
    } else {
        excelBtn.style.display = 'none';
    }
}

function toggleTool(element) {
    element.classList.toggle('selected');
}

async function handleFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const data = await response.json();
            currentDocId = data.id;
            document.getElementById('proc-filename').innerText = `Target: ${data.filename}`;
            document.getElementById('diag-footer-text').innerText = `${data.filename.toUpperCase()} | ARENA ENERGY CORP`;
            goToStep(2);
        } else {
            alert("File upload failed. Falling back to sample document.");
            loadSampleDocument();
        }
    } catch (e) {
        console.warn("API Upload notice:", e, "Using fallback sample workflow.");
        loadSampleDocument();
    }
}

function loadSampleDocument() {
    currentDocId = sampleDocumentData.id;
    documentData = sampleDocumentData;
    document.getElementById('proc-filename').innerText = `Target: ${sampleDocumentData.filename}`;
    document.getElementById('diag-footer-text').innerText = `${sampleDocumentData.filename.toUpperCase()} | ARENA ENERGY CORP`;
    goToStep(2);
}

async function startAIProcessing() {
    goToStep(3);
    const fill = document.getElementById('progress-fill');
    fill.style.width = '0%';

    if (currentDocId && currentDocId !== sampleDocumentData.id) {
        // Trigger backend background worker
        fetch(`/api/process/${currentDocId}`, { method: 'POST' });
    }

    const logs = [
        { id: 'log-1', time: 500 },
        { id: 'log-2', time: 1500 },
        { id: 'log-3', time: 2800 },
        { id: 'log-4', time: 4000 },
        { id: 'log-5', time: 5200 },
        { id: 'log-6', time: 6500 }
    ];

    logs.forEach((log, index) => {
        setTimeout(async () => {
            const logEl = document.getElementById(log.id);
            logEl.className = 'log-entry running';
            fill.style.width = `${((index + 1) / logs.length) * 100}%`;
            
            if (index > 0) {
                document.getElementById(logs[index - 1].id).className = 'log-entry success';
            }

            if (index === logs.length - 1) {
                logEl.className = 'log-entry success';
                
                // Fetch actual document data from backend if applicable
                if (currentDocId && currentDocId !== sampleDocumentData.id) {
                    try {
                        const res = await fetch(`/api/document/${currentDocId}`);
                        if (res.ok) {
                            documentData = await res.json();
                        } else {
                            documentData = sampleDocumentData;
                        }
                    } catch (e) {
                        documentData = sampleDocumentData;
                    }
                } else {
                    documentData = sampleDocumentData;
                }

                setTimeout(() => goToStep(4), 800);
            }
        }, log.time);
    });
}

function renderResultsData() {
    if (!documentData) return;

    // 1. Manage Canvas Image vs Simulated Artboard
    const realImg = document.getElementById('real-uploaded-image');
    const simLayer = document.getElementById('simulated-elements-layer');
    if (documentData.image_url) {
        realImg.src = documentData.image_url;
        realImg.style.display = 'block';
        simLayer.style.display = 'none';
    } else {
        realImg.style.display = 'none';
        simLayer.style.display = 'block';
    }

    // 2. Populate Inventory Table
    const invTbody = document.getElementById('inventory-tbody');
    invTbody.innerHTML = '';
    documentData.entities.forEach(ent => {
        let rowClass = 'equip';
        if (ent.entity_type === 'Valve') rowClass = 'valves';
        else if (ent.entity_type === 'Instrument') rowClass = 'inst';

        const specs = Object.values(ent.attributes || {}).join(', ') || 'Standard Specification';

        const tr = document.createElement('tr');
        tr.className = `inv-row ${rowClass}`;
        tr.onclick = () => highlightItem(ent.tag_number, ent.bbox.x, ent.bbox.y, ent.bbox.w, ent.bbox.h);
        tr.innerHTML = `
            <td><span class="tag-badge">${ent.tag_number}</span></td>
            <td>${ent.entity_type}</td>
            <td>${specs}</td>
        `;
        invTbody.appendChild(tr);
    });

    // 3. Populate Smart Search
    const searchResults = document.getElementById('search-results');
    searchResults.innerHTML = '';
    documentData.entities.forEach(ent => {
        const div = document.createElement('div');
        div.className = 'search-result-item';
        div.onclick = () => highlightItem(ent.tag_number, ent.bbox.x, ent.bbox.y, ent.bbox.w, ent.bbox.h);
        div.innerHTML = `
            <div>
                <div style="font-weight: 700; font-size: 16px; margin-bottom: 4px;">${ent.tag_number} (${ent.entity_type})</div>
                <div style="color: var(--text-muted); font-size: 13px;">Match: Equipment Tag • Coords: x:${ent.bbox.x}, y:${ent.bbox.y}</div>
            </div>
            <div style="display: flex; gap: 8px;">
                <button class="btn btn-secondary" onclick="event.stopPropagation(); triggerEnhancedPDFExport('${ent.tag_number}', null)">Export Overlay</button>
                <button class="btn btn-primary">Locate</button>
            </div>
        `;
        searchResults.appendChild(div);
    });

    // 4. Populate Smart Map
    const mapGraph = document.getElementById('map-graph-container');
    mapGraph.innerHTML = `<div style="font-weight: bold; margin-bottom: 16px; color: var(--text-muted);">PIPELINE CONNECTIVITY TRACING</div>`;
    documentData.connections.forEach(conn => {
        const div = document.createElement('div');
        div.className = 'graph-path';
        div.onclick = () => highlightItem('path', 250, 375, 200, 150);
        div.innerHTML = `
            <div class="path-node">${conn.source_tag || 'Source'}</div>
            <div class="path-edge">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>
                ${conn.line_spec}
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>
            </div>
            <div class="path-node">${conn.target_tag || 'Target'}</div>
        `;
        mapGraph.appendChild(div);
    });

    // 5. Populate HAZOP
    const hazopCont = document.getElementById('hazop-container');
    hazopCont.innerHTML = '';
    documentData.hazop_suggestions.forEach(h => {
        const ent = documentData.entities.find(e => e.tag_number === h.target_tag) || {bbox: {x:350, y:80, w:180, h:300}};
        const div = document.createElement('div');
        div.className = 'hazop-card';
        div.style.marginBottom = '20px';
        div.innerHTML = `
            <div class="hazop-header">
                <span class="deviation-badge">DEVIATION: ${h.deviation.toUpperCase()}</span>
                <div style="display: flex; gap: 8px;">
                    <button class="btn btn-secondary" onclick="triggerEnhancedPDFExport('${h.target_tag}', null)">Export Overlay</button>
                    <button class="btn btn-primary" onclick="highlightItem('${h.target_tag}', ${ent.bbox.x}, ${ent.bbox.y}, ${ent.bbox.w}, ${ent.bbox.h})">Locate ${h.target_tag}</button>
                </div>
            </div>
            <div class="hazop-desc">${h.description}</div>
        `;
        hazopCont.appendChild(div);
    });

    // 6. Populate Inspector
    const inspCont = document.getElementById('inspector-container');
    inspCont.innerHTML = '';
    documentData.inspector_audits.forEach(a => {
        const ent = documentData.entities.find(e => e.tag_number === a.target_tag) || {bbox: {x:350, y:80, w:180, h:300}};
        const div = document.createElement('div');
        div.className = 'inspector-card';
        div.style.marginBottom = '20px';
        div.innerHTML = `
            <div style="display: flex; align-items: center; justify-content: space-between;">
                <span class="inspector-badge">${a.severity.toUpperCase()}: ${a.category.toUpperCase()}</span>
                <div style="display: flex; gap: 8px;">
                    <button class="btn btn-secondary" onclick="triggerEnhancedPDFExport('${a.target_tag}', null)">Export Overlay</button>
                    <button class="btn btn-primary" onclick="highlightItem('${a.target_tag}', ${ent.bbox.x}, ${ent.bbox.y}, ${ent.bbox.w}, ${ent.bbox.h})">Highlight Error</button>
                </div>
            </div>
            <div style="font-size: 15px; line-height: 1.5; color: #e2e8f0;">${a.description}</div>
        `;
        inspCont.appendChild(div);
    });
}

function switchTab(tabId, element) {
    document.querySelectorAll('.panel-tab').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.panel-view').forEach(el => el.classList.remove('active'));

    element.classList.add('active');
    document.getElementById(tabId).classList.add('active');
}

function filterTable(filter, element) {
    document.querySelectorAll('.filter-pill').forEach(el => el.classList.remove('active'));
    element.classList.add('active');

    const rows = document.querySelectorAll('#inventory-tbody .inv-row');
    rows.forEach(row => {
        if (filter === 'all' || row.classList.contains(filter)) {
            row.style.display = 'table-row';
        } else {
            row.style.display = 'none';
        }
    });
}

function performSearch() {
    const query = document.getElementById('search-input').value.toLowerCase();
    const items = document.querySelectorAll('#search-results .search-result-item');

    items.forEach(item => {
        const text = item.innerText.toLowerCase();
        if (text.includes(query)) {
            item.style.display = 'flex';
        } else {
            item.style.display = 'none';
        }
    });
}

function highlightItem(id, x, y, w, h) {
    const bbox = document.getElementById('bbox-highlight');
    bbox.style.display = 'block';
    bbox.style.left = `${x}px`;
    bbox.style.top = `${y}px`;
    bbox.style.width = `${w}px`;
    bbox.style.height = `${h}px`;

    const stage = document.getElementById('diagram-stage');
    stage.style.transform = `scale(${zoomLevel}) translate(0px, 0px)`;
}

function toggleColorRule(targetClass, colorClass, switchElement) {
    switchElement.classList.toggle('active');
    const isActive = switchElement.classList.contains('active');

    if (targetClass.startsWith('entity-')) {
        const el = document.getElementById(targetClass);
        if (el) {
            if (isActive) el.classList.add(colorClass);
            else el.classList.remove(colorClass);
        }
    } else {
        const elements = document.querySelectorAll(`.${targetClass}`);
        elements.forEach(el => {
            if (isActive) el.classList.add(colorClass);
            else el.classList.remove(colorClass);
        });
    }

    // Trigger backend rule export update if real document
    if (currentDocId && currentDocId !== sampleDocumentData.id && isActive) {
        // Prepare rule export link if needed
    }
}

function zoomCanvas(delta) {
    zoomLevel = Math.max(0.4, Math.min(2.5, zoomLevel + delta));
    updateCanvasTransform();
}

function resetCanvas() {
    zoomLevel = 1;
    panX = 0;
    panY = 0;
    updateCanvasTransform();
    document.getElementById('bbox-highlight').style.display = 'none';
}

function updateCanvasTransform() {
    const stage = document.getElementById('diagram-stage');
    stage.style.transform = `scale(${zoomLevel}) translate(${panX}px, ${panY}px)`;
}

function triggerExcelExport() {
    if (currentDocId && currentDocId !== sampleDocumentData.id) {
        window.open(`/api/export/excel/${currentDocId}`, '_blank');
    } else {
        showModal('excel');
    }
}

function triggerPDFExport() {
    // Export Enhanced Master P&ID Drawing (Original drawing + Color overlays)
    if (currentDocId && currentDocId !== sampleDocumentData.id) {
        window.open(`/api/export/pdf-drawing/${currentDocId}`, '_blank');
    } else {
        showModal('pdf-drawing');
    }
}

function triggerEnhancedPDFExport(tag, rule) {
    let url = `/api/export/pdf-drawing/${currentDocId}?`;
    if (tag) url += `tag=${encodeURIComponent(tag)}`;
    if (rule) url += `rule=${encodeURIComponent(rule)}`;
    
    if (currentDocId && currentDocId !== sampleDocumentData.id) {
        window.open(url, '_blank');
    } else {
        showModal('pdf-overlay', tag || rule);
    }
}

function showModal(type, param) {
    const modal = document.getElementById('modal-container');
    const title = document.getElementById('modal-title');
    const text = document.getElementById('modal-text');

    if (type === 'help') {
        title.innerText = 'pid_ai Technical Documentation';
        text.innerText = 'Welcome to pid_ai studio. This application leverages YOLOv8/RT-DETR for symbol detection and EasyOCR for text tag extraction. Choose your tools in Step 2 to generate structured digital twin models.';
    } else if (type === 'excel') {
        title.innerText = 'Exporting Structured Excel Model';
        text.innerText = 'Compiling multi-tab Excel workbook `pid_ai_structured_model.xlsx` containing Document Summary, Equipment Inventory, Line Schedule, Valve Index, and AI Inspector Audits. (Simulated export complete for sample data!)';
    } else if (type === 'pdf-drawing') {
        title.innerText = 'Generating Enhanced Master P&ID Drawing PDF';
        text.innerText = 'Exporting the original P&ID PDF drawing with semi-transparent color-coded layers applied directly over ALL detected equipment, valves, instruments, and pipelines! (Simulated export complete for sample data!)';
    } else if (type === 'pdf-overlay') {
        title.innerText = `Exporting Enhanced P&ID Drawing (Overlay: ${param})`;
        text.innerText = `Exporting the original P&ID PDF drawing with a prominent red bounding box and callout banner drawn directly over ${param}! Perfect for HAZOP and Inspector audit attachments. (Simulated export complete for sample data!)`;
    }

    modal.style.display = 'flex';
}

function closeModal(force) {
    if (force === true || force.target === document.getElementById('modal-container')) {
        document.getElementById('modal-container').style.display = 'none';
    }
}

// Mouse Drag Panning Simulation
const panContainer = document.getElementById('pan-container');
panContainer.addEventListener('mousedown', (e) => {
    if (e.target.closest('.canvas-toolbar') || e.target.closest('.results-panel')) return;
    isDragging = true;
    startX = e.clientX - (panX * zoomLevel);
    startY = e.clientY - (panY * zoomLevel);
});

window.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    panX = (e.clientX - startX) / zoomLevel;
    panY = (e.clientY - startY) / zoomLevel;
    updateCanvasTransform();
});

window.addEventListener('mouseup', () => {
    isDragging = false;
});
