from __future__ import annotations

try:
    from model_fn import model_fn
    from input_fn import input_fn
    from predict_fn import predict_fn
    from output_fn import output_fn
except ImportError:
    from .model_fn import model_fn
    from .input_fn import input_fn
    from .predict_fn import predict_fn
    from .output_fn import output_fn

__all__ = ["model_fn", "input_fn", "predict_fn", "output_fn"]
