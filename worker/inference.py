"""
Stable Diffusion 1.5 Image-to-Image inference.

For NSFW image generation with LoRA support.
"""
import uuid
import os
import gc
import torch
from PIL import Image
from r2_client import download, upload

# Global pipeline cache
_pipeline = None
_current_model = None
_loaded_loras = []

# Model mapping - NSFW-capable SD 1.5 models
MODELS = {
    "realistic-vision-v5": "SG161222/Realistic_Vision_V5.1_noVAE",
    "dreamshaper-8": "Lykon/DreamShaper",
    "deliberate-v3": "XpucT/Deliberate",
    # Add more NSFW-capable models as needed
}

# LoRA registry - store LoRAs in R2
LORA_REGISTRY = {
    # "lora-name": "r2-key-to-lora.safetensors"
}


def clear_memory():
    """Clear GPU memory."""
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def get_pipeline(model_name: str, lora_names: list = None):
    """Load or reuse the Stable Diffusion pipeline with optional LoRAs."""
    global _pipeline, _current_model, _loaded_loras

    from diffusers import StableDiffusionImg2ImgPipeline, DPMSolverMultistepScheduler

    lora_names = lora_names or []
    model_id = MODELS.get(model_name, MODELS["realistic-vision-v5"])

    # Check if we need to reload the model
    if _pipeline is None or _current_model != model_id:
        print(f"Loading model: {model_id}")

        # Clear existing pipeline
        if _pipeline is not None:
            del _pipeline
            clear_memory()

        _pipeline = StableDiffusionImg2ImgPipeline.from_pretrained(
            model_id,
            torch_dtype=torch.float16,
            safety_checker=None,
            requires_safety_checker=False,
        )

        # Use DPM++ scheduler for better quality
        _pipeline.scheduler = DPMSolverMultistepScheduler.from_config(
            _pipeline.scheduler.config
        )

        _pipeline = _pipeline.to("cuda")

        # Try to enable memory efficient attention
        try:
            _pipeline.enable_xformers_memory_efficient_attention()
        except Exception as e:
            print(f"xformers not available: {e}")
            # Fall back to sliced attention
            _pipeline.enable_attention_slicing()

        _current_model = model_id
        _loaded_loras = []

    # Handle LoRAs
    loras_to_load = [l for l in lora_names if l not in _loaded_loras]

    for lora_name in loras_to_load:
        if lora_name in LORA_REGISTRY:
            lora_r2_key = LORA_REGISTRY[lora_name]
            print(f"Loading LoRA: {lora_name}")

            # Download LoRA from R2
            local_lora = f"/tmp/loras/{lora_name}.safetensors"
            os.makedirs("/tmp/loras", exist_ok=True)
            download(lora_r2_key, local_lora)

            _pipeline.load_lora_weights(local_lora, adapter_name=lora_name)
            _loaded_loras.append(lora_name)
        else:
            print(f"Warning: LoRA '{lora_name}' not found in registry")

    # Activate all loaded LoRAs
    if _loaded_loras:
        _pipeline.set_adapters(_loaded_loras)

    return _pipeline


def run_inference(
    job_id,
    user_id,
    input_keys,
    output_prefix,
    model_name,
    lora_names,
    params,
):
    """Run img2img inference on input images."""
    outputs = []

    # Get parameters with defaults
    prompt = params.get("prompt", "")
    negative_prompt = params.get("negative_prompt", "blurry, low quality, distorted")
    strength = params.get("strength", 0.75)
    guidance_scale = params.get("guidance_scale", 7.5)
    num_inference_steps = params.get("num_inference_steps", 30)
    seed = params.get("seed", None)

    # Get the pipeline
    pipe = get_pipeline(model_name, lora_names)

    # Set up generator for reproducibility
    generator = None
    if seed is not None:
        generator = torch.Generator(device="cuda").manual_seed(seed)

    for key in input_keys:
        local_input = f"/tmp/{uuid.uuid4()}.png"
        local_output = f"/tmp/{uuid.uuid4()}.png"

        # Download input image
        download(key, local_input)

        # Load and prepare image
        init_image = Image.open(local_input).convert("RGB")

        # Resize to multiple of 8 (required by SD)
        width, height = init_image.size
        width = (width // 8) * 8
        height = (height // 8) * 8
        init_image = init_image.resize((width, height), Image.LANCZOS)

        # Run inference
        result = pipe(
            prompt=prompt,
            negative_prompt=negative_prompt,
            image=init_image,
            strength=strength,
            guidance_scale=guidance_scale,
            num_inference_steps=num_inference_steps,
            generator=generator,
        )

        # Save output
        output_image = result.images[0]
        output_image.save(local_output, "PNG")

        # Upload to R2
        output_key = f"{output_prefix}{uuid.uuid4()}.png"
        upload(local_output, output_key)

        outputs.append({"key": output_key})

        # Cleanup
        os.remove(local_input)
        os.remove(local_output)

    return outputs

