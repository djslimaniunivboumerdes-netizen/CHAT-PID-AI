"""
CHAT-PID-AI: DEXPI Export Examples
===================================

This module provides examples and test cases for the DEXPI export functionality.

Run this script standalone to test DEXPI export:
    python examples/dexpi_export_example.py

Or use the FastAPI endpoints at:
    GET  /api/export/dexpi/status
    POST /api/export/dexpi/{doc_id}
    POST /api/export/dexpi/direct
    GET  /api/export/dexpi/download/{doc_id}

Author: CHAT-PID-AI Development Team
"""

import json
import networkx as nx
from pathlib import Path

from export_engine import (
    export_graph_to_dexpi_xml,
    DEXPIExportEngine,
    DEXPIExportOptions,
    DEXPIExportResult,
    PYDEXPI_AVAILABLE,
)


# =============================================================================
# Test Case 1: Simple P&ID Graph Export
# =============================================================================

def test_simple_pid_export():
    """
    Test Case: Export a simple P&ID graph with basic equipment.
    Expected: Valid DEXPI XML with vessel, pump, and valves.
    """
    print("\n" + "=" * 70)
    print("TEST 1: Simple P&ID Graph Export")
    print("=" * 70)

    # Create a simple P&ID graph
    G = nx.DiGraph()

    # Add equipment nodes
    G.add_node("V-101", tag="V-101", type="Vessel", spec='6"-CS-300#', attributes={
        "material": "Carbon Steel",
        "rating": "Class 300",
    })

    G.add_node("P-101A", tag="P-101A", type="Pump", spec='4"-CS-150#', attributes={
        "drive": "Electric Motor",
        "rating": "Class 150",
    })

    G.add_node("P-101B", tag="P-101B", type="Pump", spec='4"-CS-150#', attributes={
        "drive": "Electric Motor",
        "rating": "Class 150",
    })

    # Add valve nodes
    G.add_node("VLV-201", tag="VLV-201", type="Valve", spec='4"-CS-150#', attributes={
        "type": "Gate Valve",
        "size": "DN100",
    })

    G.add_node("VLV-204", tag="VLV-204", type="Valve", spec='4"-CS-150#', attributes={
        "type": "Gate Valve",
        "size": "DN100",
    })

    # Add instrument nodes
    G.add_node("TIC-203", tag="TIC-203", type="Instrument", spec="", attributes={
        "function": "Temperature Indicator Controller",
        "signal": "4-20mA",
    })

    # Add pipeline segments
    G.add_node("L-101A", tag="L-101A", type="Pipeline", spec='4"-CS-150#', attributes={})
    G.add_node("L-101B", tag="L-101B", type="Pipeline", spec='4"-CS-150#', attributes={})

    # Add connections (edges)
    G.add_edge("V-101", "VLV-201", spec='4"-CS-150#', flow="forward")
    G.add_edge("VLV-201", "P-101A", spec='4"-CS-150#', flow="forward")
    G.add_edge("V-101", "VLV-204", spec='4"-CS-150#', flow="forward")
    G.add_edge("VLV-204", "P-101B", spec='4"-CS-150#', flow="forward")
    G.add_edge("P-101A", "L-101A", spec='4"-CS-150#', flow="forward")
    G.add_edge("P-101B", "L-101B", spec='4"-CS-150#', flow="forward")

    # Export to DEXPI
    output_path = "exports/simple_pid_export.xml"
    result = export_graph_to_dexpi_xml(G, output_path)

    print_export_result(result)
    return result


# =============================================================================
# Test Case 2: Heat Exchanger with Instruments
# =============================================================================

def test_heat_exchanger_export():
    """
    Test Case: Export a heat exchanger with associated instruments.
    Expected: Valid DEXPI XML with shell-and-tube heat exchanger.
    """
    print("\n" + "=" * 70)
    print("TEST 2: Heat Exchanger with Instruments")
    print("=" * 70)

    G = nx.DiGraph()

    # Heat exchanger train
    G.add_node("E-101", tag="E-101", type="HeatExchanger", spec='6"-CS-300#', attributes={
        "type": "Shell and Tube",
        "area": "150 m²",
    })

    G.add_node("P-201", tag="P-201", type="Pump", spec='3"-CS-150#', attributes={
        "drive": "Electric Motor",
    })

    # Instruments
    G.add_node("FIC-101", tag="FIC-101", type="Instrument", attributes={
        "function": "Flow Indicator Controller",
    })

    G.add_node("TIC-101", tag="TIC-101", type="Instrument", attributes={
        "function": "Temperature Indicator Controller",
    })

    G.add_node("PIC-101", tag="PIC-101", type="Instrument", attributes={
        "function": "Pressure Indicator Controller",
    })

    # Control valve
    G.add_node("FCV-101", tag="FCV-101", type="ControlValve", attributes={
        "function": "Flow Control Valve",
    })

    # Connections
    G.add_edge("P-201", "E-101", spec='3"-CS-150#')
    G.add_edge("E-101", "FCV-101", spec='4"-CS-150#')
    G.add_edge("FCV-101", "TIC-101", spec='4"-CS-150#')

    # Export
    output_path = "exports/heat_exchanger_export.xml"
    options = DEXPIExportOptions(
        project_name="Heat Exchanger Unit HE-101",
        author="CHAT-PID-AI Test Suite",
    )

    result = export_graph_to_dexpi_xml(G, output_path, options)

    print_export_result(result)
    return result


# =============================================================================
# Test Case 3: Distillation Column with Safety Valves
# =============================================================================

def test_distillation_column_export():
    """
    Test Case: Export a distillation column with PSV and safety equipment.
    Expected: Valid DEXPI XML with process column and safety valves.
    """
    print("\n" + "=" * 70)
    print("TEST 3: Distillation Column with Safety Valves")
    print("=" * 70)

    G = nx.DiGraph()

    # Column
    G.add_node("C-101", tag="C-101", type="Column", spec='4"-CS-300#', attributes={
        "type": "Distillation Column",
        "trays": 30,
    })

    # Reboiler and Condenser
    G.add_node("E-102", tag="E-102", type="HeatExchanger", attributes={
        "type": "Shell and Tube (Reboiler)",
    })

    G.add_node("E-103", tag="E-103", type="HeatExchanger", attributes={
        "type": "Shell and Tube (Condenser)",
    })

    # Pumps
    G.add_node("P-102A", tag="P-102A", type="Pump", attributes={"drive": "Electric Motor"})
    G.add_node("P-102B", tag="P-102B", type="Pump", attributes={"drive": "Electric Motor"})

    # Safety valves
    G.add_node("PSV-101", tag="PSV-101", type="SafetyValve", attributes={
        "set_pressure": "10 bar",
        "capacity": "5000 kg/h",
    })

    G.add_node("PSV-102", tag="PSV-102", type="SafetyValve", attributes={
        "set_pressure": "5 bar",
        "capacity": "3000 kg/h",
    })

    # Level control valve
    G.add_node("LCV-101", tag="LCV-101", type="ControlValve", attributes={})

    # Connections
    G.add_edge("E-102", "C-101", spec='4"-CS-300#')
    G.add_edge("C-101", "E-103", spec='4"-CS-300#')
    G.add_edge("E-103", "P-102A", spec='2"-CS-150#')
    G.add_edge("P-102A", "E-102", spec='2"-CS-150#')
    G.add_edge("C-101", "P-102B", spec='2"-CS-150#')
    G.add_edge("P-102B", "LCV-101", spec='2"-CS-150#')

    # Safety connections
    G.add_edge("C-101", "PSV-101", spec='2"-CS-300#')
    G.add_edge("E-102", "PSV-102", spec='2"-CS-150#')

    # Export
    output_path = "exports/distillation_column_export.xml"
    result = export_graph_to_dexpi_xml(G, output_path)

    print_export_result(result)
    return result


# =============================================================================
# Test Case 4: DEXPI Export Engine Direct Usage
# =============================================================================

def test_dexpi_export_engine():
    """
    Test Case: Use DEXPIExportEngine class directly for more control.
    Expected: Demonstrates advanced usage with custom options.
    """
    print("\n" + "=" * 70)
    print("TEST 4: DEXPI Export Engine Direct Usage")
    print("=" * 70)

    # Create engine with custom options
    options = DEXPIExportOptions(
        project_name="Custom PID Project",
        author="Process Engineering Team",
        organization="Acme Chemical Corp",
        version="2.0",
        strict_mapping=False,  # Allow unrecognized types
        pretty_print=True,
    )

    engine = DEXPIExportEngine(options=options)

    # Create a simple graph programmatically
    G = nx.DiGraph()
    G.add_node("node1", tag="TEST-001", type="Vessel", spec='12"-SS-600#')
    G.add_node("node2", tag="TEST-002", type="CustomPump", spec='6"-SS-300#')

    # Export with engine
    output_path = "exports/custom_engine_export.xml"
    result = engine.export_graph_to_dexpi_xml(G, output_path)

    print_export_result(result)

    # Show statistics
    stats = engine.get_export_statistics()
    print("\nExport Statistics:")
    print(f"  Nodes registered: {stats['nodes_registered']}")
    print(f"  Connections: {stats['connections_recorded']}")
    print(f"  Object types: {json.dumps(stats['object_types'], indent=4)}")

    return result


# =============================================================================
# Utility Functions
# =============================================================================

def print_export_result(result: DEXPIExportResult):
    """Print formatted export result to console."""
    print(f"\n{'─' * 70}")
    print(f"DEXPI Export Result")
    print(f"{'─' * 70}")
    print(f"  Success:         {result.success}")
    print(f"  Output Path:     {result.output_path or 'N/A'}")
    print(f"  Nodes Exported:  {result.nodes_exported}")
    print(f"  Edges Exported:  {result.edges_exported}")

    if result.warnings:
        print(f"\n  Warnings ({len(result.warnings)}):")
        for warning in result.warnings[:5]:
            print(f"    ⚠️  {warning[:80]}...")
        if len(result.warnings) > 5:
            print(f"    ... and {len(result.warnings) - 5} more")

    if result.error_message:
        print(f"\n  ❌ Error: {result.error_message}")

    if result.success and result.exported_objects:
        print(f"\n  Exported Objects:")
        for node_id, obj_type in list(result.exported_objects.items())[:10]:
            print(f"    • {node_id} → {obj_type}")
        if len(result.exported_objects) > 10:
            print(f"    ... and {len(result.exported_objects) - 10} more")

    print(f"{'─' * 70}")


def print_status():
    """Print pyDEXPI library status."""
    print("\n" + "=" * 70)
    print("pyDEXPI Library Status Check")
    print("=" * 70)
    print(f"  Library Available: {PYDEXPI_AVAILABLE}")

    if not PYDEXPI_AVAILABLE:
        print("\n  ⚠️  pyDEXPI not installed.")
        print("  To install:")
        print("    pip install pydexpi")
        print("\n  Note: pyDEXPI requires Python >= 3.12")
        print(f"  Current Python version: {__import__('sys').version_info.major}.{__import__('sys').version_info.minor}")
    else:
        print("\n  ✅ pyDEXPI is available for DEXPI export!")

    print("=" * 70)


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Run all test cases."""
    print_status()

    if not PYDEXPI_AVAILABLE:
        print("\n⚠️  pyDEXPI not available. Skipping DEXPI export tests.")
        print("   Install pyDEXPI to run these tests:")
        print("   pip install pydexpi")
        return

    # Create output directory
    Path("exports").mkdir(exist_ok=True)

    # Run all test cases
    results = []

    try:
        results.append(("Simple P&ID", test_simple_pid_export()))
    except Exception as e:
        print(f"Test 1 failed: {e}")

    try:
        results.append(("Heat Exchanger", test_heat_exchanger_export()))
    except Exception as e:
        print(f"Test 2 failed: {e}")

    try:
        results.append(("Distillation Column", test_distillation_column_export()))
    except Exception as e:
        print(f"Test 3 failed: {e}")

    try:
        results.append(("Export Engine Direct", test_dexpi_export_engine()))
    except Exception as e:
        print(f"Test 4 failed: {e}")

    # Summary
    print("\n" + "=" * 70)
    print("TEST EXECUTION SUMMARY")
    print("=" * 70)

    success_count = sum(1 for _, r in results if r.success)
    total_count = len(results)

    for name, result in results:
        status = "✅ SUCCESS" if result.success else "❌ FAILED"
        print(f"  {status} | {name}")

    print(f"\n  TOTAL: {success_count}/{total_count} exports successful")
    print("=" * 70)


if __name__ == "__main__":
    main()
