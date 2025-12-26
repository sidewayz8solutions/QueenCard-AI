import runpod
from inference import run_inference
from video_inference import run_video_inference

def handler(event):
    """
    This function is called by RunPod.
    `event['input']` is the payload from FastAPI /dispatch.

    Supports:
    - img2img: Image to image generation with SD 1.5
    - img2vid: Image to video generation with Wan 2.1
    - txt2vid: Text to video generation with Wan 2.1
    """
    try:
        payload = event["input"]

        job_id = payload["job_id"]
        user_id = payload["user_id"]
        input_keys = payload.get("input_keys", [])
        output_prefix = payload["output_prefix"]
        job_type = payload.get("job_type", "img2img")
        model_name = payload.get("model_name", "realistic-vision-v5")
        lora_names = payload.get("lora_names", [])
        prompt = payload.get("prompt", "")

        # Build params dict
        params = payload.get("params", {})
        params["prompt"] = prompt
        params["lora_names"] = lora_names  # Pass LoRAs to video inference too

        print(f"Processing {job_type} job {job_id} for user {user_id}")
        print(f"Model: {model_name}, LoRAs: {lora_names}")
        print(f"Prompt: {prompt}")
        print(f"Input keys: {input_keys}")

        if job_type in ["img2vid", "txt2vid"]:
            # Video generation with Wan 2.1
            # For txt2vid, input_keys should be empty
            results = run_video_inference(
                job_id=job_id,
                user_id=user_id,
                input_keys=input_keys if job_type == "img2vid" else [],
                output_prefix=output_prefix,
                params=params,
            )
        else:
            # Default: Image to image with SD 1.5
            results = run_inference(
                job_id=job_id,
                user_id=user_id,
                input_keys=input_keys,
                output_prefix=output_prefix,
                model_name=model_name,
                lora_names=lora_names,
                params=params,
            )

        print(f"Job {job_id} completed with {len(results)} outputs")

        return {
            "status": "completed",
            "job_id": job_id,
            "job_type": job_type,
            "outputs": results
        }
    except Exception as e:
        print(f"Error processing job: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "status": "failed",
            "error": str(e)
        }

runpod.serverless.start({"handler": handler})

