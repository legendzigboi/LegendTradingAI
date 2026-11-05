import joblib
import xgboost as xgb
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
_cache = {}
_error_cache = {} # Store errors so we can read them

def get_model(model_path):
    path = Path(model_path)
    path_str = str(path)

    if path_str in _cache:
        return _cache[path_str]
    if path_str in _error_cache:
        return None

    if not path.exists():
        _error_cache[path_str] = f"FileNotFound: {path.name}"
        return None

    try:
        if path.suffix == '.pkl':
            model = joblib.load(path)
        elif path.suffix == '.json':
            model = xgb.XGBClassifier()
            model.load_model(path)
        else:
            _error_cache[path_str] = "Unknown extension"
            return None

        _cache[path_str] = model
        return model

    except Exception as e:
        err_msg = str(e)
        logger.error(f"Error loading model {path.name}: {err_msg}")
        _error_cache[path_str] = f"LoadError: {err_msg[:30]}"
        return None

def get_model_error(path):
    return _error_cache.get(str(path), "Unknown error")
