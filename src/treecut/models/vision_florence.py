"""CPU-safe local Florence adapter used when CUDA is unavailable."""
from __future__ import annotations

from pathlib import Path


class FlorenceVision:
    def __init__(self, model_dir: Path):
        if not (model_dir / "model.safetensors").is_file():
            raise FileNotFoundError(f"Florence 模型不完整：{model_dir}")
        import torch
        from transformers import AutoModelForCausalLM, AutoProcessor

        self.torch = torch
        self.processor = AutoProcessor.from_pretrained(
            str(model_dir), trust_remote_code=True, local_files_only=True,
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            str(model_dir), trust_remote_code=True, local_files_only=True,
            dtype=torch.float32, attn_implementation="eager",
        ).eval()

    def caption(self, image_path: Path) -> str:
        return self.caption_many([image_path])[0]

    def caption_many(self, image_paths: list[Path]) -> list[str]:
        if not image_paths:
            return []
        from PIL import Image

        task = "<MORE_DETAILED_CAPTION>"
        images = []
        for image_path in image_paths:
            with Image.open(image_path) as source:
                images.append(source.convert("RGB"))
        try:
            inputs = self.processor(
                text=[task] * len(images), images=images, return_tensors="pt", padding=True,
            )
            with self.torch.inference_mode():
                output = self.model.generate(
                    input_ids=inputs["input_ids"], pixel_values=inputs["pixel_values"],
                    max_new_tokens=96, num_beams=1, do_sample=False, use_cache=False,
                )
            raw_outputs = self.processor.batch_decode(output, skip_special_tokens=False)
            captions = []
            for raw, image, image_path in zip(raw_outputs, images, image_paths):
                parsed = self.processor.post_process_generation(raw, task=task, image_size=image.size)
                caption = str(parsed.get(task, raw)).replace("<pad>", "").strip()
                if not caption:
                    raise RuntimeError(f"Florence 没有返回画面描述：{image_path}")
                captions.append(caption)
            return captions
        finally:
            for image in images:
                image.close()

    def detect(self, image_path: Path) -> list[dict]:
        """Run Florence's native object-detection task without a second model runtime."""
        from PIL import Image

        task = "<OD>"
        with Image.open(image_path) as source:
            image = source.convert("RGB")
        try:
            inputs = self.processor(text=task, images=image, return_tensors="pt")
            with self.torch.inference_mode():
                output = self.model.generate(
                    input_ids=inputs["input_ids"],
                    pixel_values=inputs["pixel_values"],
                    max_new_tokens=256,
                    num_beams=1,
                    do_sample=False,
                    use_cache=False,
                )
            raw = self.processor.batch_decode(output, skip_special_tokens=False)[0]
            parsed = self.processor.post_process_generation(raw, task=task, image_size=image.size)
            result = parsed.get(task) or {}
            boxes = result.get("bboxes") or result.get("boxes") or []
            labels = result.get("labels") or []
            return [
                {
                    "class": str(label).strip().lower(),
                    "confidence": 1.0,
                    "box_xyxy": [round(float(value), 1) for value in box],
                }
                for box, label in zip(boxes, labels)
                if str(label).strip()
            ]
        finally:
            image.close()


SCREEN_OR_SENSITIVE_PHRASES = {
    "screenshot", "screen recording", "mobile phone screen", "phone interface",
    "app interface", "chat screen", "bank account", "account balance",
    "transaction record", "transaction details", "payment details", "credit card",
    "calendar screen", "截图", "录屏", "手机界面", "应用界面", "聊天界面",
    "银行账户", "银行卡", "账户余额", "交易记录", "交易明细", "支付页面",
    "付款码", "收款码", "信用卡", "身份证", "手机号码",
}


def assess_captions(captions: list[str]) -> dict:
    normalized = " ".join(captions).lower()
    matches = sorted(phrase for phrase in SCREEN_OR_SENSITIVE_PHRASES if phrase in normalized)
    return {
        "screen_or_sensitive": bool(matches),
        "matched_risk_words": matches,
        "needs_review": bool(matches),
    }


CAPTION_CATEGORY_WORDS = {
    "factory_production": {"factory", "workshop", "warehouse", "industrial", "manufacturing", "machine"},
    "installation": {"installing", "installation", "worker", "construction", "assembling", "tools"},
    "talking_head": {"speaking", "talking", "microphone", "presenter", "interview"},
    "customer_case": {"customer", "homeowner", "completed project", "finished home"},
    "interior_space": {"kitchen", "living room", "dining", "apartment", "home", "interior", "room"},
    "product_display": {"cabinet", "countertop", "island", "product", "drawer", "table", "storage"},
}


def classify_captions(captions: list[str]) -> dict:
    text = " ".join(captions).lower()
    matches = {
        category: sorted(word for word in words if word in text)
        for category, words in CAPTION_CATEGORY_WORDS.items()
    }
    category, words = max(matches.items(), key=lambda item: len(item[1]))
    if not words:
        return {"category": "unclassified", "confidence": 0.0, "matched_words": []}
    confidence = min(0.85, 0.35 + 0.1 * len(words))
    return {"category": category, "confidence": confidence, "matched_words": words}
