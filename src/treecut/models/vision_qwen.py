"""CUDA-only Qwen3-VL adapter with local-files-only loading."""
from __future__ import annotations

from pathlib import Path


class QwenVision:
    def __init__(self, model_dir: Path):
        shards = list(model_dir.glob("model-*.safetensors"))
        if len(shards) < 2 or not (model_dir / "config.json").is_file():
            raise FileNotFoundError(f"Qwen3-VL 模型不完整：{model_dir}")
        import torch
        if not torch.cuda.is_available():
            raise RuntimeError("Qwen3-VL FP8 仅在 NVIDIA CUDA 环境启用")
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

        self.torch = torch
        self.processor = AutoProcessor.from_pretrained(
            str(model_dir), trust_remote_code=True, local_files_only=True,
        )
        self.model = Qwen3VLForConditionalGeneration.from_pretrained(
            str(model_dir), trust_remote_code=True, local_files_only=True,
            torch_dtype="auto", low_cpu_mem_usage=True,
        ).to("cuda").eval()

    def caption_many(self, image_paths: list[Path]) -> list[str]:
        from PIL import Image

        captions = []
        for image_path in image_paths:
            with Image.open(image_path) as source:
                image = source.convert("RGB")
            try:
                messages = [{"role": "user", "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": "Describe this video frame accurately and concisely."},
                ]}]
                prompt = self.processor.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True,
                )
                inputs = self.processor(text=[prompt], images=[image], return_tensors="pt")
                inputs = {name: value.to(self.model.device) for name, value in inputs.items()}
                with self.torch.inference_mode():
                    output = self.model.generate(**inputs, max_new_tokens=96, do_sample=False)
                generated = output[:, inputs["input_ids"].shape[1]:]
                caption = self.processor.batch_decode(generated, skip_special_tokens=True)[0].strip()
                if not caption:
                    raise RuntimeError(f"Qwen3-VL 没有返回画面描述：{image_path}")
                captions.append(caption)
            finally:
                image.close()
        return captions
