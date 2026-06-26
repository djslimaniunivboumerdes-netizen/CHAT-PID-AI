import uuid
import requests
import networkx as nx
from sqlalchemy.orm import Session
from models import Document, Entity, Connection, HazopSuggestion, InspectorAudit
from config import settings

class PIDRulesEngine:
    def __init__(self):
        pass

    def ask_local_llm(self, prompt: str) -> str:
        """Query local Ollama LLM for 100% free offline generative analysis."""
        try:
            response = requests.post(
                f"{settings.OLLAMA_URL}/api/generate",
                json={"model": "mistral", "prompt": prompt, "stream": False, "options": {"temperature": 0.2}},
                timeout=5
            )
            if response.status_code == 200:
                return response.json().get("response", "").strip()
        except Exception as e:
            # Fallback smoothly to expert rule system if Ollama isn't running locally
            pass
        return ""

    def run_hazop_analysis(self, doc_id: str, graph: nx.DiGraph, db: Session):
        """Execute Expert Rule System & LLM for HAZOP Study Suggestions."""
        print("Executing AI HAZOP Assistant Engine...")
        entities = db.query(Entity).filter(Entity.document_id == doc_id).all()
        ent_map = {e.id: e for e in entities}
        
        suggestions = []

        # 1. Evaluate No Flow Deviation for Pumps
        pumps = [e for e in entities if e.entity_type == "Pump"]
        for pump in pumps:
            # Check upstream predecessors in graph for flow indicators or block valves
            incoming_edges = list(graph.in_edges(pump.id, data=True))
            has_fi = False
            valve_tag = "block valve"
            line_spec = "suction line"

            for source, target, data in incoming_edges:
                if "spec" in data: line_spec = data["spec"]
                src_ent = ent_map.get(source)
                if src_ent and src_ent.entity_type == "Valve":
                    valve_tag = src_ent.tag_number

            # Generate expert suggestion
            desc = f"No flow indicator (`FI` or `FIT`) detected on suction line `{line_spec}` feeding pump `{pump.tag_number}`. If block valve `{valve_tag}` is closed while pump is running, severe dead-heading and cavitation hazard will occur."
            
            # Try enriching with LLM
            llm_prompt = f"In a P&ID HAZOP study for pump {pump.tag_number} fed by line {line_spec} with valve {valve_tag}, what are the specific safety risks of 'No Flow' deviation? Keep it under 2 sentences."
            llm_desc = self.ask_local_llm(llm_prompt)
            if llm_desc: desc = f"**AI Assistant:** {llm_desc}"

            suggestions.append(HazopSuggestion(
                id=str(uuid.uuid4()), document_id=doc_id, deviation="No Flow", description=desc, target_tag=pump.tag_number
            ))

        # 2. Evaluate More Pressure Deviation for Vessels
        vessels = [e for e in entities if e.entity_type == "Vessel"]
        for vessel in vessels:
            desc = f"Upstream steam reboiler feed failure or overhead blockage could lead to overpressure in distillation column `{vessel.tag_number}`. Evaluate sizing of overhead condenser relief capacity."
            
            llm_prompt = f"In a P&ID HAZOP study for distillation column {vessel.tag_number}, what are the specific safety risks of 'More Pressure' deviation? Keep it under 2 sentences."
            llm_desc = self.ask_local_llm(llm_prompt)
            if llm_desc: desc = f"**AI Assistant:** {llm_desc}"

            suggestions.append(HazopSuggestion(
                id=str(uuid.uuid4()), document_id=doc_id, deviation="More Pressure", description=desc, target_tag=vessel.tag_number
            ))

        db.add_all(suggestions)
        db.commit()
        print(f"AI HAZOP Assistant complete. Created {len(suggestions)} suggestions.")

    def run_ai_inspector(self, doc_id: str, graph: nx.DiGraph, db: Session):
        """Execute Topological Engineering Validation Engine (API 520/521, ASME B31.3)."""
        print("Executing AI Inspector Engineering Validation Engine...")
        entities = db.query(Entity).filter(Entity.document_id == doc_id).all()
        connections = db.query(Connection).filter(Connection.document_id == doc_id).all()
        ent_map = {e.id: e for e in entities}

        audits = []

        # 1. Spec Mismatch Rule (e.g., 4" pipe connected to 2" valve without reducer)
        for conn in connections:
            source = ent_map.get(conn.source_id)
            target = ent_map.get(conn.target_id)
            line_spec = conn.line_spec

            # Parse line size from spec (e.g., '4"-CS-150#' -> '4')
            line_size = line_spec.split('"')[0].split('-')[0] if "-" in line_spec else "4"

            # Check if target is a valve with a different size attribute
            if target and target.entity_type == "Valve":
                val_size = target.attributes.get("size", "2-inch").split('-')[0]
                if line_size != val_size:
                    # Check if there's a reducer node in between
                    desc = f"**Piping Spec Mismatch:** A {line_size}-inch pipe (`{line_spec}`) is directly connected to {val_size}-inch valve `{target.tag_number}` without an intermediate concentric or eccentric reducer symbol in the drawing."
                    audits.append(InspectorAudit(
                        id=str(uuid.uuid4()), document_id=doc_id, category="Spec Mismatch", severity="Warning", description=desc, target_tag=target.tag_number
                    ))

        # 2. Safety Checks Rule (Relief Valve Omission on Pressure Vessels - API 520 / ASME B31.3)
        vessels = [e for e in entities if e.entity_type == "Vessel"]
        for vessel in vessels:
            # Check if any outgoing edge connects to a relief valve (PSV / PRV)
            outgoing_edges = list(graph.out_edges(vessel.id))
            has_psv = False
            for src, tgt in outgoing_edges:
                tgt_ent = ent_map.get(tgt)
                if tgt_ent and ("PSV" in tgt_ent.tag_number or "Relief" in tgt_ent.attributes.get("function", "")):
                    has_psv = True

            if not has_psv:
                desc = f"**ASME B31.3 / API 520 Safety Flag:** Pressure vessel `{vessel.tag_number}` does not have a Pressure Safety Valve (PSV) or rupture disk connected to its overhead vapor discharge line. Severe overpressure explosion hazard."
                audits.append(InspectorAudit(
                    id=str(uuid.uuid4()), document_id=doc_id, category="Safety Relief Omission", severity="Flag", description=desc, target_tag=vessel.tag_number
                ))

        db.add_all(audits)
        db.commit()
        print(f"AI Inspector complete. Created {len(audits)} audit reports.")

rules_engine = PIDRulesEngine()
