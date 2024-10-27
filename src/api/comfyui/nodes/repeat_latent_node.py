"""A ComfyUI node used to copy latent image data for batch operations."""
from typing import TypedDict, NotRequired, cast, Dict, Any

from src.api.comfyui.nodes.comfy_node import NodeConnection, ComfyNode

NODE_NAME = 'RepeatLatentBatch'


class RepeatLatentInputs(TypedDict):
    """Latent image batch creation parameters."""
    samples: NotRequired[NodeConnection]  # latent image data, e.g. from VAEEncodeNode.
    amount: int  # Number of repeated copies.


class RepeatLatentNode(ComfyNode):
    """A ComfyUI node used to copy latent image data for batch operations."""

    # Connection keys:
    SAMPLES = 'samples'

    # Output indexes:
    IDX_LATENT = 0

    def __init__(self, batch_size: int) -> None:
        connection_params = {RepeatLatentNode.SAMPLES}
        data: RepeatLatentInputs = {
            'amount': batch_size
        }
        super().__init__(NODE_NAME, cast(Dict[str, Any], data), connection_params, 1)
