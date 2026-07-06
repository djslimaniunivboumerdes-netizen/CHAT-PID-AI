"""
CHAT-PID-AI: Thermodynamic Safety Audit Examples
================================================

This module provides examples and test cases for the ThermodynamicSafetyAuditor
class and the new FastAPI endpoints.

Run this script standalone to test NeqSim integration:
    python examples/thermodynamic_audit_example.py

Or use the FastAPI endpoints at:
    POST /api/audit/thermodynamic/single
    POST /api/audit/thermodynamic/batch
    GET  /api/audit/thermodynamic/pipeline/{doc_id}

Author: CHAT-PID-AI Development Team
"""

import json
import networkx as nx
from dataclasses import asdict

# Import the auditor
from rules_engine import ThermodynamicSafetyAuditor, thermodynamic_auditor


# =============================================================================
# Test Case 1: Single Pipe Audit - Normal Operating Conditions
# =============================================================================

def test_single_pipe_normal():
    """
    Test Case: Normal single-phase gas flow conditions.
    Expected: No critical findings, ANSI check passes.
    """
    print("\n" + "=" * 70)
    print("TEST 1: Single Pipe Audit - Normal Gas Flow (25 bar, 80°C)")
    print("=" * 70)

    pipe_data = {
        "id": "pipe-001",
        "tag_number": "PIPE-101",
        "line_spec": '6"-CS-300#',
        "attributes": {"material": "Carbon Steel", "insulation": "none"},
    }

    report = thermodynamic_auditor.audit_pipe_node(
        pipe_node_data=pipe_data,
        operating_pressure_bar=25.0,
        operating_temperature_c=80.0,
    )

    print_audit_report(report)
    return report


# =============================================================================
# Test Case 2: Multiphase Dropout - CRITICAL Condition
# =============================================================================

def test_multiphase_dropout_critical():
    """
    Test Case: Two-phase flow conditions causing liquid dropout.
    Expected: CRITICAL finding for multiphase dropout risk.
    """
    print("\n" + "=" * 70)
    print("TEST 2: Multiphase Dropout - CRITICAL (30 bar, 50°C)")
    print("=" * 70)

    # Natural gas mix that will exhibit two-phase behavior at these conditions
    composition = {
        "methane": 0.60,
        "ethane": 0.20,
        "propane": 0.10,
        "n-butane": 0.05,
        "i-butane": 0.03,
        "n-pentane": 0.02,
    }

    pipe_data = {
        "id": "pipe-002",
        "tag_number": "PIPE-202",
        "line_spec": '4"-CS-150#',
        "attributes": {"material": "Carbon Steel"},
    }

    report = thermodynamic_auditor.audit_pipe_node(
        pipe_node_data=pipe_data,
        operating_pressure_bar=30.0,
        operating_temperature_c=50.0,
        fluid_composition=composition,
    )

    print_audit_report(report)
    return report


# =============================================================================
# Test Case 3: ANSI Class Exceedance - WARNING
# =============================================================================

def test_ansi_class_exceedance():
    """
    Test Case: Operating pressure exceeds ANSI 150# rating.
    Expected: WARNING for ANSI class exceedance.
    """
    print("\n" + "=" * 70)
    print("TEST 3: ANSI Class Exceedance - WARNING (35 bar, 100°C)")
    print("=" * 70)

    pipe_data = {
        "id": "pipe-003",
        "tag_number": "PIPE-303",
        "line_spec": '4"-CS-150#',  # Max pressure: ~19.6 bara
        "attributes": {"material": "Carbon Steel"},
    }

    report = thermodynamic_auditor.audit_pipe_node(
        pipe_node_data=pipe_data,
        operating_pressure_bar=35.0,  # EXCEEDS 150# limit
        operating_temperature_c=100.0,
    )

    print_audit_report(report)
    return report


# =============================================================================
# Test Case 4: High Pressure Gas - Supercritical
# =============================================================================

def test_high_pressure_gas():
    """
    Test Case: High pressure gas above critical pressure.
    Expected: Single-phase supercritical fluid, no dropout risk.
    """
    print("\n" + "=" * 70)
    print("TEST 4: High Pressure Gas - Supercritical (100 bar, 50°C)")
    print("=" * 70)

    pipe_data = {
        "id": "pipe-004",
        "tag_number": "PIPE-404",
        "line_spec": '8"-SS-600#',
        "attributes": {"material": "Stainless Steel 316"},
    }

    report = thermodynamic_auditor.audit_pipe_node(
        pipe_node_data=pipe_data,
        operating_pressure_bar=100.0,
        operating_temperature_c=50.0,
    )

    print_audit_report(report)
    return report


# =============================================================================
# Test Case 5: Batch Pipeline Audit
# =============================================================================

def test_batch_pipeline_audit():
    """
    Test Case: Audit multiple pipe segments in a pipeline graph.
    Expected: Multiple reports with various findings.
    """
    print("\n" + "=" * 70)
    print("TEST 5: Batch Pipeline Audit - Multiple Segments")
    print("=" * 70)

    # Create a sample P&ID connectivity graph
    G = nx.DiGraph()

    # Add nodes with P&ID-like attributes
    G.add_node("V-101", tag="V-101", type="Vessel", spec='6"-CS-300#', attributes={})
    G.add_node("VLV-201", tag="VLV-201", type="Valve", spec='4"-CS-150#', attributes={"size": "4-inch"})
    G.add_node("P-101A", tag="P-101A", type="Pump", spec='4"-CS-150#', attributes={})
    G.add_node("PIPE-101", tag="PIPE-101", type="Pipeline", spec='4"-CS-150#', attributes={})
    G.add_node("PIPE-102", tag="PIPE-102", type="Pipeline", spec='2"-CS-150#', attributes={})
    G.add_node("PIPE-103", tag="PIPE-103", type="Pipeline", spec='6"-CS-150#', attributes={})
    G.add_node("E-101", tag="E-101", type="Heat Exchanger", spec='6"-CS-300#', attributes={})

    # Add edges with flow connections
    G.add_edge("V-101", "VLV-201", spec='4"-CS-150#', flow="forward")
    G.add_edge("VLV-201", "P-101A", spec='4"-CS-150#', flow="forward")
    G.add_edge("V-101", "PIPE-101", spec='4"-CS-150#', flow="forward")
    G.add_edge("P-101A", "PIPE-102", spec='2"-CS-150#', flow="forward")
    G.add_edge("PIPE-102", "E-101", spec='2"-CS-300#', flow="forward")
    G.add_edge("E-101", "PIPE-103", spec='6"-CS-150#', flow="forward")

    # Custom fluid composition (gas condensate)
    composition = {
        "methane": 0.72,
        "ethane": 0.08,
        "propane": 0.05,
        "i-butane": 0.02,
        "n-butane": 0.03,
        "i-pentane": 0.01,
        "n-pentane": 0.01,
        "n-hexane": 0.01,
        "CO2": 0.03,
        "nitrogen": 0.02,
        "water": 0.02,
    }

    # Run batch audit
    reports = thermodynamic_auditor.batch_audit_pipeline(
        graph=G,
        operating_pressure_bar=45.0,  # High enough to potentially cause issues
        operating_temperature_c=60.0,
        fluid_composition=composition,
    )

    print(f"\nBatch audit completed: {len(reports)} segments audited")
    print("-" * 70)

    critical_total = 0
    warning_total = 0

    for i, report in enumerate(reports, 1):
        print(f"\n[Segment {i}] {report.pipe_node_id} | Spec: {report.line_spec}")
        print(f"  Pressure: {report.operating_pressure_bar:.1f} bar | Temp: {report.operating_temperature_c:.1f}°C")

        if report.thermodynamic_state:
            beta = report.thermodynamic_state.get("vapor_fraction_beta")
            if beta is not None:
                print(f"  Vapor Fraction (β): {beta:.4f} | Phase: {report.thermodynamic_state.get('phase_status', 'unknown')}")

        for finding in report.findings:
            severity_icon = "🔴" if finding.severity.value == "Critical" else "🟡" if finding.severity.value == "Warning" else "🔵"
            print(f"  {severity_icon} [{finding.severity.value}] {finding.title}")
            if finding.severity.value == "Critical":
                critical_total += 1
            elif finding.severity.value == "Warning":
                warning_total += 1

    print("\n" + "-" * 70)
    print(f"Batch Summary: {critical_total} CRITICAL, {warning_total} WARNING")
    print("-" * 70)

    return reports


# =============================================================================
# Test Case 6: Chemical Plant Feedstock (Heavy Hydrocarbons)
# =============================================================================

def test_heavy_hydrocarbon_feed():
    """
    Test Case: Heavy hydrocarbon feedstock prone to liquid dropout.
    Expected: Multiple critical findings for near-saturation conditions.
    """
    print("\n" + "=" * 70)
    print("TEST 6: Heavy Hydrocarbon Feed - Near-Saturation (15 bar, 120°C)")
    print("=" * 70)

    # Heavy naphtha/condensate composition
    composition = {
        "methane": 0.30,
        "ethane": 0.15,
        "propane": 0.15,
        "n-butane": 0.12,
        "i-butane": 0.08,
        "n-pentane": 0.07,
        "i-pentane": 0.06,
        "n-hexane": 0.04,
        "n-heptane": 0.02,
        "n-octane": 0.01,
    }

    pipe_data = {
        "id": "pipe-006",
        "tag_number": "FEED-501",
        "line_spec": '3"-CS-300#',
        "attributes": {"service": "Naphtha Feed", "material": "Carbon Steel"},
    }

    report = thermodynamic_auditor.audit_pipe_node(
        pipe_node_data=pipe_data,
        operating_pressure_bar=15.0,
        operating_temperature_c=120.0,
        fluid_composition=composition,
    )

    print_audit_report(report)
    return report


# =============================================================================
# Utility Functions
# =============================================================================

def print_audit_report(report):
    """Print a formatted audit report to console."""
    print(f"\n{'─' * 70}")
    print(f"AUDIT REPORT: {report.audit_id[:8]}")
    print(f"{'─' * 70}")
    print(f"  Pipe Node ID:    {report.pipe_node_id}")
    print(f"  Line Spec:       {report.line_spec}")
    print(f"  Operating P:     {report.operating_pressure_bar:.2f} bar")
    print(f"  Operating T:     {report.operating_temperature_c:.2f} °C")
    print(f"  Calculation:     {report.calculation_status}")

    if report.thermodynamic_state:
        print(f"\n  Thermodynamic State:")
        ts = report.thermodynamic_state
        print(f"    - Phase Status:        {ts.get('phase_status', 'N/A')}")
        beta = ts.get('vapor_fraction_beta')
        if beta is not None:
            print(f"    - Vapor Fraction (β):  {beta:.6f}")
        print(f"    - EOS Model:           {ts.get('eos_model', 'N/A')}")
        if ts.get('gas_density_kg_m3'):
            print(f"    - Gas Density:         {ts['gas_density_kg_m3']:.3f} kg/m³")
        if ts.get('liquid_density_kg_m3'):
            print(f"    - Liquid Density:      {ts['liquid_density_kg_m3']:.3f} kg/m³")

    if report.findings:
        print(f"\n  Safety Findings ({len(report.findings)}):")
        for i, finding in enumerate(report.findings, 1):
            severity_icon = {
                "Critical": "🔴",
                "Warning": "🟡",
                "Info": "🔵",
                "Safety Flag": "🟠",
            }.get(finding.severity.value, "⚪")

            print(f"\n    [{i}] {severity_icon} {finding.severity.value}: {finding.title}")
            print(f"        Category: {finding.category.value}")
            print(f"        {finding.description[:100]}...")

            if finding.severity.value == "Critical":
                print(f"        ⚠️  RECOMMENDATION:")
                for line in finding.recommendation.strip().split('\n')[:3]:
                    print(f"           {line}")

    if report.error_message:
        print(f"\n  ⚠️  Error: {report.error_message}")

    print(f"\n{'─' * 70}")


def print_neqsim_status():
    """Print NeqSim library availability status."""
    print("\n" + "=" * 70)
    print("NeqSim Library Status Check")
    print("=" * 70)
    print(f"  Library Available: {thermodynamic_auditor.neqsim_available}")

    if thermodynamic_auditor.neqsim_available:
        print("\n  Default Fluid Composition (Natural Gas):")
        for component, fraction in thermodynamic_auditor.DEFAULT_COMPOSITION.items():
            print(f"    - {component.capitalize():12s}: {fraction:.3f} mole fraction")

        print("\n  ANSI Class Pressure Limits (bara):")
        for ansi_class, limit in thermodynamic_auditor.ANSI_CLASS_LIMITS.items():
            print(f"    - ANSI {ansi_class:6s}: {limit:.1f} bar")
    else:
        print("\n  To install NeqSim:")
        print("    pip install neqsim")
        print("\n  Note: NeqSim requires Java Runtime Environment (JRE) 8+")
    print("=" * 70)


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Run all test cases."""
    print_neqsim_status()

    if not thermodynamic_auditor.neqsim_available:
        print("\n⚠️  NeqSim not available. Install with: pip install neqsim")
        print("   Running limited tests only...\n")

    # Run all test cases
    results = []

    try:
        results.append(("Normal Gas Flow", test_single_pipe_normal()))
    except Exception as e:
        print(f"Test 1 failed: {e}")

    try:
        results.append(("Multiphase Dropout", test_multiphase_dropout_critical()))
    except Exception as e:
        print(f"Test 2 failed: {e}")

    try:
        results.append(("ANSI Exceedance", test_ansi_class_exceedance()))
    except Exception as e:
        print(f"Test 3 failed: {e}")

    try:
        results.append(("High Pressure", test_high_pressure_gas()))
    except Exception as e:
        print(f"Test 4 failed: {e}")

    try:
        results.append(("Batch Pipeline", test_batch_pipeline_audit()))
    except Exception as e:
        print(f"Test 5 failed: {e}")

    try:
        results.append(("Heavy Hydrocarbon", test_heavy_hydrocarbon_feed()))
    except Exception as e:
        print(f"Test 6 failed: {e}")

    # Summary
    print("\n" + "=" * 70)
    print("TEST EXECUTION SUMMARY")
    print("=" * 70)

    critical_total = 0
    warning_total = 0

    for name, report in results:
        if report:
            critical = sum(1 for f in report.findings if f.severity.value == "Critical")
            warning = sum(1 for f in report.findings if f.severity.value == "Warning")
            critical_total += critical
            warning_total += warning
            status = "✓ PASS" if not critical else "⚠️ CRITICAL"
            print(f"  {status} | {name}: {critical} critical, {warning} warnings")

    print(f"\n  TOTAL: {critical_total} CRITICAL findings, {warning_total} WARNING findings")
    print("=" * 70)


if __name__ == "__main__":
    main()
