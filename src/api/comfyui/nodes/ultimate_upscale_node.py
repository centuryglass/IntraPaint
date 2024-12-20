"""A ComfyUI node used to apply the 'Ultimate SD Upscale' script."""
from typing import TypedDict, NotRequired, cast, Any, Literal, Optional

from src.api.comfyui.nodes.comfy_node import NodeConnection, ComfyNode

ULTIMATE_UPSCALE_NODE_NAME = 'UltimateSDUpscale'
ULTIMATE_UPSCALE_NODE_WITHOUT_UPSCALE_MODEL = 'UltimateSDUpscaleNoUpscale'


class UltimateUpscaleCoreInputs(TypedDict):
    """Primary inputs, excluding those related to the optional seam fix mode."""
    upscale_by: NotRequired[float]  # Leave out only if the "no upscale" option is chosen.
    seed: int
    steps: int
    cfg: float  # Cache.GUIDANCE_SCALE
    sampler_name: str
    scheduler: str
    denoise: float  # Cache.DENOISING_STRENGTH
    mode_type: Literal['Linear', 'Chess', 'None']
    tile_width: int
    tile_height: int
    mask_blur: int
    tile_padding: int
    force_uniform_tiles: bool  # default=True
    tiled_decode: bool  # default=False


class SeamFixInputs(TypedDict):
    """Inputs for the optional 'Seam Fix' mode:"""
    seam_fix_mode: Literal['None', 'Band Pass', 'Half Tile', 'Half Tile + Intersections']
    seam_fix_denoise: float
    seam_fix_width: int  # default=64
    seam_fix_mask_blur: int  # default=8
    seam_fix_padding: int  # default=16


IMAGE_KEY_WITH_UPSCALER = 'image'
IMAGE_KEY_WITHOUT_UPSCALER = 'upscaled_image'


class UltimateUpscaleInputs(TypedDict):
    """Full inputs for the "Ultimate SD Upscale" node."""
    image: NotRequired[NodeConnection]  # Image source node (upscaler mode only)
    upscaled_image: NotRequired[NodeConnection]  # Image source node (no upscaler mode only)
    model: NotRequired[NodeConnection]  # Usually CheckpointLoaderSimple
    positive: NotRequired[NodeConnection]  # Usually CLIPTextEncode
    negative: NotRequired[NodeConnection]  # Usually CLIPTextEncode
    vae: NotRequired[NodeConnection]
    upscale_model: NotRequired[NodeConnection]  # Leave out only if the "no upscale" option is chosen.
    upscale_by: NotRequired[float]  # Leave out only if the "no upscale" option is chosen.
    seed: int
    steps: int
    cfg: float  # Cache.GUIDANCE_SCALE
    sampler_name: str
    scheduler: str
    denoise: float  # Cache.DENOISING_STRENGTH
    mode_type: Literal['Linear', 'Chess', 'None']
    tile_width: int
    tile_height: int
    mask_blur: int
    tile_padding: int
    seam_fix_mode: Literal['None', 'Band Pass', 'Half Tile', 'Half Tile + Intersections']
    seam_fix_denoise: float
    seam_fix_width: int  # default=64
    seam_fix_mask_blur: int  # default=8
    seam_fix_padding: int  # default=16
    force_uniform_tiles: bool  # default=True
    tiled_decode: bool  # default=False


class UltimateUpscaleNode(ComfyNode):
    """A ComfyUI node used to apply the 'Ultimate SD Upscale' script."""

    # Connection keys:
    IMAGE = 'image'
    MODEL = 'model'
    POSITIVE = 'positive'
    NEGATIVE = 'negative'
    VAE = 'vae'
    UPSCALE_MODEL = 'upscale_model'

    # Output indexes:
    IDX_IMAGE = 0

    def __init__(self,
                 core_inputs: UltimateUpscaleCoreInputs, use_upscaler=True,
                 seam_fix_settings: Optional[SeamFixInputs] = None) -> None:
        if seam_fix_settings is None:
            seam_fix_settings = {
                'seam_fix_mode': 'None',
                'seam_fix_denoise': 0.0,
                'seam_fix_width': 64,
                'seam_fix_mask_blur': 8,
                'seam_fix_padding': 16
            }
        data: UltimateUpscaleInputs = {
            'seed': core_inputs['seed'],
            'steps': core_inputs['steps'],
            'cfg': core_inputs['cfg'],
            'sampler_name': core_inputs['sampler_name'],
            'scheduler': core_inputs['scheduler'],
            'denoise': core_inputs['denoise'],
            'mode_type': core_inputs['mode_type'],
            'tile_width': core_inputs['tile_width'],
            'tile_height': core_inputs['tile_height'],
            'mask_blur': core_inputs['mask_blur'],
            'tile_padding': core_inputs['tile_padding'],
            'force_uniform_tiles': core_inputs['force_uniform_tiles'],
            'tiled_decode': core_inputs['tiled_decode'],
            'seam_fix_mode': seam_fix_settings['seam_fix_mode'],
            'seam_fix_denoise': seam_fix_settings['seam_fix_denoise'],
            'seam_fix_width': seam_fix_settings['seam_fix_width'],
            'seam_fix_mask_blur': seam_fix_settings['seam_fix_mask_blur'],
            'seam_fix_padding': seam_fix_settings['seam_fix_padding']
        }
        connection_params = {
            UltimateUpscaleNode.IMAGE,
            IMAGE_KEY_WITHOUT_UPSCALER,
            UltimateUpscaleNode.MODEL,
            UltimateUpscaleNode.POSITIVE,
            UltimateUpscaleNode.NEGATIVE,
            UltimateUpscaleNode.VAE
        }
        node_name = ULTIMATE_UPSCALE_NODE_WITHOUT_UPSCALE_MODEL
        if use_upscaler:
            node_name = ULTIMATE_UPSCALE_NODE_NAME
            data['upscale_by'] = core_inputs['upscale_by']
            connection_params.add(UltimateUpscaleNode.UPSCALE_MODEL)
        super().__init__(node_name, cast(dict[str, Any], data), connection_params, 1)

    def add_input(self, connected_node: str, output_slot_index: int, input_key: str):
        """Connect one of this node's inputs to another node's output.

        This will check the validity of the input key, but doesn't do anything to validate that the output is correct.
        It will also correct the image key if necessary, since the Ultimate Upscale node uses a slightly different key
        depending on which variant of it is being used.
        """
        if input_key == IMAGE_KEY_WITHOUT_UPSCALER and self.node_name == ULTIMATE_UPSCALE_NODE_NAME:
            input_key = IMAGE_KEY_WITH_UPSCALER
        elif input_key == IMAGE_KEY_WITH_UPSCALER and self.node_name == ULTIMATE_UPSCALE_NODE_WITHOUT_UPSCALE_MODEL:
            input_key = IMAGE_KEY_WITHOUT_UPSCALER
        super().add_input(connected_node, output_slot_index, input_key)
