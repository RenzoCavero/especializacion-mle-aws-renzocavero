"""Inference entrypoint re-exporting training inference functions."""

from training.inference import input_fn, model_fn, output_fn, predict_fn

__all__ = ["model_fn", "input_fn", "predict_fn", "output_fn"]

