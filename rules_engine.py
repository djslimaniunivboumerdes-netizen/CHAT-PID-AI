"""
CHAT-PID-AI: Advanced Rules Engine with Thermodynamic Safety Auditing
======================================================================
This module extends the PID rules engine with physics-aware safety audits
using the NeqSim thermodynamic library for equation-of-state calculations.

Author: CHAT-PID-AI Development Team
License: Apache 2.0
"""

import uuid
import re
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime

import requests
import networkx as nx
from sqlalchemy.orm import Session

from models import Document, Entity, Connection, HazopSuggestion, InspectorAudit
from config import settings

# Configure module logger
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


# =============================================================================
# Data Classes for Thermodynamic Audit Reports
# =============================================================================

class SeverityLevel(str, Enum):
    """Enumeration of severity levels for audit findings."""
    INFO = "Info"
    WARNING = "Warning"
    CRITICAL = "Critical"
    SAFETY_FLAG = "Safety Flag"


class AuditCategory(str, Enum):
    """Categories of thermodynamic safety audits."""
    MULTIPHASE_DROPOUT = "Multiphase Dropout Risk"
    ANSI_CLASS_EXCEEDED = "ANSI Class Rating Exceeded"
    THERMODYNAMIC_CALCULATION = "Thermodynamic Calculation"
    COMPOSITION_UNCERTAINTY = "Composition Uncertainty"


@dataclass
class ThermodynamicFinding:
    """Represents a single safety finding from thermodynamic analysis."""
    severity: SeverityLevel
    category: AuditCategory
    title: str
    description: str
    recommendation: str
    technical_details: Dict[str, Any] = field(default_factory=dict)
    detected_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ThermodynamicAuditReport:
    """Complete thermodynamic safety audit report for a pipeline segment."""
    audit_id: str
    pipe_node_id: str
    line_spec: str
    operating_pressure_bar: float
    operating_temperature_c: float
    findings: List[ThermodynamicFinding] = field(default_factory=list)
    fluid_composition: Dict[str, float] = field(default_factory=dict)
    thermodynamic_state: Dict[str, Any] = field(default_factory=dict)
    audit_timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    calculation_status: str = "completed"
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary for JSON serialization."""
        return {
            "audit_id": self.audit_id,
            "pipe_node_id": self.pipe_node_id,
            "line_spec": self.line_spec,
            "operating_pressure_bar": self.operating_pressure_bar,
            "operating_temperature_c": self.operating_temperature_c,
            "findings": [
                {
                    "severity": f.severity.value,
                    "category": f.category.value,
                    "title": f.title,
                    "description": f.description,
                    "recommendation": f.recommendation,
                    "technical_details": f.technical_details,
                    "detected_at": f.detected_at,
                }
                for f in self.findings
            ],
            "fluid_composition": self.fluid_composition,
            "thermodynamic_state": self.thermodynamic_state,
            "audit_timestamp": self.audit_timestamp,
            "calculation_status": self.calculation_status,
            "error_message": self.error_message,
        }

    @property
    def has_critical_findings(self) -> bool:
        """Check if any findings are marked as CRITICAL."""
        return any(f.severity == SeverityLevel.CRITICAL for f in self.findings)

    @property
    def has_warnings(self) -> bool:
        """Check if any findings are marked as WARNING."""
        return any(f.severity == SeverityLevel.WARNING for f in self.findings)


# =============================================================================
# Thermodynamic Safety Auditor Class
# =============================================================================

class ThermodynamicSafetyAuditor:
    """
    Physics-aware safety auditor for P&ID pipeline segments using NeqSim.

    This class performs thermodynamic calculations to detect:
    - Multiphase dropout conditions (liquid slugging, water hammer risks)
    - ANSI class rating exceedances in piping specifications
    - Phase envelope boundary proximity

    Attributes:
        DEFAULT_COMPOSITION: Default hydrocarbon mixture composition (mole fractions).
        ANSI_CLASS_LIMITS: Maximum allowable pressures (bara) per ANSI class rating.
        VAPOR_FRACTION_CRITICAL_BAND: Range where multiphase dropout is dangerous.
    """

    # Default fluid composition: Methane/Ethane/Propane natural gas mix
    DEFAULT_COMPOSITION: Dict[str, float] = {
        "methane": 0.85,
        "ethane": 0.08,
        "propane": 0.05,
        "n-butane": 0.015,
        "i-butane": 0.005,
        "n-pentane": 0.002,
        "i-pentane": 0.002,
        "nitrogen": 0.001,
        "CO2": 0.001,
    }

    # ANSI Class pressure limits (bara) per ANSI/ASME B16.5
    # These are approximate maximum working pressures at 38°C for carbon steel
    ANSI_CLASS_LIMITS: Dict[str, float] = {
        "150#": 19.6,   # Class 150: ~19.6 bara (285 psig)
        "300#": 51.1,   # Class 300: ~51.1 bara (740 psig)
        "400#": 68.5,   # Class 400: ~68.5 bara (990 psig)
        "600#": 102.7,  # Class 600: ~102.7 bara (1485 psig)
        "900#": 154.5,  # Class 900: ~154.5 bara (2225 psig)
        "1500#": 256.9, # Class 1500: ~256.9 bara (3705 psig)
        "2500#": 422.0, # Class 2500: ~422.0 bara (6080 psig)
    }

    # Critical multiphase dropout detection band
    # If 0.0 < beta < 0.95, significant liquid dropout can occur
    VAPOR_FRACTION_CRITICAL_MIN: float = 0.0
    VAPOR_FRACTION_CRITICAL_MAX: float = 0.95

    # Warning threshold: approaching phase boundary
    VAPOR_FRACTION_WARNING_MIN: float = 0.05
    VAPOR_FRACTION_WARNING_MAX: float = 0.98

    def __init__(self, use_neqsim: bool = True):
        """
        Initialize the thermodynamic safety auditor.

        Args:
            use_neqsim: Whether to attempt NeqSim calculations.
                       Set to False for fallback-only mode.
        """
        self.use_neqsim = use_neqsim
        self._neqsim_available = None
        self._neqsim = None

    @property
    def neqsim_available(self) -> bool:
        """Check if NeqSim is available and working."""
        if self._neqsim_available is not None:
            return self._neqsim_available

        if not self.use_neqsim:
            self._neqsim_available = False
            return False

        try:
            from neqsim.thermo import fluid, TPflash
            self._neqsim = {"fluid": fluid, "TPflash": TPflash}
            self._neqsim_available = True
            logger.info("NeqSim library successfully initialized for thermodynamic calculations")
        except ImportError as e:
            logger.warning(f"NeqSim not available: {e}. Thermodynamic calculations disabled.")
            self._neqsim_available = False
        except Exception as e:
            logger.error(f"NeqSim initialization failed: {e}")
            self._neqsim_available = False

        return self._neqsim_available

    def _parse_line_spec(self, line_spec: str) -> Dict[str, Any]:
        """
        Parse pipe line specification string.

        Expected format: "{size}\"-{material}-{rating}#" or similar patterns.
        Examples: '4"-CS-150#', '6"-SS-300#', '2"-CS-600#'

        Args:
            line_spec: The line specification string from P&ID.

        Returns:
            Dictionary containing parsed components.
        """
        result = {
            "original_spec": line_spec,
            "size_inches": None,
            "material": None,
            "ansi_class": None,
            "parse_success": False,
        }

        if not line_spec:
            return result

        # Pattern to match line specs like: 4"-CS-150#, 6"-SS-300#, etc.
        pattern = r'(\d+(?:\.\d+)?)"?-([A-Za-z]+)-(\d+)#?'
        match = re.search(pattern, line_spec, re.IGNORECASE)

        if match:
            result["size_inches"] = float(match.group(1))
            result["material"] = match.group(2).upper()
            result["ansi_class"] = f"{match.group(3)}#"
            result["parse_success"] = True
            logger.debug(f"Parsed line spec '{line_spec}' -> {result}")
        else:
            # Try simpler pattern: just extract size and ANSI class
            size_match = re.search(r'(\d+(?:\.\d+)?)', line_spec)
            class_match = re.search(r'(\d+)#', line_spec, re.IGNORECASE)

            if size_match:
                result["size_inches"] = float(size_match.group(1))
            if class_match:
                result["ansi_class"] = f"{class_match.group(1)}#"

            result["parse_success"] = size_match is not None or class_match is not None
            logger.debug(f"Partial parse of '{line_spec}' -> {result}")

        return result

    def _check_ansi_class_exceedance(
        self, line_spec: str, operating_pressure_bar: float
    ) -> Optional[ThermodynamicFinding]:
        """
        Check if operating pressure exceeds ANSI class rating for the pipe spec.

        Args:
            line_spec: The parsed line specification (e.g., "4\"-CS-150#").
            operating_pressure_bar: Operating pressure in bara.

        Returns:
            ThermodynamicFinding if pressure exceeds rating, None otherwise.
        """
        parsed = self._parse_line_spec(line_spec)
        ansi_class = parsed.get("ansi_class")

        if not ansi_class or ansi_class not in self.ANSI_CLASS_LIMITS:
            return None

        max_pressure = self.ANSI_CLASS_LIMITS[ansi_class]
        pressure_ratio = operating_pressure_bar / max_pressure

        if operating_pressure_bar > max_pressure:
            return ThermodynamicFinding(
                severity=SeverityLevel.WARNING,
                category=AuditCategory.ANSI_CLASS_EXCEEDED,
                title="ANSI Class Pressure Rating Exceeded",
                description=(
                    f"Operating pressure ({operating_pressure_bar:.1f} bar) EXCEEDS the "
                    f"ANSI Class {ansi_class} maximum allowable pressure ({max_pressure:.1f} bar). "
                    f"Pressure ratio: {pressure_ratio:.2f}x rated capacity."
                ),
                recommendation=(
                    f"IMMEDIATE ACTION REQUIRED: Replace pipe/spec with ANSI Class "
                    f"{self._get_next_ansi_class(ansi_class)} or higher rating. "
                    f"Current operation violates ASME B31.3 pressure design requirements. "
                    f"Consider conducting a Fitness-For-Service (FFS) assessment."
                ),
                technical_details={
                    "line_spec": line_spec,
                    "ansi_class": ansi_class,
                    "max_allowable_pressure_bar": max_pressure,
                    "operating_pressure_bar": operating_pressure_bar,
                    "exceedance_ratio": round(pressure_ratio, 3),
                    "applicable_code": "ASME B31.3 / ANSI B16.5",
                },
            )
        elif pressure_ratio > 0.85:
            # Warning when approaching limit
            return ThermodynamicFinding(
                severity=SeverityLevel.INFO,
                category=AuditCategory.ANSI_CLASS_EXCEEDED,
                title="Approaching ANSI Class Pressure Limit",
                description=(
                    f"Operating pressure ({operating_pressure_bar:.1f} bar) is within "
                    f"85% of ANSI Class {ansi_class} limit ({max_pressure:.1f} bar). "
                    f"Pressure ratio: {pressure_ratio:.1%} of rated capacity."
                ),
                recommendation=(
                    f"Schedule engineering review for potential uprating or pressure reduction. "
                    f"Ensure pressure relief devices are sized appropriately."
                ),
                technical_details={
                    "line_spec": line_spec,
                    "ansi_class": ansi_class,
                    "max_allowable_pressure_bar": max_pressure,
                    "operating_pressure_bar": operating_pressure_bar,
                    "utilization_ratio": round(pressure_ratio, 3),
                },
            )

        return None

    def _get_next_ansi_class(self, current_class: str) -> str:
        """Get the next higher ANSI class rating."""
        class_order = ["150#", "300#", "400#", "600#", "900#", "1500#", "2500#"]
        try:
            current_idx = class_order.index(current_class)
            if current_idx < len(class_order) - 1:
                return class_order[current_idx + 1]
        except ValueError:
            pass
        return "300#"  # Default fallback

    def _run_neqsim_calculation(
        self,
        temperature_c: float,
        pressure_bar: float,
        composition: Optional[Dict[str, float]] = None,
    ) -> Tuple[Optional[float], Optional[Dict[str, Any]], Optional[str]]:
        """
        Execute NeqSim TPflash calculation for vapor-liquid equilibrium.

        Args:
            temperature_c: Operating temperature in Celsius.
            pressure_bar: Operating pressure in bara.
            composition: Optional fluid composition override.

        Returns:
            Tuple of (vapor_fraction_beta, thermodynamic_properties, error_message).
        """
        if not self.neqsim_available:
            return None, None, "NeqSim library not available"

        try:
            fluid_func = self._neqsim["fluid"]
            TPflash_func = self._neqsim["TPflash"]

            # Create SRK fluid system
            # NeqSim uses Kelvin and bara internally
            temp_K = temperature_c + 273.15
            pres_bar = pressure_bar

            fluid_system = fluid_func("srk")
            fluid_system.setTemperature(temp_K)
            fluid_system.setPressure(pres_bar)

            # Add components with mole fractions
            comp = composition or self.DEFAULT_COMPOSITION
            total_mole = sum(comp.values())

            for component, mole_fraction in comp.items():
                # Normalize to ensure mass balance
                normalized_mole = mole_fraction / total_mole
                fluid_system.addComponent(component, normalized_mole)

            fluid_system.setMixingRule("classic")

            # Perform TP flash calculation
            TPflash_func(fluid_system)

            # Initialize thermodynamic properties
            fluid_system.initProperties()

            # Extract vapor fraction (beta) - fraction of moles in vapor phase
            beta = fluid_system.getBeta()

            # Build comprehensive thermodynamic state dictionary
            thermo_state = {
                "vapor_fraction_beta": float(beta) if beta is not None else None,
                "phase_status": self._interpret_phase_status(beta),
                "temperature_K": float(temp_K),
                "temperature_C": float(temperature_c),
                "pressure_bar": float(pres_bar),
                "pressure_psi": float(pres_bar * 14.5038),
                "eos_model": "Soave-Redlich-Kwong (SRK)",
            }

            # Try to get phase-specific properties if multiphase
            if beta is not None and 0.0 < beta < 1.0:
                try:
                    gas_phase = fluid_system.getPhase("gas")
                    liquid_phase = fluid_system.getPhase("oil")  # NeqSim uses 'oil' for liquid

                    if gas_phase is not None:
                        thermo_state["gas_density_kg_m3"] = round(gas_phase.getDensity("kg/m3"), 3)
                        thermo_state["gas_enthalpy_J_mol"] = round(gas_phase.getEnthalpy("J/mol"), 2)

                    if liquid_phase is not None:
                        thermo_state["liquid_density_kg_m3"] = round(liquid_phase.getDensity("kg/m3"), 3)
                        thermo_state["liquid_enthalpy_J_mol"] = round(liquid_phase.getEnthalpy("J/mol"), 2)

                    # Calculate liquid dropout fraction
                    thermo_state["liquid_mole_fraction"] = round(1.0 - float(beta), 4)

                except Exception as phase_err:
                    logger.debug(f"Phase-specific property extraction failed: {phase_err}")

            # Overall system properties
            try:
                thermo_state["overall_density_kg_m3"] = round(fluid_system.getDensity("kg/m3"), 3)
                thermo_state["overall_enthalpy_J_mol"] = round(fluid_system.getEnthalpy("J/mol"), 2)
                thermo_state["overall_entropy_J_molK"] = round(fluid_system.getEntropy("J/molK"), 3)
            except Exception as prop_err:
                logger.debug(f"Overall property extraction failed: {prop_err}")

            return beta, thermo_state, None

        except Exception as e:
            error_msg = f"NeqSim calculation failed: {str(e)}"
            logger.error(error_msg)
            return None, None, error_msg

    def _interpret_phase_status(self, beta: Optional[float]) -> str:
        """Interpret the phase status based on vapor fraction."""
        if beta is None:
            return "unknown"
        elif beta >= 0.999:
            return "supercritical_vapor"
        elif beta <= 0.001:
            return "subcooled_liquid"
        elif 0.0 < beta < self.VAPOR_FRACTION_CRITICAL_MAX:
            return "two_phase_near_liquid"
        elif self.VAPOR_FRACTION_CRITICAL_MAX <= beta < 1.0:
            return "two_phase_near_vapor"
        else:
            return "supercritical"

    def _check_multiphase_dropout(
        self,
        vapor_fraction_beta: float,
        thermodynamic_state: Dict[str, Any],
    ) -> Optional[ThermodynamicFinding]:
        """
        Check for dangerous multiphase dropout conditions.

        CRITICAL if 0.0 < beta < 0.95: High risk of liquid slugging, water hammer,
       erosion-corrosion, and improper process performance.

        Args:
            vapor_fraction_beta: Vapor mole fraction from NeqSim TPflash.
            thermodynamic_state: Additional thermodynamic properties.

        Returns:
            ThermodynamicFinding if dangerous multiphase condition detected.
        """
        # Check for critical two-phase dropout
        if self.VAPOR_FRACTION_CRITICAL_MIN < vapor_fraction_beta < self.VAPOR_FRACTION_CRITICAL_MAX:
            liquid_fraction = 1.0 - vapor_fraction_beta
            liquid_pct = liquid_fraction * 100

            return ThermodynamicFinding(
                severity=SeverityLevel.CRITICAL,
                category=AuditCategory.MULTIPHASE_DROPOUT,
                title="CRITICAL: Multiphase Dropout Detected - Liquid Slugging Risk",
                description=(
                    f"THERMODYNAMIC HAZARD: Fluid is in a two-phase state with "
                    f"{liquid_pct:.1f}% liquid dropout (beta = {vapor_fraction_beta:.4f}). "
                    f"This represents a CRITICAL safety and operational risk. "
                    f"Under stratified or annular flow conditions, rapid liquid accumulation "
                    f"can cause destructive slugging forces, water hammer events, and severe "
                    f"equipment damage upon flow regime transitions."
                ),
                recommendation=(
                    "URGENT MITIGATION REQUIRED:\n"
                    "1. Install robust slug catchers or knock-out drums upstream\n"
                    "2. Implement pigging systems for liquids removal\n"
                    "3. Add liquid level instrumentation and automated dump valves\n"
                    "4. Redesign line routing to avoid low points where liquids accumulate\n"
                    "5. Consider process condition modification to achieve single-phase flow\n"
                    "6. Conduct detailed multiphase flow modeling (OLGA, LedaFlow)\n"
                    "7. Perform acoustic fatigue analysis on pipe supports"
                ),
                technical_details={
                    "vapor_fraction": round(vapor_fraction_beta, 6),
                    "liquid_fraction": round(liquid_fraction, 6),
                    "liquid_percentage": round(liquid_pct, 2),
                    "phase_status": thermodynamic_state.get("phase_status", "unknown"),
                    "liquid_density_kg_m3": thermodynamic_state.get("liquid_density_kg_m3"),
                    "gas_density_kg_m3": thermodynamic_state.get("gas_density_kg_m3"),
                    "density_ratio": (
                        thermodynamic_state.get("liquid_density_kg_m3", 0) /
                        max(thermodynamic_state.get("gas_density_kg_m3", 1), 0.001)
                        if thermodynamic_state.get("gas_density_kg_m3")
                        else None
                    ),
                    "hazard_mechanisms": [
                        "Liquid slugging",
                        "Water hammer",
                        "Erosion-corrosion",
                        "Process upset",
                        "Level control failure",
                        "Compressor cavitation",
                        "Pump cavitation",
                    ],
                },
            )

        # Warning for near-boundary conditions
        elif (
            self.VAPOR_FRACTION_WARNING_MIN <= vapor_fraction_beta <= self.VAPOR_FRACTION_WARNING_MAX
            and not (self.VAPOR_FRACTION_CRITICAL_MIN < vapor_fraction_beta < self.VAPOR_FRACTION_CRITICAL_MAX)
        ):
            return ThermodynamicFinding(
                severity=SeverityLevel.INFO,
                category=AuditCategory.MULTIPHASE_DROPOUT,
                title="Approaching Phase Boundary - Monitor Closely",
                description=(
                    f"Operating conditions are approaching the vapor-liquid "
                    f"phase boundary (beta = {vapor_fraction_beta:.4f}). "
                    f"Minor process disturbances could push the system into "
                    f"two-phase flow regime."
                ),
                recommendation=(
                    "1. Implement enhanced monitoring with densitometers\n"
                    "2. Review control system interlocks\n"
                    "3. Ensure adequate insulation and trace heating\n"
                    "4. Verify relief valve sizing accounts for potential two-phase flow"
                ),
                technical_details={
                    "vapor_fraction": round(vapor_fraction_beta, 6),
                    "proximity_to_boundary": "near_phase_envelope",
                    "monitoring_recommendation": "install_coriolis_densitometer",
                },
            )

        return None

    def audit_pipe_node(
        self,
        pipe_node_data: Dict[str, Any],
        operating_pressure_bar: float,
        operating_temperature_c: float,
        fluid_composition: Optional[Dict[str, float]] = None,
    ) -> ThermodynamicAuditReport:
        """
        Perform complete thermodynamic safety audit for a single pipe node.

        This method integrates:
        1. ANSI class rating exceedance check
        2. NeqSim TPflash calculation for phase behavior
        3. Multiphase dropout risk assessment

        Args:
            pipe_node_data: Dictionary containing pipe node information with keys:
                - 'id': Unique node identifier
                - 'tag_number': P&ID tag (e.g., "PIPE-101")
                - 'line_spec': Line specification (e.g., '4"-CS-150#')
                - 'attributes': Optional dict with additional metadata
            operating_pressure_bar: Operating pressure in bara.
            operating_temperature_c: Operating temperature in °C.
            fluid_composition: Optional fluid composition override.
                Defaults to methane-rich natural gas mixture.

        Returns:
            ThermodynamicAuditReport with all findings and thermodynamic state.
        """
        audit_id = str(uuid.uuid4())
        pipe_node_id = pipe_node_data.get("id", "unknown")
        line_spec = pipe_node_data.get("line_spec", pipe_node_data.get("attributes", {}).get("spec", ""))

        report = ThermodynamicAuditReport(
            audit_id=audit_id,
            pipe_node_id=pipe_node_id,
            line_spec=line_spec,
            operating_pressure_bar=operating_pressure_bar,
            operating_temperature_c=operating_temperature_c,
            fluid_composition=fluid_composition or self.DEFAULT_COMPOSITION,
        )

        logger.info(
            f"Auditing pipe {pipe_node_id} | Spec: {line_spec} | "
            f"P={operating_pressure_bar:.1f} bar | T={operating_temperature_c:.1f}°C"
        )

        # 1. Check ANSI class rating exceedance
        ansi_finding = self._check_ansi_class_exceedance(line_spec, operating_pressure_bar)
        if ansi_finding:
            report.findings.append(ansi_finding)
            logger.warning(
                f"ANSI class exceedance detected for {pipe_node_id}: "
                f"{ansi_finding.description[:100]}..."
            )

        # 2. Run NeqSim thermodynamic calculation
        composition = fluid_composition or self.DEFAULT_COMPOSITION

        vapor_beta, thermo_state, calc_error = self._run_neqsim_calculation(
            temperature_c=operating_temperature_c,
            pressure_bar=operating_pressure_bar,
            composition=composition,
        )

        if calc_error:
            report.calculation_status = "failed"
            report.error_message = calc_error
            logger.error(f"Thermodynamic calculation failed for {pipe_node_id}: {calc_error}")

            # Add informational finding about calculation failure
            report.findings.append(ThermodynamicFinding(
                severity=SeverityLevel.INFO,
                category=AuditCategory.THERMODYNAMIC_CALCULATION,
                title="Thermodynamic Calculation Unavailable",
                description=f"NeqSim calculation could not be performed: {calc_error}",
                recommendation=(
                    "Install neqsim package: pip install neqsim\n"
                    "Verify Java Runtime Environment (JRE) is installed\n"
                    "Manual phase behavior review recommended"
                ),
                technical_details={"error": calc_error},
            ))
        else:
            report.thermodynamic_state = thermo_state

            # 3. Check for multiphase dropout
            if vapor_beta is not None:
                dropout_finding = self._check_multiphase_dropout(vapor_beta, thermo_state)
                if dropout_finding:
                    report.findings.append(dropout_finding)
                    logger.critical(
                        f"MULTIPHASE DROPOUT CRITICAL for {pipe_node_id}: "
                        f"beta={vapor_beta:.4f}, liquid_dropout={1-vapor_beta:.1%}"
                    )

        report.calculation_status = "completed"
        return report

    def audit_pipeline_segment(
        self,
        graph: nx.DiGraph,
        pipe_node_id: str,
        operating_pressure_bar: float,
        operating_temperature_c: float,
        fluid_composition: Optional[Dict[str, float]] = None,
    ) -> ThermodynamicAuditReport:
        """
        Audit a specific pipe node from a NetworkX pipeline graph.

        Extracts line specification from graph node metadata.

        Args:
            graph: NetworkX DiGraph representing the P&ID pipeline.
            pipe_node_id: Node ID of the pipe segment to audit.
            operating_pressure_bar: Operating pressure in bara.
            operating_temperature_c: Operating temperature in °C.
            fluid_composition: Optional fluid composition override.

        Returns:
            ThermodynamicAuditReport for the specified pipe segment.
        """
        if pipe_node_id not in graph:
            raise ValueError(f"Pipe node '{pipe_node_id}' not found in graph")

        node_data = graph.nodes[pipe_node_id]

        # Extract line spec from node attributes
        pipe_node = {
            "id": pipe_node_id,
            "tag_number": node_data.get("tag", node_data.get("label", f"PIPE-{pipe_node_id[:8]}")),
            "line_spec": node_data.get("spec", node_data.get("line_spec", "4\"-CS-150#")),
            "attributes": node_data.get("attributes", {}),
        }

        # Also check incoming edges for line spec (connections may have specs)
        in_edges = list(graph.in_edges(pipe_node_id, data=True))
        out_edges = list(graph.out_edges(pipe_node_id, data=True))

        for _, _, edge_data in in_edges + out_edges:
            if "spec" in edge_data and not pipe_node["line_spec"]:
                pipe_node["line_spec"] = edge_data["spec"]

        return self.audit_pipe_node(
            pipe_node_data=pipe_node,
            operating_pressure_bar=operating_pressure_bar,
            operating_temperature_c=operating_temperature_c,
            fluid_composition=fluid_composition,
        )

    def batch_audit_pipeline(
        self,
        graph: nx.DiGraph,
        operating_pressure_bar: float,
        operating_temperature_c: float,
        fluid_composition: Optional[Dict[str, float]] = None,
        pipe_filter: Optional[callable] = None,
    ) -> List[ThermodynamicAuditReport]:
        """
        Perform thermodynamic audit on all pipe nodes in a pipeline graph.

        Args:
            graph: NetworkX DiGraph representing the P&ID pipeline.
            operating_pressure_bar: Operating pressure in bara.
            operating_temperature_c: Operating temperature in °C.
            fluid_composition: Optional fluid composition override.
            pipe_filter: Optional function(node_data) -> bool to filter which
                pipes to audit.

        Returns:
            List of ThermodynamicAuditReport for each audited pipe segment.
        """
        reports = []

        # Find all pipe/connection nodes
        pipe_nodes = [
            node_id
            for node_id, data in graph.nodes(data=True)
            if data.get("type", "").lower() in ("pipeline", "pipe", "connection", "line")
            or "spec" in data
            or "line_spec" in data
        ]

        logger.info(
            f"Starting batch thermodynamic audit of {len(pipe_nodes)} pipe segments | "
            f"P={operating_pressure_bar:.1f} bar | T={operating_temperature_c:.1f}°C"
        )

        for pipe_node_id in pipe_nodes:
            try:
                # Apply optional filter
                if pipe_filter:
                    node_data = graph.nodes[pipe_node_id]
                    if not pipe_filter(node_data):
                        continue

                report = self.audit_pipeline_segment(
                    graph=graph,
                    pipe_node_id=pipe_node_id,
                    operating_pressure_bar=operating_pressure_bar,
                    operating_temperature_c=operating_temperature_c,
                    fluid_composition=fluid_composition,
                )
                reports.append(report)

            except Exception as e:
                logger.error(f"Failed to audit pipe {pipe_node_id}: {e}")

        logger.info(
            f"Batch audit complete. Audited {len(reports)} segments | "
            f"Critical findings: {sum(1 for r in reports if r.has_critical_findings)} | "
            f"Warnings: {sum(1 for r in reports if r.has_warnings)}"
        )

        return reports


# =============================================================================
# Pydantic Schemas for FastAPI Integration
# =============================================================================

from pydantic import BaseModel, Field, field_validator


class PipeNodeInput(BaseModel):
    """Input schema for a single pipe node to audit."""
    id: str = Field(..., description="Unique identifier for the pipe node")
    tag_number: str = Field(..., description="P&ID tag number (e.g., 'PIPE-101')")
    line_spec: str = Field(default='4"-CS-150#', description="Line specification (e.g., '4\"-CS-150#')")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Additional node attributes")


class ThermodynamicAuditRequest(BaseModel):
    """Request schema for thermodynamic safety audit."""
    pipe_node_data: PipeNodeInput = Field(..., description="Pipe node information to audit")
    operating_pressure_bar: float = Field(
        ...,
        gt=0,
        le=1000,
        description="Operating pressure in bara (1-1000 bar range)"
    )
    operating_temperature_c: float = Field(
        ...,
        ge=-200,
        le=1000,
        description="Operating temperature in Celsius"
    )
    fluid_composition: Optional[Dict[str, float]] = Field(
        None,
        description=(
            "Optional fluid composition as mole fractions. "
            "Defaults to methane-rich natural gas mix if not provided."
        )
    )

    @field_validator("fluid_composition")
    @classmethod
    def validate_composition(cls, v):
        if v is not None:
            total = sum(v.values())
            if abs(total - 1.0) > 0.01:
                raise ValueError(f"Fluid composition mole fractions must sum to 1.0, got {total:.4f}")
        return v


class ThermodynamicAuditRequestBatch(BaseModel):
    """Request schema for batch thermodynamic audit of pipeline graph."""
    graph_data: Dict[str, Any] = Field(..., description="Serialized NetworkX graph data")
    operating_pressure_bar: float = Field(..., gt=0, le=1000, description="Operating pressure in bara")
    operating_temperature_c: float = Field(..., ge=-200, le=1000, description="Operating temperature in °C")
    fluid_composition: Optional[Dict[str, float]] = Field(None, description="Optional fluid composition override")


# =============================================================================
# Existing PID Rules Engine (Preserved from original code)
# =============================================================================

class PIDRulesEngine:
    """Original HAZOP and inspection rules engine (unchanged)."""

    def __init__(self):
        self.thermodynamic_auditor = ThermodynamicSafetyAuditor()

    def ask_local_llm(self, prompt: str) -> str:
        """Query local Ollama LLM for 100% free offline generative analysis."""
        try:
            response = requests.post(
                f"{settings.OLLAMA_URL}/api/generate",
                json={
                    "model": "mistral",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.2},
                },
                timeout=5,
            )
            if response.status_code == 200:
                return response.json().get("response", "").strip()
        except Exception:
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
            incoming_edges = list(graph.in_edges(pump.id, data=True))
            has_fi = False
            valve_tag = "block valve"
            line_spec = "suction line"

            for source, target, data in incoming_edges:
                if "spec" in data:
                    line_spec = data["spec"]
                src_ent = ent_map.get(source)
                if src_ent and src_ent.entity_type == "Valve":
                    valve_tag = src_ent.tag_number

            desc = (
                f"No flow indicator (`FI` or `FIT`) detected on suction line "
                f"`{line_spec}` feeding pump `{pump.tag_number}`. "
                f"If block valve `{valve_tag}` is closed while pump is running, "
                f"severe dead-heading and cavitation hazard will occur."
            )

            llm_prompt = (
                f"In a P&ID HAZOP study for pump {pump.tag_number} fed by line "
                f"{line_spec} with valve {valve_tag}, what are the specific safety "
                f"risks of 'No Flow' deviation? Keep it under 2 sentences."
            )
            llm_desc = self.ask_local_llm(llm_prompt)
            if llm_desc:
                desc = f"**AI Assistant:** {llm_desc}"

            suggestions.append(
                HazopSuggestion(
                    id=str(uuid.uuid4()),
                    document_id=doc_id,
                    deviation="No Flow",
                    description=desc,
                    target_tag=pump.tag_number,
                )
            )

        # 2. Evaluate More Pressure Deviation for Vessels
        vessels = [e for e in entities if e.entity_type == "Vessel"]
        for vessel in vessels:
            desc = (
                f"Upstream steam reboiler feed failure or overhead blockage could "
                f"lead to overpressure in distillation column `{vessel.tag_number}`. "
                f"Evaluate sizing of overhead condenser relief capacity."
            )

            llm_prompt = (
                f"In a P&ID HAZOP study for distillation column {vessel.tag_number}, "
                f"what are the specific safety risks of 'More Pressure' deviation? "
                f"Keep it under 2 sentences."
            )
            llm_desc = self.ask_local_llm(llm_prompt)
            if llm_desc:
                desc = f"**AI Assistant:** {llm_desc}"

            suggestions.append(
                HazopSuggestion(
                    id=str(uuid.uuid4()),
                    document_id=doc_id,
                    deviation="More Pressure",
                    description=desc,
                    target_tag=vessel.tag_number,
                )
            )

        db.add_all(suggestions)
        db.commit()
        print(f"AI HAZOP Assistant complete. Created {len(suggestings)} suggestions.")

    def run_ai_inspector(self, doc_id: str, graph: nx.DiGraph, db: Session):
        """Execute Topological Engineering Validation Engine (API 520/521, ASME B31.3)."""
        print("Executing AI Inspector Engineering Validation Engine...")
        entities = db.query(Entity).filter(Entity.document_id == doc_id).all()
        connections = db.query(Connection).filter(Connection.document_id == doc_id).all()
        ent_map = {e.id: e for e in entities}

        audits = []

        # 1. Spec Mismatch Rule
        for conn in connections:
            source = ent_map.get(conn.source_id)
            target = ent_map.get(conn.target_id)
            line_spec = conn.line_spec

            line_size = line_spec.split('"')[0].split("-")[0] if "-" in line_spec else "4"

            if target and target.entity_type == "Valve":
                val_size = target.attributes.get("size", "2-inch").split("-")[0]
                if line_size != val_size:
                    desc = (
                        f"**Piping Spec Mismatch:** A {line_size}-inch pipe "
                        f"(`{line_spec}`) is directly connected to {val_size}-inch "
                        f"valve `{target.tag_number}` without an intermediate reducer symbol."
                    )
                    audits.append(
                        InspectorAudit(
                            id=str(uuid.uuid4()),
                            document_id=doc_id,
                            category="Spec Mismatch",
                            severity="Warning",
                            description=desc,
                            target_tag=target.tag_number,
                        )
                    )

        # 2. Safety Relief Omission Rule (API 520 / ASME B31.3)
        vessels = [e for e in entities if e.entity_type == "Vessel"]
        for vessel in vessels:
            outgoing_edges = list(graph.out_edges(vessel.id))
            has_psv = False
            for src, tgt in outgoing_edges:
                tgt_ent = ent_map.get(tgt)
                if tgt_ent and (
                    "PSV" in tgt_ent.tag_number
                    or "Relief" in tgt_ent.attributes.get("function", "")
                ):
                    has_psv = True

            if not has_psv:
                desc = (
                    f"**ASME B31.3 / API 520 Safety Flag:** Pressure vessel "
                    f"`{vessel.tag_number}` does not have a Pressure Safety Valve (PSV) "
                    f"or rupture disk connected to its overhead vapor discharge line. "
                    f"Severe overpressure explosion hazard."
                )
                audits.append(
                    InspectorAudit(
                        id=str(uuid.uuid4()),
                        document_id=doc_id,
                        category="Safety Relief Omission",
                        severity="Flag",
                        description=desc,
                        target_tag=vessel.tag_number,
                    )
                )

        db.add_all(audits)
        db.commit()
        print(f"AI Inspector complete. Created {len(audits)} audit reports.")

    def run_thermodynamic_audit(
        self,
        pipe_node_data: Dict[str, Any],
        operating_pressure_bar: float,
        operating_temperature_c: float,
        fluid_composition: Optional[Dict[str, float]] = None,
    ) -> ThermodynamicAuditReport:
        """
        Run thermodynamic safety audit for a pipe node.

        This method integrates the ThermodynamicSafetyAuditor with the
        existing rules engine framework.
        """
        return self.thermodynamic_auditor.audit_pipe_node(
            pipe_node_data=pipe_node_data,
            operating_pressure_bar=operating_pressure_bar,
            operating_temperature_c=operating_temperature_c,
            fluid_composition=fluid_composition,
        )


# Initialize module singleton
rules_engine = PIDRulesEngine()
thermodynamic_auditor = ThermodynamicSafetyAuditor()
