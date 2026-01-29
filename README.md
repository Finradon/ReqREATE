# ReqRE - Requirements Rewriting Engine
A driver for graph rewriting in a [Neo4j](https://neo4j.com/) database based on [SysML](https://www.omg.org/spec/SysML/) requirements.

## Purpose

This software is for locally defining graph rewriting rules using the Python [NetworkX](https://networkx.org/) library, based on locally defined SysML requirements. Intended use is the formalization of design automation in modular bridge design (using concrete modules).

The requirements always represent the LHS of the rules. Based on a pattern of requirements, the graph is rewritten to satisfy those requirements. This may be a simple subgraph of building components or more intricate rewriting processes.

The rules are stored as `networkx.MultiDiGraph` objects and are then intended to be serialized into [Cypher](https://neo4j.com/developer/cypher/). The resulting Cypher query can then be used to enact these changes in the Neo4j graph database.

## Development Setup

Gaphor requires system packages before installing the Python dependencies.

Debian/Ubuntu:

```bash
sudo apt install libcairo2-dev pkg-config python3-dev libgirepository1.0-dev libgtk-4-dev gir1.2-pango-1.0 libgtksourceview-5-dev gir1.2-adw-1
```

Fedora:

```bash
sudo dnf install cairo-devel pkgconf-pkg-config python3-devel gobject-introspection-devel gtk4-devel pango-devel gtksourceview5-devel libadwaita-devel
```

Arch:

```bash
sudo pacman -S --needed \
  cairo \
  pkgconf \
  python \
  gobject-introspection \
  gtk4 \
  pango \
  gtksourceview5 \
  libadwaita
```

Python environment setup:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
gaphor install-schemas
pip install -e .
```

## Neo4j Connection

Set credentials in your environment before running code:

```bash
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=neo4jneo4j
```

Example usage:

```python
from reqre.neo4j import Neo4jClient

with Neo4jClient() as client:
    rows = client.execute("MATCH (n) RETURN count(n) AS total")
    print(rows)
```

CLI demo:

```bash
python scripts/demo_neo4j.py --query "RETURN 1 AS ok"
```

## Gaphor Requirements Import

You can load SysML requirements from a `.gaphor` model and push them to Neo4j:

```python
from reqre.gaphor_requirements import (
    load_requirement_relationships_from_file,
    load_requirements_from_file,
    push_requirement_relationships_to_neo4j,
    push_requirements_to_neo4j,
)
from reqre.neo4j import Neo4jClient

requirements = load_requirements_from_file("gaphor_files/ArchBridgeRequirements.gaphor")
relationships = load_requirement_relationships_from_file("gaphor_files/ArchBridgeRequirements.gaphor")
with Neo4jClient() as client:
    push_requirements_to_neo4j(client, requirements)
    push_requirement_relationships_to_neo4j(client, relationships)
```

Only `SysML:Requirement` elements are imported; diagram presentation items are ignored. Requirement-to-requirement relationships (for example, `Refine`) are modeled as relationships between `Requirement` nodes.

## Quick Start (Rule Representation)

```python
import networkx as nx

from reqre.cypher import rule_to_cypher
from reqre.rules import DpoRule, add_edge, add_node

left = nx.MultiDiGraph()
interface = nx.MultiDiGraph()
right = nx.MultiDiGraph()

add_node(left, "req1", label="Requirement", props={"id": "REQ-1"})
add_node(interface, "req1", label="Requirement", props={"id": "REQ-1"})
add_node(right, "req1", label="Requirement", props={"id": "REQ-1"})
add_node(right, "comp1", label="Component", props={"name": "Beam"})

add_edge(right, "req1", "comp1", rel_type="SATISFIES")

rule = DpoRule(left=left, interface=interface, right=right)
cypher = rule_to_cypher(rule)

print(rule.summary())
print(cypher.query)
print(cypher.params)
```

## GraphML Import/Export

You can serialize rules to a single GraphML file and load them back:

```python
from reqre.graphml import export_rule_graphml, import_rule_graphml

export_rule_graphml(rule, "rule.graphml")
loaded_rule = import_rule_graphml("rule.graphml")
```

GraphML stores rule membership per node/edge using metadata, and `props` are
encoded as JSON strings for portability.

## Workflow (Rule Application)

* Rule = (L, K, R), each as `networkx.MultiDiGraph`

* match(rule, host_graph) -> Match

* apply_dpo(rule, host_graph, match) -> Delta(delete, create, set_props)

* delta_to_cypher(delta) -> (query, params)

* run(query, params)

## Cypher Serialization Notes

- Interface nodes must be present in both left and right; nodes shared by left/right must appear in the interface.
- Interface edges must be present in both left and right; shared edges must appear in the interface.
- Deletions are supported; deleted nodes must have no extra relationships outside the matched LHS.
- Preserved nodes must keep identical labels/props across L/K/R (attribute updates are not serialized yet).
- Node `label` (string or sequence) and edge `type` must be valid Cypher identifiers.
- `props` must be a mapping with string keys; values are parameterized.
- Relationship types are required for created edges; missing types on the LHS mean "match any type."
