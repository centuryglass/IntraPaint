"""A ComfyUI node used to encode latent image data in tiled blocks."""
from typing import TypedDict, NotRequired, cast, Dict, Any

from src.api.comfyui.nodes.comfy_node import NodeConnection, ComfyNode

NODE_NAME = 'VAEEncodeTiled'
TILE_MIN = 320
TILE_MAX = 4096
TILE_STEP = 64


class VAEEncodeTiledInputs(TypedDict):
    """Latent image tiled decoding input parameter object definition."""
    pixels: NotRequired[NodeConnection]  # raw image data, e.g. from LoadImage.
    vae: NotRequired[NodeConnection]  # VAE model used for decoding. May be baked-in to a regular SD model.
    tile_size: int


class VAEEncodeTiledNode(ComfyNode):
    """A ComfyUI node used to encode latent image data in tiled blocks."""

    # Connection keys:
    PIXELS = 'pixels'
    VAE = 'vae'

    # Output indexes:
    IDX_LATENT = 0

    def __init__(self, tile_size: int) -> None:
        if tile_size < TILE_MIN:
            raise ValueError(f'Tile size {tile_size} is below minimum {TILE_MIN}')
        if tile_size > TILE_MAX:
            raise ValueError(f'Tile size {tile_size} is above maximum {TILE_MAX}')
        if (tile_size % TILE_STEP) != 0:
            raise ValueError(f'Tile size {tile_size} is not a multiple of {TILE_STEP}')
        connection_params = {
            VAEEncodeTiledNode.PIXELS,
            VAEEncodeTiledNode.VAE
        }
        data: VAEEncodeTiledInputs = {'tile_size': tile_size}
        super().__init__(NODE_NAME, cast(Dict[str, Any], data), connection_params, 1)
