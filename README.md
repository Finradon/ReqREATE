# ReqRE - Requirements Rewriting Engine
A driver for graph rewriting in a Neo4j Database based on SysML requirements. 

## Purpose

This software is for locally defining graph rewriting rules using the python networkx library, based on locally defined SysML requirements. Intened use is the formalization of design automation in modular bridge design (using concrete modules).

The requirements always represent the LHS of the rules. Based on a pattern of requirements, the graph is rewritten to satisfy said requirements. This may be a simple subgraph of building components or more intricate rewriting processes.

The Rules are stored as networkx.MultiDiGraphs, and are then intended to be serialized into cypher. The resulting cypher query can then be used to enact these changes in the neo4j graph database. 

## Workflow (Rule Application)

* Rule = (L,K,R) each as networkx.MultiDiGraph

* match(rule, host_graph) -> Match

* apply_dpo(rule, host_graph, match) -> Delta(delete, create, set_props)

* delta_to_cypher(delta) -> (query, params)

* run(query, params)
