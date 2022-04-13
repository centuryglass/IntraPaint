# GLID-3-XL

GLID-3-xl is the [1.4B latent diffusion](https://github.com/CompVis/latent-diffusion#april-2022) model from CompVis back-ported to the guided diffusion codebase

The model has been split into three checkpoints. This lets us fine tune the diffusion model on new datasets and for additional tasks like inpainting and super-resolution

# Install

First install [latent diffusion](https://github.com/CompVis/latent-diffusion)
```
# then
git clone https://github.com/Jack000/glid-3-xl
cd glid-3-xl
pip install -e .
```

# Download model files

```
# text encoder (required)
wget https://dall-3.com/models/glid-3-xl/bert.pt

# ldm first stage (required)
wget https://dall-3.com/models/glid-3-xl/kl-f8.pt

# there are several diffusion models to choose from:

# original diffusion model from CompVis
wget https://dall-3.com/models/glid-3-xl/diffusion.pt

# new model fine tuned on a cleaner dataset (will not generate watermarks, split images or blurry images)
wget https://dall-3.com/models/glid-3-xl/finetune.pt

```

# Generating images
note: best results at 256x256 image size

```
# fast PLMS sampling
python sample.py --model_path finetune.pt --batch_size 6 --num_batches 6 --text "a cyberpunk girl with a scifi neuralink device on her head"

# classifier free guidance + CLIP guidance (better adherence to prompt, much slower)
python sample.py --clip_guidance --model_path finetune.pt --batch_size 1 --num_batches 12 --text "a cyberpunk girl with a scifi neuralink device on her head | trending on artstation"

# sample with an init image
python sample.py --init_image picture.jpg --skip_timesteps 10 --model_path finetune.pt --batch_size 6 --num_batches 6 --text "a cyberpunk girl with a scifi neuralink device on her head"

# generated images saved to ./output/
# generated image embeddings saved to ./output_npy/ as npy files
```

# Training/Fine tuning
Train with same flags as guided diffusion. Data directory should contain image and text files with the same name (image1.png image1.txt)

```
# not possible to train on 24gb vram currently!
MODEL_FLAGS="--ema_rate 0.9999 --attention_resolutions 32,16,8 --class_cond False --diffusion_steps 1000 --image_size 32 --learn_sigma False --noise_schedule linear --num_channels 320 --num_heads 8 --num_res_blocks 2 --resblock_updown False --use_fp16 True --use_scale_shift_norm False"
TRAIN_FLAGS="--lr 1e-5 --batch_size 1 --log_interval 1 --save_interval 5000 --kl_model kl-f8.pt --bert_model bert.pt --resume_checkpoint diffusion.pt"
export OPENAI_LOGDIR=./logs/
export TOKENIZERS_PARALLELISM=false
python scripts/image_train_latent.py --data_dir /path/to/data $MODEL_FLAGS $TRAIN_FLAGS
```

Train for inpainting
```
# batch size > 1 required
MODEL_FLAGS="--dropout 0.1 --ema_rate 0.9999 --attention_resolutions 32,16,8 --class_cond False --diffusion_steps 1000 --image_size 32 --learn_sigma False --noise_schedule linear --num_channels 320 --num_heads 8 --num_res_blocks 2 --resblock_updown False --use_fp16 True --use_scale_shift_norm False"
TRAIN_FLAGS="--lr 1e-5 --batch_size 2 --log_interval 1 --save_interval 5000 --kl_model kl-f8.pt --bert_model bert.pt --resume_checkpoint diffusion.pt"
export OPENAI_LOGDIR=./logs/
export TOKENIZERS_PARALLELISM=false
python scripts/image_train_inpaint.py --data_dir /path/to/data $MODEL_FLAGS $TRAIN_FLAGS
```