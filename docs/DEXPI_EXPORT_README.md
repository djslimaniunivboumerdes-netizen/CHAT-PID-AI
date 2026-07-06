# CHAT-PID-AI: DEXPI Export Module

## Overview

This module extends CHAT-PID-AI with **official DEXPI (Data Exchange in the Process Industry)** XML export capabilities using the open-source [pyDEXPI](https://github.com/process-intelligence-research/pyDEXPI) library.

DEXPI is an ISO 15926-based standard for machine-readable P&ID data that enables interoperability between engineering tools, digital twins, and AI applications.

## Features

### 📤 DEXPI XML Export

- **Standard-compliant export** to DEXPI Proteus XML format (version 1.3)
- **Automatic node mapping** from P&ID entity types to DEXPI equipment classes
- **Topological preservation** of piping connections and flow directions
- **Graceful degradation** with warnings for unrecognized node types
- **Validation** of exported XML structure

### 🔄 Node Type Mappings

The export engine automatically maps P&ID entity types to official DEXPI classes:

| P&ID Entity Type | DEXPI Class | Description |
|------------------|-------------|-------------|
| Vessel, Tank, Drum | `Vessel` | Storage vessels and drums |
| PressureVessel | `PressureVessel` | High-pressure vessels |
| ProcessColumn, Tower | `ProcessColumn` | Distillation/tray columns |
| Pump | `CentrifugalPump` | Centrifugal process pumps |
| ReciprocatingPump | `ReciprocatingPump` | Positive displacement pump |
| HeatExchanger | `ShellAndTubeHeatExchanger` | Shell & tube heat exchangers |
| PlateHE | `PlateHeatExchanger` | Plate-type heat exchangers |
| GateValve, GlobeValve | `GateValve`, `GlobeValve` | Manual valves |
| BallValve | `BallValve` | Quarter-turn ball valves |
| ButterflyValve | `ButterflyValve` | Butterfly-type valves |
| CheckValve | `CheckValve` | Non-return valves |
| SafetyValve, PSV | `SpringLoadedGlobeSafetyValve` | Pressure safety valves |
| ControlValve | `ControlValve` | Modulating control valves |
| Pipeline, Pipe, Line | `PipingNetworkSegment` | Piping segments |
| Instrument, Sensor | `ProcessInstrumentationFunction` | Process instrumentation |

## Installation

### Prerequisites

1. **Python 3.12+** (pyDEXPI requirement)
   ```bash
   python --version  # Must be 3.12 or higher
   ```

### Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- `pydexpi>=1.2.0` - DEXPI data model implementation

### Verify Installation

```bash
python -c "from pydexpi.dexpi_classes import Vessel; print('pyDEXPI OK')"
```

## Usage

### Option 1: Python API

```python
import networkx as nx
from export_engine import export_graph_to_dexpi_xml

# Create P&ID graph
G = nx.DiGraph()
G.add_node("V-101", tag="V-101", type="Vessel", spec='6"-CS-300#')
G.add_node("P-101", tag="P-101", type="Pump", spec='4"-CS-150#')
G.add_edge("V-101", "P-101", spec='4"-CS-150#', flow="forward")

# Export to DEXPI
result = export_graph_to_dexpi_xml(G, "exports/PID_001.xml")

if result.success:
    print(f"Exported to {result.output_path}")
    print(f"Nodes: {result.nodes_exported}, Edges: {result.edges_exported}")
```

### Option 2: Direct Export Engine Usage

```python
from export_engine import DEXPIExportEngine, DEXPIExportOptions

options = DEXPIExportOptions(
    project_name="My P&ID Project",
    author="Process Engineering",
    strict_mapping=False,
)

engine = DEXPIExportEngine(options=options)
result = engine.export_graph_to_dexpi_xml(graph, "output.xml")

# Get statistics
stats = engine.get_export_statistics()
```

### Option 3: FastAPI Endpoints

Start the server and access the API at `http://localhost:7860/docs`

#### Check DEXPI Status
```bash
curl http://localhost:7860/api/export/dexpi/status
```

#### Export Document to DEXPI
```bash
curl -X POST "http://localhost:7860/api/export/dexpi/{doc_id}"
```

#### Direct Graph Export
```bash
curl -X POST "http://localhost:7860/api/export/dexpi/direct" \
  -H "Content-Type: application/json" \
  -d '{
    "graph_data": {
      "nodes": [
        {"id": "V-101", "tag": "V-101", "type": "Vessel", "spec": "6\"-CS-300#"}
      ],
      "edges": [
        {"source": "V-101", "target": "P-101", "spec": "4\"-CS-150#"}
      ]
    },
    "project_name": "My Project"
  }'
```

#### Download DEXPI File
```bash
curl -O "http://localhost:7860/api/export/dexpi/download/{doc_id}"
```

## API Reference

### Classes

#### `DEXPIExportEngine`
Main export engine class.

```python
engine = DEXPIExportEngine(options=None)
result = engine.export_graph_to_dexpi_xml(graph, output_path, options=None)
stats = engine.get_export_statistics()
```

#### `DEXPIExportOptions`
Configuration options for export.

```python
options = DEXPIExportOptions(
    project_name="Project Name",
    author="Author Name",
    organization="Organization",
    version="1.0",
    validate_xml=True,
    pretty_print=True,
    strict_mapping=False,
    default_equipment_class="CustomEquipment",
)
```

#### `DEXPIExportResult`
Result of an export operation.

```python
result.success           # bool: Export succeeded
result.output_path       # str: Path to output file
result.error_message     # str: Error message if failed
result.nodes_exported    # int: Number of nodes exported
result.edges_exported    # int: Number of edges exported
result.warnings          # list: Warnings encountered
result.exported_objects  # dict: Mapping of node IDs to DEXPI classes
```

### Functions

#### `export_graph_to_dexpi_xml(networkx_graph, output_path, options=None)`
Export a NetworkX graph to DEXPI XML format.

**Parameters:**
- `networkx_graph` (nx.DiGraph): The P&ID graph to export
- `output_path` (str): Output file path
- `options` (DEXPIExportOptions): Optional configuration

**Returns:** `DEXPIExportResult`

### FastAPI Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/export/dexpi/status` | Check pyDEXPI availability |
| POST | `/api/export/dexpi/{doc_id}` | Export document to DEXPI |
| POST | `/api/export/dexpi/direct` | Direct graph export |
| GET | `/api/export/dexpi/download/{doc_id}` | Download DEXPI file |

## NetworkX Graph Format

The NetworkX graph should have nodes with the following attributes:

```python
G.add_node(
    "V-101",                           # Node ID
    tag="V-101",                       # Equipment tag
    type="Vessel",                     # Entity type (maps to DEXPI class)
    spec='6"-CS-300#',                 # Pipe/equipment specification
    attributes={                       # Additional metadata
        "material": "Carbon Steel",
        "rating": "Class 300",
    }
)
```

Edges represent connections with flow direction:

```python
G.add_edge(
    "V-101",                           # Source node
    "P-101",                          # Target node
    spec='4"-CS-150#',                # Line specification
    flow="forward"                    # Flow direction
)
```

## DEXPI Standard

The exported files conform to the DEXPI (Data Exchange in the Process Industry) standard, specifically:

- **Version**: 1.3
- **Format**: Proteus XML (ISO 15926 based)
- **Schema**: Full DEXPI information model including:
  - Plant structure hierarchy
  - Piping network systems
  - Equipment with tags and specifications
  - Instrumentation functions
  - Topology relationships

## Error Handling

The export engine provides robust error handling:

1. **Unrecognized Node Types**: Logs warning, exports with `CustomEquipment` class
2. **Missing Required Fields**: Uses defaults where possible
3. **XML Validation Errors**: Reports detailed error messages
4. **pyDEXPI Not Available**: Clear error message with installation instructions

## Troubleshooting

### "pyDEXPI not available"

```bash
# Check Python version (must be 3.12+)
python --version

# Install pyDEXPI
pip install pydexpi
```

### "Invalid node type" warnings

These are informational. The engine will:
1. Log a warning with the unrecognized type
2. Export the node using the `default_equipment_class`
3. Continue processing other nodes

Set `strict_mapping=True` to fail on unrecognized types instead.

### XML validation errors

Check the `result.warnings` list for specific issues. Common causes:
- Missing required attributes
- Invalid tag number format
- Incompatible equipment connections

## Examples

See `examples/dexpi_export_example.py` for comprehensive test cases:

```bash
# Run DEXPI export examples
python examples/dexpi_export_example.py
```

## Architecture

```
export_engine.py
├── DEXPIExportEngine (main class)
│   ├── export_graph_to_dexpi_xml()
│   ├── _map_node_type_to_dexpi()
│   ├── _create_dexpi_equipment()
│   ├── _build_dexpi_model()
│   └── get_export_statistics()
│
├── NODE_TYPE_TO_DEXPI_CLASS (mapping dict)
│
├── export_graph_to_dexpi_xml() (convenience function)
│
└── PIDExportEngine (original class, unchanged)
```

## Contributing

Contributions to enhance DEXPI export capabilities are welcome:

1. Add new equipment class mappings
2. Improve error handling
3. Add validation rules
4. Support additional DEXPI classes

## License

This module is part of CHAT-PID-AI and licensed under Apache 2.0.

## References

- [DEXPI Official Website](https://dexpi.org/)
- [pyDEXPI GitHub](https://github.com/process-intelligence-research/pyDEXPI)
- [ISO 15926 Standard](https://www.iso.org/standard/30948.html)
- [DEXPI Information Model](https://dexpi.plants-and-bytes.de/)
