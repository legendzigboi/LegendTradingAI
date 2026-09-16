"""
Pure Python XGBoost inference.

Loads an XGBoost .json model and predicts without xgboost or numpy.
Works on Termux / any minimal Python environment.

XGBoost JSON structure (per tree):
  - left_children[i]   : left child index (or -1 for leaf)
  - right_children[i]  : right child index
  - split_indices[i]   : feature index used at node i
  - split_conditions[i]: threshold value at node i
  - default_left[i]    : 1 if missing goes left
  - split_conditions[i]: also used at leaf nodes as the leaf value

For binary:logistic, final output = sigmoid(sum_of_leaf_values + base_score_logit)
"""

import json
import math
from pathlib import Path


class XGBPure:
    def __init__(self, model_path):
        with open(model_path, "r") as f:
            model = json.load(f)

        learner = model["learner"]
        gb = learner["gradient_booster"]["model"]

        self.trees = gb["trees"]
        self.feature_names = learner["feature_names"]

        # ---- base_score can be: "0.5", "4.88e-1", or "[4.88e-1]" (XGBoost 2.x) ----
        _bs = learner["learner_model_param"]["base_score"]
        if isinstance(_bs, str):
            _bs = _bs.strip().strip("[]")
        self.base_score = float(_bs)

        # objective
        self.objective = learner["objective"]["name"]
        if self.objective != "binary:logistic":
            raise ValueError(f"Unsupported objective: {self.objective}")

        # base_score is in probability space; convert to logit (margin space)
        # sigmoid(x) = base_score  =>  x = log(base_score / (1 - base_score))
        eps = 1e-7
        b = min(max(self.base_score, eps), 1.0 - eps)
        self.base_margin = math.log(b / (1.0 - b))

    def _traverse_tree(self, tree, features):
        """Return the leaf value for one tree."""
        left = tree["left_children"]
        right = tree["right_children"]
        split_idx = tree["split_indices"]
        split_cond = tree["split_conditions"]
        default_left = tree["default_left"]

        node = 0
        while left[node] != -1:
            f_idx = split_idx[node]
            f_val = features[f_idx]
            threshold = split_cond[node]

            if f_val is None:
                node = left[node] if default_left[node] else right[node]
            elif isinstance(f_val, float) and math.isnan(f_val):
                node = left[node] if default_left[node] else right[node]
            elif f_val < threshold:
                node = left[node]
            else:
                node = right[node]

        return split_cond[node]  # leaf value

    def predict_proba(self, X):
        """
        X: list of feature rows (each row is a list of floats).
        Returns: list of P(class=1) probabilities.
        """
        probs = []
        for row in X:
            margin = self.base_margin
            for tree in self.trees:
                margin += self._traverse_tree(tree, row)
            p = 1.0 / (1.0 + math.exp(-margin))
            probs.append(p)
        return probs

    def predict(self, X, threshold=0.5):
        return [1 if p >= threshold else 0 for p in self.predict_proba(X)]


# ---- Self-test ----
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m src.xgb_pure <model.json>")
        sys.exit(1)

    m = XGBPure(sys.argv[1])
    print(f"✅ Loaded: {sys.argv[1]}")
    print(f"   Trees:        {len(m.trees)}")
    print(f"   Features:     {len(m.feature_names)}")
    print(f"   Base score:   {m.base_score:.6f}")
    print(f"   Base margin:  {m.base_margin:.6f}")

    n_feat = len(m.feature_names)
    X = [[0.0] * n_feat]
    p = m.predict_proba(X)[0]
    print(f"   Test pred (all zeros): {p:.6f}")
