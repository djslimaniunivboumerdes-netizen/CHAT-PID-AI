# CHAT-PID-AI: Thermodynamic Safety Audit Module

## Overview

This module extends CHAT-PID-AI with **physics-aware safety auditing** capabilities using the open-source [NeqSim](https://github.com/equinor/neqsim) thermodynamic library. It performs equation-of-state (EOS) calculations to detect dangerous operating conditions in P&ID pipeline segments.

## Features

### 🔬 Thermodynamic Calculations (NeqSim SRK EOS)

- **TPflash calculations** for vapor-liquid equilibrium (VLE)
- **Phase fraction analysis** (vapor fraction β)
- **Density and enthalpy** calculations for each phase
- **Supercritical fluid detection**

### ⚠️ Safety Risk Detection

#### 1. Multiphase Dropout Detection (CRITICAL)
Identifies two-phase flow conditions that can cause:
- **Liquid slugging** - destructive pressure surges
- **Water hammer** - catastrophic pipe damage
- **Erosion-corrosion** - accelerated pipe wall wear
- **Process upset** - control valve malfunction
- **Equipment damage** - pump/compressor cavitation

**Detection Logic:**
```
if 0.0 < β < 0.95 → CRITICAL WARNING
```

#### 2. ANSI Class Rating Exceedance (WARNING)
Validates that operating pressure doesn't exceed the maximum allowable pressure for the pipe's ANSI class rating per ASME B31.3.

| ANSI Class | Max Pressure (bara) |
|------------|---------------------|
| 150#       | 19.6                |
| 300#       | 51.1                |
| 400#       | 68.5                |
| 600#       | 102.7               |
| 900#       | 154.5               |
| 1500#      | 256.9               |
| 2500#      | 422.0               |

## Installation

### Prerequisites

1. **Python 3.9+**
2. **Java Runtime Environment (JRE) 8 or higher**
   ```bash
   # Ubuntu/Debian
   sudo apt install default-jre
   
   # macOS
   brew install openjdk
   ```

### Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- `neqsim>=2.0.0` - Thermodynamic calculations
- `jpype1>=1.4.0` - Python-Java interoperability

### Verify Installation

```bash
python -c "from neqsim.thermo import fluid, TPflash; print('NeqSim OK')"
```

## Usage

### Option 1: Python API

```python
from rules_engine import thermodynamic_auditor

# Single pipe audit
pipe_data = {
    "id": "pipe-001",
    "tag_number": "PIPE-101",
    "line_spec": '4"-CS-150#',
}

report = thermodynamic_auditor.audit_pipe_node(
    pipe_node_data=pipe_data,
    operating_pressure_bar=25.0,
    operating_temperature_c=80.0,
)

# Check for critical findings
if report.has_critical_findings:
    for finding in report.findings:
        print(f"🔴 {finding.title}")
        print(f"   {finding.description}")
```

### Option 2: FastAPI Endpoints

Start the server and access the API at `http://localhost:7860/docs`

#### Single Pipe Audit
```bash
curl -X POST "http://localhost:7860/api/audit/thermodynamic/single" \
  -H "Content-Type: application/json" \
  -d '{
    "pipe_node_data": {
      "id": "pipe-101",
      "tag_number": "PIPE-101",
      "line_spec": "4\"-CS-150#"
    },
    "operating_pressure_bar": 30.0,
    "operating_temperature_c": 50.0
  }'
```

#### Batch Pipeline Audit
```bash
curl -X POST "http://localhost:7860/api/audit/thermodynamic/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "graph_data": {
      "nodes": [...],
      "edges": [...]
    },
    "operating_pressure_bar": 45.0,
    "operating_temperature_c": 60.0
  }'
```

### Option 3: Run Test Examples

```bash
# Run all test cases
python examples/thermodynamic_audit_example.py

# Test API endpoints
bash examples/api_examples.sh
```

## API Reference

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/audit/thermodynamic/status` | Check NeqSim availability |
| POST | `/api/audit/thermodynamic/single` | Audit single pipe segment |
| POST | `/api/audit/thermodynamic/batch` | Audit multiple pipe segments |
| GET | `/api/audit/thermodynamic/pipeline/{doc_id}` | Audit processed P&ID document |

### Response Schema

```json
{
  "audit_id": "uuid",
  "pipe_node_id": "pipe-001",
  "line_spec": "4\"-CS-150#",
  "operating_pressure_bar": 25.0,
  "operating_temperature_c": 80.0,
  "findings": [
    {
      "severity": "Critical|Warning|Info",
      "category": "Multiphase Dropout Risk|ANSI Class Rating Exceeded|...",
      "title": "Finding title",
      "description": "Detailed description",
      "recommendation": "Actionable mitigation steps",
      "technical_details": {...}
    }
  ],
  "thermodynamic_state": {
    "vapor_fraction_beta": 0.8500,
    "phase_status": "two_phase_near_vapor",
    "gas_density_kg_m3": 45.234,
    "liquid_density_kg_m3": 612.456
  },
  "has_critical_findings": true|false
}
```

## Default Fluid Composition

The auditor uses a methane-rich natural gas mixture by default:

| Component | Mole Fraction |
|-----------|---------------|
| Methane | 0.850 |
| Ethane | 0.080 |
| Propane | 0.050 |
| n-Butane | 0.015 |
| i-Butane | 0.005 |
| n-Pentane | 0.002 |
| i-Pentane | 0.002 |
| Nitrogen | 0.001 |
| CO₂ | 0.001 |

Override with custom composition:
```python
composition = {
    "methane": 0.72,
    "ethane": 0.08,
    "propane": 0.05,
    "CO2": 0.03,
    # ...
}
```

## Safety Standards Compliance

The thermodynamic audit module supports compliance with:

- **ASME B31.3** - Process Piping
- **API 520/521** - Pressure Relieving Devices
- **API 521** - Pressure Relieving and Depressuring Systems
- **ASME Section VIII** - Pressure Vessels

## Error Handling

The auditor gracefully handles:

- **NeqSim not installed** → Returns INFO status, no crash
- **Calculation convergence failure** → Returns error in report
- **Invalid line spec** → Falls back to default parsing
- **Invalid composition** → Validates and normalizes

## Troubleshooting

### NeqSim Installation Issues

```bash
# Install NeqSim
pip install neqsim

# Verify Java is available
java -version

# Set JAVA_HOME if needed
export JAVA_HOME=/usr/lib/jvm/default-java
```

### Common Errors

| Error | Solution |
|-------|----------|
| `No module named 'neqsim'` | Run `pip install neqsim` |
| `jpype JVM not found` | Install JRE and set JAVA_HOME |
| `Calculation did not converge` | Check pressure/temperature ranges |

## Architecture

```
rules_engine.py
├── PIDRulesEngine (original class)
│   ├── ask_local_llm()
│   ├── run_hazop_analysis()
│   └── run_ai_inspector()
│
└── ThermodynamicSafetyAuditor (new class)
    ├── audit_pipe_node()
    ├── audit_pipeline_segment()
    ├── batch_audit_pipeline()
    ├── _run_neqsim_calculation()
    ├── _check_multiphase_dropout()
    └── _check_ansi_class_exceedance()
```

## Contributing

Contributions to enhance the thermodynamic audit capabilities are welcome:

1. Add new equation of state models (PR, CPA, etc.)
2. Implement additional safety checks
3. Add support for more fluid types
4. Improve error handling and convergence

## License

This module is part of CHAT-PID-AI and licensed under Apache 2.0.

## References

- [NeqSim Documentation](https://equinor.github.io/neqsim/)
- [NeqSim GitHub](https://github.com/equinor/neqsim)
- [ASME B31.3 Process Piping](https://www.asme.org/codes-standards/b31-3-process-piping)
- [API 520 Sizing Selection](https://www.api.org/standards/520)
