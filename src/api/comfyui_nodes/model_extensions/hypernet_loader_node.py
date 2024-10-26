"""A ComfyUI node used to load a hypernetwork model extension."""
from typing import TypedDict, NotRequired

from src.api.comfyui_nodes.comfy_node import NodeConnection, ComfyNode

NODE_NAME = 'HypernetworkLoader'


class HypernetLoaderInputs(TypedDict):
    """Inputs for hypernetwork model loading."""
    hypernetwork_name: str
    strength: float
    model: NotRequired[NodeConnection]


class HypernetLoaderNode(ComfyNode):
    """A ComfyUI node used to load a hypernetwork model extension."""

    # Connection keys:
    MODEL = 'model'

    # Output indexes:
    IDX_MODEL = 0

    def __init__(self, hypernetwork_name: str, strength: float) -> None:
        connection_params = {
            HypernetLoaderNode.MODEL
        }
        data: HypernetLoaderInputs = {
            'hypernetwork_name': hypernetwork_name,
            'strength': strength
        }
        super().__init__(NODE_NAME, data, connection_params, 1)
