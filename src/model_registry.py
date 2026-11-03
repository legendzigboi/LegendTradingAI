import logging
from pathlib import Path
from src.xgb_pure import XGBPure

logger = logging.getLogger(__name__)

# This dictionary stores the models in RAM
_MODEL_CACHE = {}

def get_model(model_path: Path):
    """Loads model from disk ONCE, then serves it from RAM."""
    path_str = str(model_path)
    
    if path_str in _MODEL_CACHE:
        return _MODEL_CACHE[path_str]
        
    if not model_path.exists():
        return None
        
    try:
        logger.info(f"Loading model into cache: {model_path.name}")
        model = XGBPure(model_path)
        _MODEL_CACHE[path_str] = model
        return model
    except Exception as e:
        logger.error(f"Failed to load model {path_str}: {e}")
        return None
