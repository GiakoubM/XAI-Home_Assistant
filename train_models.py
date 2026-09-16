"""
Train the 6-model stacked DAG on threat_smart_home_data.csv.

Algorithms (as specified):
  Occupancy            -> RandomForestClassifier
  Vibration Analysis    -> GradientBoostingClassifier
  Energy Consumption    -> LSTM (Keras, regression, sequence input)
  Activity Recognition  -> Neural Network (Keras Dense classifier)
  Anomaly Detection     -> IsolationForest (unsupervised)
  Threat Assessment     -> Neural Network (Keras Dense classifier)

"""

import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, IsolationForest
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, r2_score
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

tf.random.set_seed(42)
np.random.seed(42)

MODEL_DIR = "."
import os
os.makedirs(MODEL_DIR, exist_ok=True)

df = pd.read_csv("threat_smart_home_data.csv")
print(f"Loaded {len(df)} rows\n")

results = {}

# ===========================================================================
# 1. OCCUPANCY ESTIMATION MODEL  -- Random Forest (classifier)
# ===========================================================================
print("=" * 70)
print("1. OCCUPANCY ESTIMATION MODEL (Random Forest)")
print("=" * 70)

occ_features = ["temperature", "humidity", "co2", "light", "PIR"]
X = df[occ_features]
y = df["occupant_presence"]
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

occ_model = RandomForestClassifier(n_estimators=200, max_depth=10, random_state=42, n_jobs=-1)
occ_model.fit(X_train, y_train)
occ_acc = accuracy_score(y_test, occ_model.predict(X_test))
print(f"Accuracy: {occ_acc:.4f}")
results["Occupancy (RandomForest)"] = f"accuracy={occ_acc:.4f}"

joblib.dump(occ_model, f"{MODEL_DIR}/occupancy_random_forest.joblib")

# ===========================================================================
# 2. VIBRATION ANALYSIS MODEL -- Gradient Boosting (classifier, event_type)
# ===========================================================================
print("\n" + "=" * 70)
print("2. VIBRATION ANALYSIS MODEL (Gradient Boosting)")
print("=" * 70)

vib_features = [
    "vibration_rms", "peak_acceleration", "dominant_frequency", "spectral_energy",
    "spectral_entropy", "vibration_duration", "acceleration_x", "acceleration_y",
    "acceleration_z", "occupant_presence",
]
event_encoder = LabelEncoder()
y_event = event_encoder.fit_transform(df["event_type"])
X = df[vib_features]
X_train, X_test, y_train, y_test = train_test_split(X, y_event, test_size=0.2, random_state=42, stratify=y_event)

vib_model = GradientBoostingClassifier(n_estimators=150, max_depth=3, learning_rate=0.1, random_state=42)
vib_model.fit(X_train, y_train)
vib_acc = accuracy_score(y_test, vib_model.predict(X_test))
print(f"Accuracy: {vib_acc:.4f}  (classes: {list(event_encoder.classes_)})")
results["Vibration Analysis (GradientBoosting)"] = f"accuracy={vib_acc:.4f}"

joblib.dump(vib_model, f"{MODEL_DIR}/vibration_gradient_boosting.joblib")
joblib.dump(event_encoder, f"{MODEL_DIR}/event_type_encoder.joblib")

# ===========================================================================
# 3. ENERGY CONSUMPTION PREDICTION MODEL -- LSTM (regression, sequence input)
# ===========================================================================
print("\n" + "=" * 70)
print("3. ENERGY CONSUMPTION PREDICTION MODEL (LSTM)")
print("=" * 70)

energy_features = ["temperature", "humidity", "co2", "light", "occupant_presence"]
target_col = "cumulative energy"

WINDOW = 12  # use the past 11 hours PLUS the current hour's own readings
             # (the LSTM captures the temporal build-up, while the final step
             # in the window still carries "now"'s temperature/co2/occupancy)
feat_arr = df[energy_features].values.astype("float32")
target_arr = df[target_col].values.astype("float32")

X_seq, y_seq = [], []
for i in range(WINDOW - 1, len(df)):
    X_seq.append(feat_arr[i - WINDOW + 1:i + 1])
    y_seq.append(target_arr[i])
X_seq = np.array(X_seq)
y_seq = np.array(y_seq)

split = int(len(X_seq) * 0.8)
X_train, X_test = X_seq[:split], X_seq[split:]
y_train, y_test = y_seq[:split], y_seq[split:]

# scale features (fit on train only) — reshape for scaler then back to sequences
n_feat = len(energy_features)
scaler_x = StandardScaler().fit(X_train.reshape(-1, n_feat))
X_train_s = scaler_x.transform(X_train.reshape(-1, n_feat)).reshape(X_train.shape)
X_test_s = scaler_x.transform(X_test.reshape(-1, n_feat)).reshape(X_test.shape)

scaler_y = StandardScaler().fit(y_train.reshape(-1, 1))
y_train_s = scaler_y.transform(y_train.reshape(-1, 1)).ravel()
y_test_s = scaler_y.transform(y_test.reshape(-1, 1)).ravel()

energy_model = keras.Sequential([
    layers.Input(shape=(WINDOW, n_feat)),
    layers.LSTM(32, return_sequences=True),
    layers.LSTM(16),
    layers.Dense(16, activation="relu"),
    layers.Dense(1),
])
energy_model.compile(optimizer="adam", loss="mse")
energy_model.fit(X_train_s, y_train_s, epochs=20, batch_size=64, verbose=0,
                  validation_split=0.1)

y_pred_s = energy_model.predict(X_test_s, verbose=0).ravel()
y_pred = scaler_y.inverse_transform(y_pred_s.reshape(-1, 1)).ravel()
energy_r2 = r2_score(y_test, y_pred)
print(f"R2: {energy_r2:.4f}")
results["Energy Consumption (LSTM)"] = f"R2={energy_r2:.4f}"

energy_model.save(f"{MODEL_DIR}/energy_lstm.keras")
joblib.dump(scaler_x, f"{MODEL_DIR}/energy_scaler_x.joblib")
joblib.dump(scaler_y, f"{MODEL_DIR}/energy_scaler_y.joblib")

# generate a full-length "predicted_consumption" column (ground truth ffill for
# the first WINDOW rows that have no history) to feed downstream models
X_all_s = scaler_x.transform(feat_arr.reshape(-1, n_feat)).reshape(-1, n_feat)
full_seq = []
for i in range(WINDOW - 1, len(df)):
    full_seq.append(X_all_s[i - WINDOW + 1:i + 1])
full_seq = np.array(full_seq)
pred_all_s = energy_model.predict(full_seq, verbose=0).ravel()
pred_all = scaler_y.inverse_transform(pred_all_s.reshape(-1, 1)).ravel()
# first WINDOW-1 rows have no full history yet: fall back to ground truth
predicted_consumption = np.concatenate([target_arr[:WINDOW - 1], pred_all])
df["predicted_consumption"] = predicted_consumption

# ===========================================================================
# 4. ACTIVITY RECOGNITION MODEL -- Neural Network (Keras Dense classifier)
# ===========================================================================
print("\n" + "=" * 70)
print("4. ACTIVITY RECOGNITION MODEL (Neural Network)")
print("=" * 70)

har_num_features = ["occupant_count", "PIR", "outdoor_temperature", "light",
                     "predicted_consumption", "time_of_day"]
har_cat_feature = "event_type"

activity_encoder = LabelEncoder()
y_activity = activity_encoder.fit_transform(df["predicted_activity"])

event_dummies = pd.get_dummies(df[har_cat_feature], prefix="event")
door_state = df[["door_state"]].values
X_har = np.hstack([df[har_num_features].values, door_state, event_dummies.values]).astype("float32")
har_feature_names = har_num_features + ["door_state"] + list(event_dummies.columns)

X_train, X_test, y_train, y_test = train_test_split(
    X_har, y_activity, test_size=0.2, random_state=42, stratify=y_activity
)
har_scaler = StandardScaler().fit(X_train)
X_train_s = har_scaler.transform(X_train)
X_test_s = har_scaler.transform(X_test)

n_classes_har = len(activity_encoder.classes_)
har_model = keras.Sequential([
    layers.Input(shape=(X_train_s.shape[1],)),
    layers.Dense(32, activation="relu"),
    layers.Dropout(0.2),
    layers.Dense(16, activation="relu"),
    layers.Dense(n_classes_har, activation="softmax"),
])
har_model.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])
har_model.fit(X_train_s, y_train, epochs=25, batch_size=64, verbose=0, validation_split=0.1)

har_loss, har_acc = har_model.evaluate(X_test_s, y_test, verbose=0)
print(f"Accuracy: {har_acc:.4f}  (classes: {list(activity_encoder.classes_)})")
results["Activity Recognition (NeuralNetwork)"] = f"accuracy={har_acc:.4f}"

har_model.save(f"{MODEL_DIR}/activity_recognition_nn.keras")
joblib.dump(har_scaler, f"{MODEL_DIR}/har_scaler.joblib")
joblib.dump(activity_encoder, f"{MODEL_DIR}/activity_encoder.joblib")
joblib.dump(har_feature_names, f"{MODEL_DIR}/har_feature_names.joblib")

# full-dataset predicted_activity for downstream Threat Assessment model
pred_activity_all = activity_encoder.inverse_transform(
    np.argmax(har_model.predict(har_scaler.transform(X_har), verbose=0), axis=1)
)
df["predicted_activity_model"] = pred_activity_all

# ===========================================================================
# 5. ANOMALY DETECTION MODEL -- Isolation Forest
# ===========================================================================
print("\n" + "=" * 70)
print("5. ANOMALY DETECTION MODEL (Isolation Forest)")
print("=" * 70)

anomaly_event_encoder = LabelEncoder()
event_type_encoded = anomaly_event_encoder.fit_transform(df["event_type"])

anomaly_features_df = pd.DataFrame({
    "actual_consumption": df["actual_consumption"],
    "predicted_consumption": df["predicted_consumption"],
    "event_type_encoded": event_type_encoded,
    "temperature": df["temperature"],
    "humidity": df["humidity"],
    "PIR": df["PIR"],
    "door_state": df["door_state"],
    "time_of_day": df["time_of_day"],
})

anomaly_scaler = StandardScaler().fit(anomaly_features_df)
X_anom = anomaly_scaler.transform(anomaly_features_df)

contamination = max(df["anomaly_true"].mean(), 0.01)
anomaly_model = IsolationForest(
    n_estimators=200, contamination=contamination, random_state=42, n_jobs=-1
)
anomaly_model.fit(X_anom)

raw_pred = anomaly_model.predict(X_anom)          # -1 = anomaly, 1 = normal
anomaly_pred = (raw_pred == -1).astype(int)
anomaly_true = df["anomaly_true"].values
anomaly_acc = accuracy_score(anomaly_true, anomaly_pred)
print(f"Accuracy vs injected ground-truth anomalies: {anomaly_acc:.4f}")
print("(Isolation Forest is unsupervised; ground-truth anomaly flags were")
print(" synthetically injected during data generation purely for evaluation.)")
results["Anomaly Detection (IsolationForest)"] = f"accuracy={anomaly_acc:.4f}"

joblib.dump(anomaly_model, f"{MODEL_DIR}/anomaly_isolation_forest.joblib")
joblib.dump(anomaly_scaler, f"{MODEL_DIR}/anomaly_scaler.joblib")
joblib.dump(anomaly_event_encoder, f"{MODEL_DIR}/anomaly_event_encoder.joblib")

df["anomaly_pred"] = anomaly_pred

# ===========================================================================
# 6. THREAT ASSESSMENT MODEL -- Neural Network (Keras Dense classifier)
# ===========================================================================
print("\n" + "=" * 70)
print("6. THREAT ASSESSMENT MODEL (Neural Network)")
print("=" * 70)

threat_num_features = ["PIR", "predicted_consumption", "actual_consumption", "anomaly_pred",
                        "door_state", "smoke_level", "co2", "time_of_day",
                        "outdoor_temperature", "temperature"]
threat_encoder = LabelEncoder()
y_threat = threat_encoder.fit_transform(df["threat_type"])

activity_dummies = pd.get_dummies(df["predicted_activity_model"], prefix="activity")
X_threat = np.hstack([df[threat_num_features].values, activity_dummies.values]).astype("float32")
threat_feature_names = threat_num_features + list(activity_dummies.columns)

X_train, X_test, y_train, y_test = train_test_split(
    X_threat, y_threat, test_size=0.2, random_state=42, stratify=y_threat
)
threat_scaler = StandardScaler().fit(X_train)
X_train_s = threat_scaler.transform(X_train)
X_test_s = threat_scaler.transform(X_test)

n_classes_threat = len(threat_encoder.classes_)
threat_model = keras.Sequential([
    layers.Input(shape=(X_train_s.shape[1],)),
    layers.Dense(64, activation="relu"),
    layers.Dropout(0.3),
    layers.Dense(32, activation="relu"),
    layers.Dense(n_classes_threat, activation="softmax"),
])
threat_model.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])

# class weights: threat_type is heavily imbalanced (mostly "none")
from sklearn.utils.class_weight import compute_class_weight
class_weights = compute_class_weight("balanced", classes=np.unique(y_train), y=y_train)
class_weight_dict = dict(zip(np.unique(y_train), class_weights))

threat_model.fit(X_train_s, y_train, epochs=40, batch_size=64, verbose=0,
                  validation_split=0.1, class_weight=class_weight_dict)

threat_loss, threat_acc = threat_model.evaluate(X_test_s, y_test, verbose=0)
print(f"Accuracy: {threat_acc:.4f}  (classes: {list(threat_encoder.classes_)})")
results["Threat Assessment (NeuralNetwork)"] = f"accuracy={threat_acc:.4f}"

threat_model.save(f"{MODEL_DIR}/threat_assessment_nn.keras")
joblib.dump(threat_scaler, f"{MODEL_DIR}/threat_scaler.joblib")
joblib.dump(threat_encoder, f"{MODEL_DIR}/threat_encoder.joblib")
joblib.dump(threat_feature_names, f"{MODEL_DIR}/threat_feature_names.joblib")

# ===========================================================================
# SUMMARY
# ===========================================================================
print("\n" + "=" * 70)
print("PERFORMANCE SUMMARY OF ALL 6 STACKED MODELS")
print("=" * 70)
for name, metric in results.items():
    print(f"{name:45s} {metric}")

print(f"\nAll model weights saved to: {MODEL_DIR}/")
