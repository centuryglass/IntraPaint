"""Abstract interface for all ComfyUI workflow nodes."""
from copy import deepcopy
from typing import TypeAlias, Dict, Any, Set, TypedDict, Tuple

NodeId: TypeAlias = str  # Should be an integer string
SlotIndex: TypeAlias = int  # connection index within the connected node, not the current one.
NodeConnection: TypeAlias = Tuple[NodeId, SlotIndex]


class NodeDict(TypedDict):
    """Generic node data format."""
    class_type: str
    inputs: Dict[str, Any]


class ComfyNode:
    """Abstract Node class."""

    def __init__(self, class_type: str, input_data: Dict[str, Any], node_input_keys: Set[str],
                 output_count: int) -> None:
        self._class_type = class_type
        self._inputs = input_data
        self._node_input_keys = node_input_keys
        self._output_count = output_count

    @property
    def output_count(self) -> int:
        """Returns the number of outputs the node provides."""
        return self._output_count

    def add_input(self, connected_node: str, output_slot_index: int, input_key: str):
        """Connect one of this node's inputs to another node's output.

        This will check the validity of the input key, but doesn't do anything to validate that the output is correct.
        """
        if input_key not in self._node_input_keys:
            raise ValueError(f'Unexpected input key {input_key}')
        self._inputs[input_key] = (connected_node, output_slot_index)

    def get_dict(self) -> NodeDict:
        """Returns the node API dict."""
        return {
            'class_type': self._class_type,
            'inputs': deepcopy(self._inputs)
        }
