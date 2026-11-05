import joblib
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
        if path.suffix == '.pkl':
            model = joblib.load(path)
            logger.info(f"Loaded Ensemble Model: {path.name}")
        elif path.suffix == '.json':
            model = xgb.XGBClassifier()
            model.load_model(path)
            logger.info(f"Loaded XGBoost Model: {path.name}")
        else:
            return None

        _cache[path_str] = model
        return model

    except Exception as e:
        logger.error(f"Error loading model {path.name}: {e}")
        return None
