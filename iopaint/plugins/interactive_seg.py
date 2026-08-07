import hashlib
from typing import List

import numpy as np
import torch
from huggingface_hub.errors import GatedRepoError
from loguru import logger
from transformers import Sam3Model, Sam3Processor, Sam3TrackerModel, Sam3TrackerProcessor

from iopaint.helper import download_model
from iopaint.plugins.base_plugin import BasePlugin
from iopaint.plugins.segment_anything import SamPredictor, sam_model_registry
from iopaint.plugins.segment_anything.predictor_hq import SamHQPredictor
from iopaint.plugins.segment_anything2.build_sam import build_sam2
from iopaint.plugins.segment_anything2.sam2_image_predictor import SAM2ImagePredictor
from iopaint.schema import RunPluginRequest

# 从小到大
SEGMENT_ANYTHING_MODELS = {
    "vit_b": {
        "url": "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth",
        "md5": "01ec64d29a2fca3f0661936605ae66f8",
    },
    "vit_l": {
        "url": "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_l_0b3195.pth",
        "md5": "0b3195507c641ddb6910d2bb5adee89c",
    },
    "vit_h": {
        "url": "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth",
        "md5": "4b8939a88964f0f4ff5f5b2642c598a6",
    },
    "mobile_sam": {
        "url": "https://github.com/Sanster/models/releases/download/MobileSAM/mobile_sam.pt",
        "md5": "f3c0d8cda613564d499310dab6c812cd",
    },
    "sam_hq_vit_b": {
        "url": "https://huggingface.co/lkeab/hq-sam/resolve/main/sam_hq_vit_b.pth",
        "md5": "c6b8953247bcfdc8bb8ef91e36a6cacc",
    },
    "sam_hq_vit_l": {
        "url": "https://huggingface.co/lkeab/hq-sam/resolve/main/sam_hq_vit_l.pth",
        "md5": "08947267966e4264fb39523eccc33f86",
    },
    "sam_hq_vit_h": {
        "url": "https://huggingface.co/lkeab/hq-sam/resolve/main/sam_hq_vit_h.pth",
        "md5": "3560f6b6a5a6edacd814a1325c39640a",
    },
    "sam2_tiny": {
        "url": "https://dl.fbaipublicfiles.com/segment_anything_2/072824/sam2_hiera_tiny.pt",
        "md5": "99eacccce4ada0b35153d4fd7af05297",
    },
    "sam2_small": {
        "url": "https://dl.fbaipublicfiles.com/segment_anything_2/072824/sam2_hiera_small.pt",
        "md5": "7f320dbeb497330a2472da5a16c7324d",
    },
    "sam2_base": {
        "url": "https://dl.fbaipublicfiles.com/segment_anything_2/072824/sam2_hiera_base_plus.pt",
        "md5": "09dc5a3d7719f64aaea1d37341ef26f2",
    },
    "sam2_large": {
        "url": "https://dl.fbaipublicfiles.com/segment_anything_2/072824/sam2_hiera_large.pt",
        "md5": "08083462423be3260cd6a5eef94dc01c",
    },
    "sam2_1_tiny": {
        "url": "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_tiny.pt",
        "md5": "6aa6761c9da74fbaa74b4c790a0a2007",
    },
    "sam2_1_small": {
        "url": "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_small.pt",
        "md5": "51713b3d1994696d27f35f9c6de6f5ef",
    },
    "sam2_1_base": {
        "url": "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_base_plus.pt",
        "md5": "ec7bd7d23d280d5e3cfa45984c02eda5",
    },
    "sam2_1_large": {
        "url": "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_large.pt",
        "md5": "2b30654b6112c42a115563c638d238d9",
    },
}

# facebook/sam3.1 ships only a raw multiplex checkpoint incompatible with
# Transformers as of 2026-08, so it is intentionally not offered here.
SAM3_MODELS = {"sam3": "facebook/sam3"}


def _raise_sam3_access_error(error: BaseException, repo_id: str):
    current = error
    seen = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, GatedRepoError):
            raise RuntimeError(
                f"{repo_id} is gated. Accept its license on Hugging Face, then run "
                "`hf auth login` and retry."
            ) from error
        current = current.__cause__ or current.__context__


class InteractiveSeg(BasePlugin):
    name = "InteractiveSeg"
    support_gen_mask = True

    def __init__(self, model_name, device):
        super().__init__()
        self.model_name = model_name
        self.device = device
        self._init_session(model_name)

    def _init_session(self, model_name: str):
        self.predictor = None
        self.sam3_tracker = None
        self.sam3_tracker_processor = None
        self.sam3_image_embeddings = None
        self.sam3_original_sizes = None
        self.sam3_model = None
        self.sam3_processor = None

        if model_name.startswith("sam3"):
            self.sam3_repo_id = SAM3_MODELS[model_name]
            try:
                self.sam3_tracker_processor = Sam3TrackerProcessor.from_pretrained(
                    self.sam3_repo_id
                )
                self.sam3_tracker = Sam3TrackerModel.from_pretrained(
                    self.sam3_repo_id, dtype=torch.float32
                ).to(self.device)
                self.sam3_tracker.eval()
            except Exception as error:
                _raise_sam3_access_error(error, self.sam3_repo_id)
                raise
            self.prev_img_md5 = None
            return

        model_path = download_model(
            SEGMENT_ANYTHING_MODELS[model_name]["url"],
            SEGMENT_ANYTHING_MODELS[model_name]["md5"],
        )
        logger.info(f"SegmentAnything model path: {model_path}")
        if "sam_hq" in model_name:
            self.predictor = SamHQPredictor(
                sam_model_registry[model_name](checkpoint=model_path).to(self.device)
            )
        elif model_name.startswith("sam2"):
            sam2_model = build_sam2(
                model_name, ckpt_path=model_path, device=self.device
            )
            self.predictor = SAM2ImagePredictor(sam2_model)
        else:
            self.predictor = SamPredictor(
                sam_model_registry[model_name](checkpoint=model_path).to(self.device)
            )
        self.prev_img_md5 = None

    def switch_model(self, new_model_name):
        if self.model_name == new_model_name:
            return

        logger.info(
            f"Switching InteractiveSeg model from {self.model_name} to {new_model_name}"
        )
        self._init_session(new_model_name)
        self.model_name = new_model_name

    def gen_mask(self, rgb_np_img, req: RunPluginRequest) -> np.ndarray:
        img_md5 = hashlib.md5(req.image.encode("utf-8")).hexdigest()
        return self.forward(rgb_np_img, req.clicks, img_md5)

    @torch.inference_mode()
    def forward(self, rgb_np_img, clicks: List[List], img_md5: str):
        input_point = []
        input_label = []
        for click in clicks:
            x = click[0]
            y = click[1]
            input_point.append([x, y])
            input_label.append(click[2])

        if self.model_name.startswith("sam3"):
            if img_md5 and img_md5 != self.prev_img_md5:
                image_inputs = self.sam3_tracker_processor(
                    images=rgb_np_img, return_tensors="pt"
                )
                pixel_values = image_inputs["pixel_values"].to(
                    device=self.device, dtype=torch.float32
                )
                self.sam3_image_embeddings = self.sam3_tracker.get_image_embeddings(
                    pixel_values
                )
                self.sam3_original_sizes = image_inputs["original_sizes"]
                self.prev_img_md5 = img_md5

            prompt_inputs = self.sam3_tracker_processor(
                original_sizes=self.sam3_original_sizes,
                input_points=[[input_point]],
                input_labels=[[input_label]],
                return_tensors="pt",
            )
            outputs = self.sam3_tracker(
                image_embeddings=self.sam3_image_embeddings,
                input_points=prompt_inputs["input_points"].to(self.device),
                input_labels=prompt_inputs["input_labels"].to(self.device),
                multimask_output=False,
            )
            masks = self.sam3_tracker_processor.post_process_masks(
                outputs.pred_masks, prompt_inputs["original_sizes"]
            )
            return masks[0][0][0].cpu().numpy().astype(np.uint8) * 255

        if img_md5 and img_md5 != self.prev_img_md5:
            self.prev_img_md5 = img_md5
            self.predictor.set_image(rgb_np_img)

        masks, _, _ = self.predictor.predict(
            point_coords=np.array(input_point),
            point_labels=np.array(input_label),
            multimask_output=False,
        )
        mask = masks[0].astype(np.uint8) * 255
        return mask

    @torch.inference_mode()
    def gen_mask_by_text(
        self, rgb_np_img: np.ndarray, prompt: str, score_threshold: float
    ) -> np.ndarray:
        if not self.model_name.startswith("sam3"):
            raise ValueError("Text segmentation requires the sam3 model")

        if self.sam3_model is None:
            try:
                self.sam3_processor = Sam3Processor.from_pretrained(self.sam3_repo_id)
                self.sam3_model = Sam3Model.from_pretrained(
                    self.sam3_repo_id, dtype=torch.float32
                ).to(self.device)
                self.sam3_model.eval()
            except Exception as error:
                _raise_sam3_access_error(error, self.sam3_repo_id)
                raise

        inputs = self.sam3_processor(
            images=rgb_np_img, text=prompt, return_tensors="pt"
        )
        outputs = self.sam3_model(
            pixel_values=inputs["pixel_values"].to(
                device=self.device, dtype=torch.float32
            ),
            input_ids=inputs["input_ids"].to(self.device),
            attention_mask=inputs["attention_mask"].to(self.device),
        )
        result = self.sam3_processor.post_process_instance_segmentation(
            outputs,
            threshold=score_threshold,
            target_sizes=[rgb_np_img.shape[:2]],
        )[0]
        if len(result["masks"]) == 0:
            return np.zeros(rgb_np_img.shape[:2], dtype=np.uint8)
        return (
            result["masks"].bool().any(dim=0).cpu().numpy().astype(np.uint8) * 255
        )
