from __future__ import annotations

try:
    from input_fn import input_fn
    from model_fn import model_fn
    from output_fn import output_fn
    from predict_fn import predict_fn
except ImportError:
    from .input_fn import input_fn
    from .model_fn import model_fn
    from .output_fn import output_fn
    from .predict_fn import predict_fn

__all__ = ["model_fn", "input_fn", "predict_fn", "output_fn"]
