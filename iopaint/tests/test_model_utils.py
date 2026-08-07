import torch

from diffusers.pipelines.stable_diffusion.safety_checker import (
    StableDiffusionSafetyChecker,
)
from transformers import CLIPImageProcessor

from iopaint.model.utils import get_sd_safety_checker_components


def test_enabled_safety_checker_components_are_attached(monkeypatch):
    checker = object()
    feature_extractor = object()
    calls = {}

    def load_checker(*args, **kwargs):
        calls["checker"] = kwargs
        return checker

    def load_feature_extractor(*args, **kwargs):
        calls["feature_extractor"] = kwargs
        return feature_extractor

    monkeypatch.setattr(
        StableDiffusionSafetyChecker, "from_pretrained", load_checker
    )
    monkeypatch.setattr(
        CLIPImageProcessor, "from_pretrained", load_feature_extractor
    )

    components = get_sd_safety_checker_components(
        torch.float32, local_files_only=True
    )

    assert components["safety_checker"] is checker
    assert components["feature_extractor"] is feature_extractor
    assert components["requires_safety_checker"] is True
    assert calls["checker"]["dtype"] is torch.float32
    assert calls["checker"]["local_files_only"] is True
    assert calls["feature_extractor"]["local_files_only"] is True
