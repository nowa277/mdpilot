"""Node configuration and tool-to-node mapping."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NodeConfig:
    """Configuration for a compute node."""

    node_id: str
    host: str
    user: str
    writable_dir: str
    gpu_info: str

NODES = {
    "lab02": NodeConfig(
      node_id="lab02",
        host="lab02",
        user="zhao",
        writable_dir="/home/2-BB/changshengjie",
        gpu_info="9× TITAN V",
    ),
    "lab03": NodeConfig(
      node_id="lab03",
        host="lab03",
        user="zhao",
        writable_dir="/home/3-FF/changshengjie",
        gpu_info="4× GTX 1080Ti",
    ),
    "lab06": NodeConfig(
        node_id="lab06",
        host="lab06",
        user="zhao",
        writable_dir="/home/6-FF/changshengjie",
        gpu_info="9× RTX 3090",
    ),
}

TOOL_NODE_MAP: dict[str, str] = {
    "alphafold2_predict": "lab02",
    "bioreason_annotate": "lab06",
    "pdb4amber": "lab03",
    "tleap": "lab03",
    "pmemd.cuda": "lab03",
    "mmpbsa": "lab03",
    "bash_run": "lab03",
    "file_read": "lab03",
    "file_write": "lab03",
    "knowledge_search": "lab03",
}

DEFAULT_NODE = "lab03"


def get_node_for_tool(tool_name: str) -> NodeConfig:
    """Return the node config for a given tool name."""
    node_id = TOOL_NODE_MAP.get(tool_name, DEFAULT_NODE)
    return NODES[node_id]
