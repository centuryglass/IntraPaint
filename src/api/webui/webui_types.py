"""Misc. WebUI API data formats."""
from typing import TypedDict, List, Any, Dict, TypeAlias


# LoRA model data:
class LoraMetadata(TypedDict, total=False):
    """Extra metadata associated with a LoRA model.  I've left out a lot of parameters, this just defines the ones
       that IntraPaint might want to show to users eventually."""
    ss_sd_model_name: str  # Model used for training
    ss_sd_model_hash: str
    ss_resolution: str  # str(tuple(width, height))
    ss_clip_skip: str  # int string, or "None"
    ss_num_train_images: str  # int string
    ss_dataset_dirs: Dict[str, Dict[str, int]]  # Training data directories
    ss_enable_bucket: str  # bool string
    ss_epoch: str  # int string

    # Bucket data structure: it's potentially useful to see what sizes the LoRA is trained on.
    # bucket_idx: { "resolution": [width, height], "count": num_images }
    ss_bucket_info: Dict[str, Any]  # Training image resolution groups

    # Training tags: potentially useful for constructing LoRA prompts.
    ss_tag_frequency: Dict[str, Dict[str, int]]

    sshs_model_hash: str


class LoraInfo(TypedDict):
    """Data used to define a LoRA model in API responses."""
    name: str
    alias: str
    path: str  # NOTE: this is an absolute path
    metadata: LoraMetadata


# Prompt styles are sent as a list of JSON object strings.
PromptStyleRes: TypeAlias = List[str]

class PromptStyleData(TypedDict):
    """List entry from PromptStyleRes, after parsing."""
    name: str
    prompt: str
    negative_prompt: str

