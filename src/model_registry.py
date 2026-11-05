import xgboost as xgb
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
_cache = {}

def get_model(model_path):
    path = Path(model_path)
    path_str = str(path)

    if path_str in _cache:
        return _cache[path_str]

    if not path.exists():
        return None

    try:
        model = xgb.XGBClassifier()
        model.load_model(path)
        _cache[path_str] = model
        return model
    except Exception as e:
        logger.error(f"Error loading model {path.name}: {e}")
        return None
