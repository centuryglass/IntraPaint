"""Manages a set of connected ComfyUI nodes."""
from copy import deepcopy
from typing import Any

from src.api.comfyui.nodes.comfy_node import ComfyNode


class ComfyNodeGraph:
    """Manages a set of connected ComfyUI nodes."""

    def __init__(self) -> None:
        self._node_key_dict: dict[ComfyNode, str] = {}
        self._next_key_number = 3

    def __deepcopy__(self, memo: dict[int, Any]) -> 'ComfyNodeGraph':
        graph_copy = ComfyNodeGraph()
        for node in self._node_key_dict:
            graph_copy.add_node(deepcopy(node))
        memo[id(self)] = graph_copy
        return graph_copy

    def add_node(self, node: ComfyNode) -> None:
        """Adds a new node to the graph."""
        assert node not in self._node_key_dict, 'Node already added'
        self._node_key_dict[node] = str(self._next_key_number)
        self._next_key_number += 1

    def connect_nodes(self, input_node: ComfyNode, input_key: str, output_node: ComfyNode, out_slot_idx: int):
        """Adds a new connection between graph nodes.

        This will validate the input_key (implicitly, within the ComfyNode method) and the out_slot_idx, and make sure
        both nodes are actually in the graph, but it won't do anything to validate that the output data is compatible
        with the input slot.
        """
        if out_slot_idx < 0 or out_slot_idx >= output_node.output_count:
            raise ValueError(f'Invalid output index: expected 0-{output_node.output_count-1}, got {out_slot_idx}')
        if input_node not in self._node_key_dict:
            self.add_node(input_node)
        if output_node not in self._node_key_dict:
            self.add_node(output_node)
        output_key = self._node_key_dict[output_node]
        input_node.add_input(output_key, out_slot_idx, input_key)

    def get_workflow_dict(self) -> dict[str, Any]:
        """Gets the dict defining the entire workflow."""
        workflow = {}
        nodes = list(self._node_key_dict.keys())
        nodes.sort(key=lambda node: int(self._node_key_dict[node]))
        for graph_node in nodes:
            workflow[self._node_key_dict[graph_node]] = graph_node.get_dict()
        return workflow
