import os
import joblib
import numpy as np
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
from tensorflow.keras.models import load_model

def to_number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return value

class Model:
    def __init__(
        self,
        name,
        model_path,
        input_keys,
        output_key,
        output_topic,
        feature_names_path=None,
        scaler_path=None,
        input_label_encoder_path=None,
        input_label_col=None,
        one_hot_configs=None,
        window_size=0,
        output_scaler_path=None,
        output_encoder_path=None,
        needs_argmax=False,
        is_anomaly_model=False
    ):
        self.name = name
        self.model_path = model_path
        self.input_keys = input_keys
        self.output_key = output_key
        self.output_topic = output_topic

        self.feature_names_path = feature_names_path
        self.scaler_path = scaler_path
        self.input_label_encoder_path = input_label_encoder_path
        self.input_label_col = input_label_col
        self.one_hot_configs = one_hot_configs or {}
        self.window_size = window_size
        self.output_scaler_path = output_scaler_path
        self.output_encoder_path = output_encoder_path
        self.needs_argmax = needs_argmax
        self.is_anomaly_model = is_anomaly_model

        self.is_keras = self.model_path.endswith(('.keras', '.h5'))

        self.model = None
        self.feature_names = None
        self.scaler = None
        self.input_label_encoder = None
        self.output_scaler = None
        self.output_encoder = None
        self.history = []

    def load(self, base_dir="."):
        if self.is_keras:
            self.model = load_model(os.path.join(base_dir, self.model_path))
        else:
            self.model = joblib.load(os.path.join(base_dir, self.model_path))

        if self.feature_names_path:
            self.feature_names = joblib.load(os.path.join(base_dir, self.feature_names_path))
        if self.scaler_path:
            self.scaler = joblib.load(os.path.join(base_dir, self.scaler_path))
        if self.input_label_encoder_path:
            self.input_label_encoder = joblib.load(os.path.join(base_dir, self.input_label_encoder_path))
        if self.output_scaler_path:
            self.output_scaler = joblib.load(os.path.join(base_dir, self.output_scaler_path))
        if self.output_encoder_path:
            self.output_encoder = joblib.load(os.path.join(base_dir, self.output_encoder_path))

        print(f"[MODEL] Loaded: {self.name}")

    def predict(self, values):
        features_dict = {}
        for k in self.input_keys:
            val = values.get(k, 0.0)
            
            if k == self.input_label_col and self.input_label_encoder:
                val = self.input_label_encoder.transform([val])[0]
            else:
                val = to_number(val)
                
            features_dict[k] = val

        for col, prefix in self.one_hot_configs.items():
            if col in values:
                one_hot_key = f"{prefix}{values[col]}"
                features_dict[one_hot_key] = 1.0

        if self.feature_names:
            raw_features = [features_dict.get(f, 0.0) for f in self.feature_names]
        else:
            raw_features = [features_dict[k] for k in self.input_keys]

        if self.scaler:
            X = self.scaler.transform([raw_features])
        else:
            X = np.array([raw_features])

        if self.window_size > 0:
            self.history.append(X[0])
            if len(self.history) > self.window_size:
                self.history.pop(0)
            if len(self.history) < self.window_size:
                raise ValueError(f"Pending Data Collection ({len(self.history)}/{self.window_size})")
            X = np.array([self.history], dtype="float32")

        if self.is_keras:
            pred_raw = self.model.predict(X, verbose=0)
        else:
            pred_raw = self.model.predict(X)

        if self.output_scaler:
            return float(self.output_scaler.inverse_transform(pred_raw)[0][0])

        if self.needs_argmax:
            pred_raw = [np.argmax(pred_raw, axis=1)[0]]

        if self.output_encoder:
            return self.output_encoder.inverse_transform(pred_raw)[0]

        if self.is_anomaly_model:
            return 1 if pred_raw[0] == -1 else 0

        return int(pred_raw[0])

def run_pipeline(models, values):
    for model in models:
        try:
            prediction = model.predict(values)
            values[model.output_key] = prediction
            print(f"[PIPELINE] {model.name} -> {model.output_key}={prediction}")
        except Exception as err:
            if "Pending" not in str(err):
                print(f"[PIPELINE] {model.name} skipped: {err}")
    return values