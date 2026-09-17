import os
import joblib
import tensorflow as tf
from tensorflow import keras
import numpy as np
import pandas as pd
import time
from lime.lime_tabular import LimeTabularExplainer
import sys
import warnings
import json
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
from openai import OpenAI
os.environ["PYTHONWARNINGS"] = "ignore"
warnings.filterwarnings("ignore")



# API Key
GROQ_API_KEY = "your_API_Key" 

llm_client = None
if GROQ_API_KEY:
    llm_client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=GROQ_API_KEY
    )

def generate_llm_answer(model_name, prediction, scores_dict):
    if not llm_client:
        return "LLM explanations are disabled. No API Key provided."
        
    prompt = f"""
    You are the AI assistant of a smart home security system. 
    The module '{model_name}' just ran and its final output/prediction is: '{prediction}'.

    The features that led to this output are:
    {scores_dict}

    Your task is to interpret this outcome and explain it to the homeowner in 1-2 short, natural sentences. 
    - Understand what the output '{prediction}' means in the context of '{model_name}'.
    - Explain *why* this specific outcome happened by naturally referencing the provided features.
    DO NOT mention any numbers, math, decimals, or weights. Speak simply and contextually.
    """
    
    try:
        response = llm_client.chat.completions.create(
            model="groq/compound-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=200
        )
        
        answer = response.choices[0].message.content
            
        return answer.strip()
        
    except Exception as e:
        return f"Error generating explanation: {e}"

BROKER="your_ip"
# Load data
# ============================================================
# DATA
# ============================================================

CSV_PATH = r"csv_path/filename.csv" #add the path to your csv file (place it in the same folder as this code)
#na valw sto telos toy path kai to noma toy arxeioy
df = pd.read_csv(CSV_PATH)

if "timestamp" in df.columns:
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

print("Dataset shape:", df.shape)

# Load models

# ============================================================
# MODEL DIRECTORY
# ============================================================

MODEL_DIR = r"path_where_models_are" #add the path where the models are (also place them in the same folder)


# ============================================================
# 1. OCCUPANCY ESTIMATION
# RandomForestClassifier
# ============================================================

model1 = joblib.load(
    os.path.join(MODEL_DIR, "occupancy_random_forest.joblib")
)

print("Model 1 loaded: Occupancy Random Forest")


# ============================================================
# 2. VIBRATION ANALYSIS
# GradientBoostingClassifier
# ============================================================

model2 = joblib.load(
    os.path.join(MODEL_DIR, "vibration_gradient_boosting.joblib")
)

# Encoder used to convert event_type <-> numerical classes
model2_encoder = joblib.load(
    os.path.join(MODEL_DIR, "event_type_encoder.joblib")
)

print("Model 2 loaded: Vibration Gradient Boosting")


# ============================================================
# 3. ENERGY CONSUMPTION
# LSTM
# ============================================================

model3 = keras.models.load_model(
    os.path.join(MODEL_DIR, "energy_lstm.keras")
)

# Input and output scalers
model3_scaler_x = joblib.load(
    os.path.join(MODEL_DIR, "energy_scaler_x.joblib")
)

model3_scaler_y = joblib.load(
    os.path.join(MODEL_DIR, "energy_scaler_y.joblib")
)

print("Model 3 loaded: Energy LSTM")


# ============================================================
# 4. ACTIVITY RECOGNITION
# Keras Dense Neural Network
# ============================================================

model4 = keras.models.load_model(
    os.path.join(MODEL_DIR, "activity_recognition_nn.keras")
)

# Scaler
model4_scaler = joblib.load(
    os.path.join(MODEL_DIR, "har_scaler.joblib")
)

# Activity label encoder
model4_encoder = joblib.load(
    os.path.join(MODEL_DIR, "activity_encoder.joblib")
)

# Exact feature order used during training
model4_feature_names = joblib.load(
    os.path.join(MODEL_DIR, "har_feature_names.joblib")
)

print("Model 4 loaded: Activity Recognition Neural Network")


# ============================================================
# 5. ANOMALY DETECTION
# IsolationForest
# ============================================================

model5 = joblib.load(
    os.path.join(MODEL_DIR, "anomaly_isolation_forest.joblib")
)

# Scaler
model5_scaler = joblib.load(
    os.path.join(MODEL_DIR, "anomaly_scaler.joblib")
)

# Event encoder
model5_encoder = joblib.load(
    os.path.join(MODEL_DIR, "anomaly_event_encoder.joblib")
)

print("Model 5 loaded: Anomaly Isolation Forest")


# ============================================================
# 6. THREAT ASSESSMENT
# Keras Dense Neural Network
# ============================================================

model6 = keras.models.load_model(
    os.path.join(MODEL_DIR, "threat_assessment_nn.keras")
)

# Scaler
model6_scaler = joblib.load(
    os.path.join(MODEL_DIR, "threat_scaler.joblib")
)

# Threat label encoder
model6_encoder = joblib.load(
    os.path.join(MODEL_DIR, "threat_encoder.joblib")
)

# Exact feature order used during training
model6_feature_names = joblib.load(
    os.path.join(MODEL_DIR, "threat_feature_names.joblib")
)

print("Model 6 loaded: Threat Assessment Neural Network")


# ============================================================
# CHECK THAT EVERYTHING LOADED
# ============================================================

print("\n" + "=" * 60)
print("ALL 6 MODELS LOADED SUCCESSFULLY")
print("=" * 60)

print("model1:", type(model1).__name__)
print("model2:", type(model2).__name__)
print("model3:", type(model3).__name__)
print("model4:", type(model4).__name__)
print("model5:", type(model5).__name__)
print("model6:", type(model6).__name__)




# ============================================================
# TRACE-XAI DAG
# ============================================================

graph = {

    # --------------------------------------------------------
    # MODEL 1
    # Occupancy Estimation -- Random Forest
    # --------------------------------------------------------

    "M1_Occupancy": {

        "model": model1,

        "input_names": [
            "temperature",
            "humidity",
            "co2",
            "light",
            "PIR"
        ],

        "input_sources": {

            "temperature": None,
            "humidity": None,
            "co2": None,
            "light": None,
            "PIR": None
        }
    },


    # --------------------------------------------------------
    # MODEL 2
    # Vibration Analysis -- Gradient Boosting
    # --------------------------------------------------------

    "M2_Vibration": {

        "model": model2,

        "input_names": [

            "vibration_rms",
            "peak_acceleration",
            "dominant_frequency",
            "spectral_energy",
            "spectral_entropy",
            "vibration_duration",

            "acceleration_x",
            "acceleration_y",
            "acceleration_z",

            "occupant_presence"
        ],

        "input_sources": {

            "vibration_rms": None,
            "peak_acceleration": None,
            "dominant_frequency": None,
            "spectral_energy": None,
            "spectral_entropy": None,
            "vibration_duration": None,

            "acceleration_x": None,
            "acceleration_y": None,
            "acceleration_z": None,

            "occupant_presence": "M1_Occupancy"
        }
    },


    # --------------------------------------------------------
    # MODEL 3
    # Energy Consumption Prediction -- LSTM
    # --------------------------------------------------------

    "M3_Energy": {

        "model": model3,

        "input_names": [

            "temperature",
            "humidity",
            "co2",
            "light",
            "occupant_presence"
        ],

        "input_sources": {

            "temperature": None,
            "humidity": None,
            "co2": None,
            "light": None,

            "occupant_presence": "M1_Occupancy"
        }
    },


    # --------------------------------------------------------
    # MODEL 4
    # Activity Recognition -- Neural Network
    # --------------------------------------------------------

    "M4_Activity": {

        "model": model4,

        "input_names": [

            "occupant_count",
            "PIR",
            "outdoor_temperature",
            "light",
            "predicted_consumption",
            "time_of_day",

            "door_state",
            "event_type"
        ],

        "input_sources": {

            "occupant_count": None,
            "PIR": None,
            "outdoor_temperature": None,
            "light": None,

            "predicted_consumption": "M3_Energy",

            "time_of_day": None,

            "door_state": None,

            "event_type": "M2_Vibration"
        }
    },


    # --------------------------------------------------------
    # MODEL 5
    # Anomaly Detection -- Isolation Forest
    # --------------------------------------------------------

    "M5_Anomaly": {

        "model": model5,

        "input_names": [

            "actual_consumption",
            "predicted_consumption",
            "event_type_encoded",

            "temperature",
            "humidity",
            "PIR",
            "door_state",
            "time_of_day"
        ],

        "input_sources": {

            "actual_consumption": None,

            "predicted_consumption": "M3_Energy",

            "event_type_encoded": "M2_Vibration",

            "temperature": None,
            "humidity": None,
            "PIR": None,
            "door_state": None,
            "time_of_day": None
        }
    },


    # --------------------------------------------------------
    # MODEL 6
    # Threat Assessment -- Neural Network
    # FINAL MODEL
    # --------------------------------------------------------

    "M6_Threat": {

        "model": model6,

        "input_names": [

            "PIR",
            "predicted_consumption",
            "actual_consumption",
            "anomaly_pred",
            "door_state",
            "smoke_level",
            "co2",
            "time_of_day",
            "outdoor_temperature",
            "temperature",

            "predicted_activity_model"
        ],

        "input_sources": {

            "PIR": None,

            "predicted_consumption": "M3_Energy",

            "actual_consumption": None,

            "anomaly_pred": "M5_Anomaly",

            "door_state": None,
            "smoke_level": None,
            "co2": None,
            "time_of_day": None,
            "outdoor_temperature": None,
            "temperature": None,

            "predicted_activity_model": "M4_Activity"
        }
    }
}


# RAW FEATURES

raw_features = {
    "temperature",
    "humidity",
    "co2",
    "light",
    "PIR",
    "outdoor_temperature",
    "time_of_day",
    "vibration_rms",
    "peak_acceleration",
    "dominant_frequency",
    "spectral_energy",
    "spectral_entropy",
    "vibration_duration",
    "acceleration_x",
    "acceleration_y",
    "acceleration_z",
    "occupant_count",
    "door_state",
    "actual_consumption",
    "smoke_level"
}





# ============================================================
# DAG OUTPUTS
# ============================================================

def get_dag_outputs(row_index):

    row = df.iloc[row_index]

    outputs = {}


    # ========================================================
    # M1 OCCUPANCY
    # Random Forest
    # ========================================================

    X1 = pd.DataFrame([[
        row["temperature"],
        row["humidity"],
        row["co2"],
        row["light"],
        row["PIR"]
    ]], columns=[
        "temperature",
        "humidity",
        "co2",
        "light",
        "PIR"
    ])

    occupancy_pred = model1.predict(X1)[0]

    outputs["M1_Occupancy"] = occupancy_pred


    # ========================================================
    # M2 VIBRATION
    # Gradient Boosting
    # ========================================================

    X2 = pd.DataFrame([[
        row["vibration_rms"],
        row["peak_acceleration"],
        row["dominant_frequency"],
        row["spectral_energy"],
        row["spectral_entropy"],
        row["vibration_duration"],
        row["acceleration_x"],
        row["acceleration_y"],
        row["acceleration_z"],
        outputs["M1_Occupancy"]
    ]], columns=[
        "vibration_rms",
        "peak_acceleration",
        "dominant_frequency",
        "spectral_energy",
        "spectral_entropy",
        "vibration_duration",
        "acceleration_x",
        "acceleration_y",
        "acceleration_z",
        "occupant_presence"
    ])

    event_id = model2.predict(X2)[0]

    # Convert numerical class back to original event_type
    event_pred = model2_encoder.inverse_transform(
        [event_id]
    )[0]

    outputs["M2_Vibration"] = event_pred


    # ========================================================
    # M3 ENERGY CONSUMPTION
    # LSTM
    #
    # IMPORTANT:
    # M3 requires a 12-timestep sequence.
    # Therefore we cannot simply pass one row.
    # ========================================================

    WINDOW = 12

    start_idx = max(
        0,
        row_index - WINDOW + 1
    )

    history = df.iloc[start_idx:row_index + 1].copy()

    energy_features = [
        "temperature",
        "humidity",
        "co2",
        "light",
        "occupant_presence"
    ]

    # --------------------------------------------------------
    # Build the sequence
    #
    # For occupant_presence we use the M1 prediction for
    # every timestep in the available history.
    # --------------------------------------------------------

    energy_sequence = []

    for idx in range(start_idx, row_index + 1):

        hist_row = df.iloc[idx]

        # Run M1 for this historical timestep
        X1_hist = pd.DataFrame([[
            hist_row["temperature"],
            hist_row["humidity"],
            hist_row["co2"],
            hist_row["light"],
            hist_row["PIR"]
        ]], columns=[
            "temperature",
            "humidity",
            "co2",
            "light",
            "PIR"
        ])

        occupancy_hist = model1.predict(X1_hist)[0]

        energy_sequence.append([
            hist_row["temperature"],
            hist_row["humidity"],
            hist_row["co2"],
            hist_row["light"],
            occupancy_hist
        ])

    energy_sequence = np.asarray(
        energy_sequence,
        dtype="float32"
    )

    # --------------------------------------------------------
    # If fewer than 12 observations are available, pad using
    # the earliest available observation.
    # --------------------------------------------------------

    if len(energy_sequence) < WINDOW:

        padding = np.repeat(
            energy_sequence[0:1],
            WINDOW - len(energy_sequence),
            axis=0
        )

        energy_sequence = np.vstack([
            padding,
            energy_sequence
        ])

    # Keep exactly the last 12 observations
    energy_sequence = energy_sequence[-WINDOW:]

    # --------------------------------------------------------
    # Scale input
    # --------------------------------------------------------

    X3 = model3_scaler_x.transform(
        energy_sequence
    )

    # Add batch dimension:
    # (12, 5) -> (1, 12, 5)
    X3 = X3[np.newaxis, :, :]

    # --------------------------------------------------------
    # LSTM prediction
    # --------------------------------------------------------

    energy_pred_scaled = model3.predict(
        X3,
        verbose=0
    ).reshape(-1, 1)

    energy_pred = model3_scaler_y.inverse_transform(
        energy_pred_scaled
    )[0, 0]

    outputs["M3_Energy"] = float(
        energy_pred
    )

    # Use the name from the training pipeline
    outputs["predicted_consumption"] = float(
        energy_pred
    )


    # ========================================================
    # M4 ACTIVITY RECOGNITION
    # Neural Network
    # ========================================================

    # --------------------------------------------------------
    # Training features:
    #
    # occupant_count
    # PIR
    # outdoor_temperature
    # light
    # predicted_consumption
    # time_of_day
    # door_state
    # event_type one-hot encoded
    # --------------------------------------------------------

    # Create the event one-hot vector using the exact feature
    # names saved during training.
    event_columns = [
        name
        for name in model4_feature_names
        if name.startswith("event_")
    ]

    event_dummies = {
        column: 0.0
        for column in event_columns
    }

    # The training code used:
    # pd.get_dummies(df["event_type"], prefix="event")
    #
    # Therefore the expected column is event_<event_type>.
    current_event_column = f"event_{event_pred}"

    if current_event_column in event_dummies:
        event_dummies[current_event_column] = 1.0

    # --------------------------------------------------------
    # Construct features in EXACT training order
    # --------------------------------------------------------

    X4_dict = {

        "occupant_count": row["occupant_count"],
        "PIR": row["PIR"],
        "outdoor_temperature": row["outdoor_temperature"],
        "light": row["light"],
        "predicted_consumption": outputs["predicted_consumption"],
        "time_of_day": row["time_of_day"],
        "door_state": row["door_state"]
    }

    X4_dict.update(event_dummies)

    X4 = pd.DataFrame(
        [[X4_dict[name] for name in model4_feature_names]],
        columns=model4_feature_names
    )

    # Scale exactly as during training
    X4_scaled = model4_scaler.transform(X4)

    # --------------------------------------------------------
    # Neural network prediction
    # --------------------------------------------------------

    p4 = model4.predict(
        X4_scaled,
        verbose=0
    )

    activity_id = np.argmax(
        p4,
        axis=1
    )[0]

    activity_pred = model4_encoder.inverse_transform(
        [activity_id]
    )[0]

    outputs["M4_Activity"] = activity_pred

    # Name used by M6
    outputs["predicted_activity_model"] = activity_pred


    # ========================================================
    # M5 ANOMALY DETECTION
    # Isolation Forest
    # ========================================================

    # --------------------------------------------------------
    # Training features:
    #
    # actual_consumption
    # predicted_consumption
    # event_type_encoded
    # temperature
    # humidity
    # PIR
    # door_state
    # time_of_day
    # --------------------------------------------------------

    # Encode event_type exactly as during training
    event_type_encoded = model5_encoder.transform(
        [event_pred]
    )[0]

    X5 = pd.DataFrame([[
        row["actual_consumption"],
        outputs["predicted_consumption"],
        event_type_encoded,
        row["temperature"],
        row["humidity"],
        row["PIR"],
        row["door_state"],
        row["time_of_day"]
    ]], columns=[
        "actual_consumption",
        "predicted_consumption",
        "event_type_encoded",
        "temperature",
        "humidity",
        "PIR",
        "door_state",
        "time_of_day"
    ])

    # Scale
    X5_scaled = model5_scaler.transform(X5)

    # Isolation Forest:
    #   1  = normal
    #  -1  = anomaly
    anomaly_raw = model5.predict(
        X5_scaled
    )[0]

    anomaly_pred = (
        1
        if anomaly_raw == -1
        else 0
    )

    outputs["M5_Anomaly"] = anomaly_pred

    # Explicit name used by M6
    outputs["anomaly_pred"] = anomaly_pred


    # ========================================================
    # M6 THREAT ASSESSMENT
    # Neural Network -- FINAL MODEL
    # ========================================================

    # --------------------------------------------------------
    # Training features:
    #
    # PIR
    # predicted_consumption
    # actual_consumption
    # anomaly_pred
    # door_state
    # smoke_level
    # co2
    # time_of_day
    # outdoor_temperature
    # temperature
    #
    # + predicted_activity_model one-hot encoded
    # --------------------------------------------------------

    activity_columns = [
        name
        for name in model6_feature_names
        if name.startswith("activity_")
    ]

    activity_dummies = {
        column: 0.0
        for column in activity_columns
    }

    current_activity_column = (
        f"activity_{activity_pred}"
    )

    if current_activity_column in activity_dummies:
        activity_dummies[current_activity_column] = 1.0

    # --------------------------------------------------------
    # Construct base features
    # --------------------------------------------------------

    X6_dict = {

        "PIR": row["PIR"],

        "predicted_consumption":
            outputs["predicted_consumption"],

        "actual_consumption":
            row["actual_consumption"],

        "anomaly_pred":
            outputs["anomaly_pred"],

        "door_state":
            row["door_state"],

        "smoke_level":
            row["smoke_level"],

        "co2":
            row["co2"],

        "time_of_day":
            row["time_of_day"],

        "outdoor_temperature":
            row["outdoor_temperature"],

        "temperature":
            row["temperature"]
    }

    X6_dict.update(activity_dummies)

    # --------------------------------------------------------
    # IMPORTANT:
    # Use the exact feature order saved during training.
    # --------------------------------------------------------

    X6 = pd.DataFrame(
        [[X6_dict[name] for name in model6_feature_names]],
        columns=model6_feature_names
    )

    # Scale
    X6_scaled = model6_scaler.transform(X6)

    # --------------------------------------------------------
    # Threat prediction
    # --------------------------------------------------------

    p6 = model6.predict(
        X6_scaled,
        verbose=0
    )

    threat_id = np.argmax(
        p6,
        axis=1
    )[0]

    threat_pred = model6_encoder.inverse_transform(
        [threat_id]
    )[0]

    outputs["M6_Threat"] = threat_pred


    # ========================================================
    # RETURN ALL DAG OUTPUTS
    # ========================================================

    return outputs




# ============================================================
# BUILD TRAIN_FULL
# ============================================================



#########################################" TO BE COMMENT AFTER GENERATING TRAIN FULL DATASET"

# import time

#all_rows = []

# print("Generating DAG outputs...")

# start = time.perf_counter()

# with joblib.parallel_backend('sequential'):
#     for i in range(len(df)):
#         if i % 100 == 0:
#             print(f"Επεξεργασία γραμμής: {i} / {len(df)}")
#         # --------------------------------------------------------
#         # Run the complete DAG for this row
#         # --------------------------------------------------------

#         outputs = get_dag_outputs(i)

#         row = df.iloc[i]


#         # --------------------------------------------------------
#         # Store raw features + DAG outputs
#         # --------------------------------------------------------

#         all_rows.append({

#             # ====================================================
#             # RAW FEATURES
#             # ====================================================

#             "temperature": row["temperature"],
#             "humidity": row["humidity"],
#             "co2": row["co2"],
#             "light": row["light"],
#             "PIR": row["PIR"],

#             "outdoor_temperature":
#                 row["outdoor_temperature"],

#             "time_of_day":
#                 row["time_of_day"],

#             # ----------------------------------------------------
#             # Vibration
#             # ----------------------------------------------------

#             "vibration_rms":
#                 row["vibration_rms"],

#             "peak_acceleration":
#                 row["peak_acceleration"],

#             "dominant_frequency":
#                 row["dominant_frequency"],

#             "spectral_energy":
#                 row["spectral_energy"],

#             "spectral_entropy":
#                 row["spectral_entropy"],

#             "vibration_duration":
#                 row["vibration_duration"],

#             "acceleration_x":
#                 row["acceleration_x"],

#             "acceleration_y":
#                 row["acceleration_y"],

#             "acceleration_z":
#                 row["acceleration_z"],

#             # ----------------------------------------------------
#             # Activity / Context
#             # ----------------------------------------------------

#             "occupant_count":
#                 row["occupant_count"],

#             "door_state":
#                 row["door_state"],

#             "event_type":
#                 row["event_type"],

#             # ----------------------------------------------------
#             # Energy
#             # ----------------------------------------------------

#             "actual_consumption":
#                 row["actual_consumption"],

#             # ----------------------------------------------------
#             # Threat / Safety
#             # ----------------------------------------------------

#             "smoke_level":
#                 row["smoke_level"],


#             # ====================================================
#             # INTERMEDIATE / DAG OUTPUTS
#             # ====================================================

#             # ----------------------------------------------------
#             # M1 Occupancy
#             # ----------------------------------------------------

#             "M1_Occupancy":
#                 outputs["M1_Occupancy"],


#             # ----------------------------------------------------
#             # M2 Vibration
#             # ----------------------------------------------------

#             "M2_Vibration":
#                 outputs["M2_Vibration"],


#             # ----------------------------------------------------
#             # M3 Energy Consumption
#             # ----------------------------------------------------

#             "M3_Energy":
#                 outputs["M3_Energy"],

#             # Alias corresponding to the feature used downstream
#             "predicted_consumption":
#                 outputs["predicted_consumption"],


#             # ----------------------------------------------------
#             # M4 Activity Recognition
#             # ----------------------------------------------------

#             "M4_Activity":
#                 outputs["M4_Activity"],

#             # Feature name used by M6
#             "predicted_activity_model":
#                 outputs["predicted_activity_model"],


#             # ----------------------------------------------------
#             # M5 Anomaly Detection
#             # ----------------------------------------------------

#             "M5_Anomaly":
#                 outputs["M5_Anomaly"],

#             # Feature name used by M6
#             "anomaly_pred":
#                 outputs["anomaly_pred"],


#             # ----------------------------------------------------
#             # M6 Threat Assessment -- FINAL OUTPUT
#             # ----------------------------------------------------

#             "M6_Threat":
#                 outputs["M6_Threat"]
#         })


# # ============================================================
# # CREATE TRAIN_FULL
# # ============================================================

# train_full = pd.DataFrame(all_rows)


# # ============================================================
# # PERFORMANCE INFORMATION
# # ============================================================

# elapsed = time.perf_counter() - start

# print(
#     f"Finished in {elapsed:.2f} seconds"
# )

# print(
#     f"train_full shape: {train_full.shape}"
# )

# print("\nColumns:")
# for column in train_full.columns:
#     print(f"  - {column}")


# train_full.to_pickle(
#     r"path_where_ths_code_is/trace_xai_train_full.pkl"
# )

# #########################################" TO BE COMMENT AFTER GENERATING TRAIN FULL DATASET"


train_full = pd.read_pickle(
     r"path_where_this_code_is/trace_xai_train_full.pkl"
)


# ============================================================
# LIME FEATURES FOR EACH NODE
# ============================================================

lime_features = {

    "M1_Occupancy": [
        "temperature",
        "humidity",
        "co2",
        "light",
        "PIR"
    ],

    "M2_Vibration": [
        "vibration_rms",
        "peak_acceleration",
        "dominant_frequency",
        "spectral_energy",
        "spectral_entropy",
        "vibration_duration",
        "acceleration_x",
        "acceleration_y",
        "acceleration_z",
        "occupant_presence"
    ],

    "M3_Energy": [
        "temperature",
        "humidity",
        "co2",
        "light",
        "occupant_presence"
    ],

    "M4_Activity": [
        "occupant_count",
        "PIR",
        "outdoor_temperature",
        "light",
        "predicted_consumption",
        "time_of_day",
        "door_state",
        "event_type"
    ],

    "M5_Anomaly": [
        "actual_consumption",
        "predicted_consumption",
        "event_type_encoded",
        "temperature",
        "humidity",
        "PIR",
        "door_state",
        "time_of_day"
    ],

    "M6_Threat": [
        "PIR",
        "predicted_consumption",
        "actual_consumption",
        "anomaly_pred",
        "door_state",
        "smoke_level",
        "co2",
        "time_of_day",
        "outdoor_temperature",
        "temperature",
        "predicted_activity_model"
    ]
}


# ============================================================
# NODE INPUT DATA
# ============================================================

train_node = {}


# ------------------------------------------------------------
# M1: OCCUPANCY
# ------------------------------------------------------------

train_node["M1_Occupancy"] = pd.DataFrame({

    "temperature":
        train_full["temperature"],

    "humidity":
        train_full["humidity"],

    "co2":
        train_full["co2"],

    "light":
        train_full["light"],

    "PIR":
        train_full["PIR"]
})


# ------------------------------------------------------------
# M2: VIBRATION
# ------------------------------------------------------------

train_node["M2_Vibration"] = pd.DataFrame({

    "vibration_rms":
        train_full["vibration_rms"],

    "peak_acceleration":
        train_full["peak_acceleration"],

    "dominant_frequency":
        train_full["dominant_frequency"],

    "spectral_energy":
        train_full["spectral_energy"],

    "spectral_entropy":
        train_full["spectral_entropy"],

    "vibration_duration":
        train_full["vibration_duration"],

    "acceleration_x":
        train_full["acceleration_x"],

    "acceleration_y":
        train_full["acceleration_y"],

    "acceleration_z":
        train_full["acceleration_z"],

    "occupant_presence":
        train_full["M1_Occupancy"]
})


# ------------------------------------------------------------
# M3: ENERGY
# ------------------------------------------------------------

train_node["M3_Energy"] = pd.DataFrame({

    "temperature":
        train_full["temperature"],

    "humidity":
        train_full["humidity"],

    "co2":
        train_full["co2"],

    "light":
        train_full["light"],

    "occupant_presence":
        train_full["M1_Occupancy"]
})


# ------------------------------------------------------------
# M4: ACTIVITY
# ------------------------------------------------------------

train_node["M4_Activity"] = pd.DataFrame({

    "occupant_count":
        train_full["occupant_count"],

    "PIR":
        train_full["PIR"],

    "outdoor_temperature":
        train_full["outdoor_temperature"],

    "light":
        train_full["light"],

    "predicted_consumption":
        train_full["predicted_consumption"],

    "time_of_day":
        train_full["time_of_day"],

    "door_state":
        train_full["door_state"],

    "event_type":
        train_full["event_type"]
})


# ------------------------------------------------------------
# M5: ANOMALY
# ------------------------------------------------------------

train_node["M5_Anomaly"] = pd.DataFrame({

    "actual_consumption":
        train_full["actual_consumption"],

    "predicted_consumption":
        train_full["predicted_consumption"],

    "event_type_encoded":
        train_full["event_type"].map(
            lambda x: model5_encoder.transform([x])[0]
        ),

    "temperature":
        train_full["temperature"],

    "humidity":
        train_full["humidity"],

    "PIR":
        train_full["PIR"],

    "door_state":
        train_full["door_state"],

    "time_of_day":
        train_full["time_of_day"]
})


# ------------------------------------------------------------
# M6: THREAT
# ------------------------------------------------------------

train_node["M6_Threat"] = pd.DataFrame({

    "PIR":
        train_full["PIR"],

    "predicted_consumption":
        train_full["predicted_consumption"],

    "actual_consumption":
        train_full["actual_consumption"],

    "anomaly_pred":
        train_full["anomaly_pred"],

    "door_state":
        train_full["door_state"],

    "smoke_level":
        train_full["smoke_level"],

    "co2":
        train_full["co2"],

    "time_of_day":
        train_full["time_of_day"],

    "outdoor_temperature":
        train_full["outdoor_temperature"],

    "temperature":
        train_full["temperature"],

    "predicted_activity_model":
        train_full["predicted_activity_model"]
})


model_types = {

    "M1_Occupancy": "classification",

    "M2_Vibration": "classification",

    "M3_Energy": "regression",

    "M4_Activity": "classification",

    "M5_Anomaly": "classification",

    "M6_Threat": "classification",

}



def create_lime_explainers(
    graph,
    train_node,
    random_state=42
):
    """
    Create LIME explainers for all DAG nodes.

    Classification:
        mode='classification'
        class_names taken from model.classes_

    Regression:
        mode='regression'

    Automatically detects categorical input columns.
    """

    explainer_dict = {}

    for node_name, node in graph.items():

        model = node["model"]
        model_type = model_types[node_name]
        input_names = node["input_names"]

        X_train = train_node[node_name][input_names].copy()

        print(f"\nCreating LIME explainer: {node_name}")
        print(f"  Type: {model_type}")
        print(f"  Features: {input_names}")
        print(f"  Shape: {X_train.shape}")

        # ==================================================
        # DETECT CATEGORICAL FEATURES
        # ==================================================

        categorical_features = []
        categorical_names = {}

        for i, feature in enumerate(input_names):

            # Object/string/category columns
            if (
                X_train[feature].dtype == "object"
                or str(X_train[feature].dtype) == "category"
                or pd.api.types.is_string_dtype(
                    X_train[feature]
                )
            ):

                categorical_features.append(i)

                # Convert categories to strings
                categories = (
                    X_train[feature]
                    .dropna()
                    .unique()
                    .tolist()
                )

                categorical_names[i] = [
                    str(x) for x in categories
                ]

        if categorical_features:

            print("  Categorical features:")

            for idx in categorical_features:

                print(
                    f"    {input_names[idx]}: "
                    f"{categorical_names[idx]}"
                )

        else:

            print("  Categorical features: None")

        # ==================================================
        # LIME NEEDS NUMERIC DATA
        # ==================================================
        #
        # LIME represents categorical variables internally
        # using integer codes.
        #
        # Therefore convert categorical columns to codes.
        # ==================================================

        X_lime = X_train.copy()

        for idx in categorical_features:

            feature = input_names[idx]

            categories = categorical_names[idx]

            mapping = {
                category: i
                for i, category in enumerate(categories)
            }

            X_lime[feature] = (
                X_lime[feature]
                .astype(str)
                .map(mapping)
            )

        # Make sure everything passed to LIME is numeric
        X_lime = X_lime.astype(float)

        # ==================================================
        # CREATE CLASSIFICATION EXPLAINER
        # ==================================================

        if model_type == "classification":

            if hasattr(model, "classes_"):
                class_names = [str(c) for c in model.classes_]
            elif node_name == "M4_Activity":
                class_names = [str(c) for c in model4_encoder.classes_]
            elif node_name == "M6_Threat":
                class_names = [str(c) for c in model6_encoder.classes_]
            elif node_name == "M5_Anomaly":
                class_names = ["-1", "1"] 
            else:
                raise AttributeError(
                    f"{node_name} is marked as classification "
                    f"but no classes were found."
                )

            print(
                f"  Classes: {class_names}"
            )

            explainer = LimeTabularExplainer(
                training_data=X_lime.values,
                feature_names=input_names,
                class_names=class_names,
                categorical_features=categorical_features,
                categorical_names=categorical_names,
                mode="classification",
                discretize_continuous=True,
                random_state=random_state
            )

        # ==================================================
        # CREATE REGRESSION EXPLAINER
        # ==================================================

        elif model_type == "regression":

            explainer = LimeTabularExplainer(
                training_data=X_lime.values,
                feature_names=input_names,
                categorical_features=categorical_features,
                categorical_names=categorical_names,
                mode="regression",
                discretize_continuous=True,
                random_state=random_state
            )

        else:

            raise ValueError(
                f"Unknown model type '{model_type}' "
                f"for {node_name}"
            )

        # Store additional information because we need
        # the same categorical encoding later when LIME
        # calls predict_fn.
        explainer_dict[node_name] = {
            "explainer": explainer,
            "categorical_features": categorical_features,
            "categorical_names": categorical_names,
            "input_names": input_names
        }

    return explainer_dict

explainer_dict = create_lime_explainers(
    graph=graph,
    train_node=train_node
)


# ============================================================
# CLEAN LIME EXPLANATION
# ============================================================

def clean_exp(
    features,
    explanation_list
):

    cleaned = {
        f: 0.0
        for f in features
    }

    for condition, value in explanation_list:

        condition = condition.strip()

        # Exact feature detection
        for feature in features:

            if (
                condition == feature
                or condition.startswith(feature + " ")
                or condition.startswith(feature + "<")
                or condition.startswith(feature + ">")
                or condition.startswith(feature + "=")
            ):

                cleaned[feature] += value
                break

    return cleaned


preprocessors = {

    "M1_Occupancy": None,

    "M2_Vibration": None,

    "M3_Energy": model3_scaler_x,

    "M4_Activity": model4_scaler,

    "M5_Anomaly": model5_scaler,

    "M6_Threat": model6_scaler

}

df_copy = train_full.copy()

df_copy = df_copy.rename(columns={

    "M1_Occupancy": "occupancy_true",

    "M2_Vibration": "event_type_predicted",

    "M3_Energy": "total_energy",

    "M4_Activity": "activity",

    "M5_Anomaly": "anomaly",

    "M6_Threat": "threat"

})




def get_lime_weights(
    model_name,
    sample,
    graph,
    explainer_dict,
    preprocessor=None
):

    # =========================================================
    # 1. MODEL INFORMATION
    # =========================================================

    node = graph[model_name]
    model = node["model"]
    model_type = model_types[model_name]

    # =========================================================
    # 2. LIME INFORMATION
    # =========================================================

    lime_info = explainer_dict[model_name]
    explainer = lime_info["explainer"]
    input_names = lime_info["input_names"]
    categorical_features = lime_info["categorical_features"]
    categorical_names = lime_info["categorical_names"]

    # =========================================================
    # 3. SAMPLE
    # =========================================================

    if isinstance(sample, pd.Series):
        sample_df = sample.to_frame().T
    else:
        sample_df = pd.DataFrame(sample)
    sample_df = sample_df[input_names].copy()

    # =========================================================
    # 4. CONVERT ORIGINAL SAMPLE -> LIME REPRESENTATION
    # =========================================================

    X = []

    for i, feature in enumerate(input_names):

        value = sample_df.iloc[0][feature]

        # -----------------------------------------------------
        # categorical feature
        # -----------------------------------------------------

        if i in categorical_features:

            categories = categorical_names[i]

            value_string = str(value)

            if value_string not in categories:

                raise ValueError(
                    f"Unknown categorical value '{value}' "
                    f"for feature '{feature}' in {model_name}.\n"
                    f"Expected one of: {categories}"
                )

            value = categories.index(value_string)


        # -----------------------------------------------------
        # numerical feature
        # -----------------------------------------------------

        else:

            value = float(value)

        X.append(value)

    X = np.asarray(X, dtype=float)


    # =========================================================
    # 5. LIME -> MODEL CONVERSION
    # =========================================================

    def lime_to_model_dataframe(X_lime):

        X_lime = np.asarray(X_lime)

        rows = []

        for row in X_lime:

            values = []

            for i, value in enumerate(row):

                feature = input_names[i]

                # ---------------------------------------------
                # categorical
                # ---------------------------------------------

                if i in categorical_features:

                    categories = categorical_names[i]


                    category_index = int(
                        np.clip(
                            np.round(value),
                            0,
                            len(categories) - 1
                        )
                    )

                    original_value = categories[
                        category_index
                    ]

                    values.append(original_value)

                # ---------------------------------------------
                # numerical
                # ---------------------------------------------

                else:

                    values.append(float(value))

            rows.append(values)



        return pd.DataFrame(
            rows,
            columns=input_names
        )

    # =========================================================
    # 6. MODEL PREDICTION FUNCTION
    # =========================================================

    def predict_fn(X_lime):
        import numpy as np

        X_model = lime_to_model_dataframe(X_lime)

        # 1. Βίαιη συμπλήρωση των 14 στηλών απευθείας από το sample
        expected_cols = list(sample.columns) if hasattr(sample, 'columns') else list(sample.index)
        
        for col in expected_cols:
            if col not in X_model.columns:
                if hasattr(sample, 'columns'):
                    X_model[col] = sample[col].iloc[0]
                else:
                    X_model[col] = sample[col]
                    
        X_model = X_model[expected_cols]

        # 2. One-hot expand
        if model_name == "M4_Activity" and "event_type" in X_model.columns:
            dummies = pd.get_dummies(X_model["event_type"].astype(str), prefix="event")
            X_model = pd.concat([X_model.drop(columns=["event_type"]), dummies], axis=1)
            X_model = X_model.reindex(columns=model4_feature_names, fill_value=0.0)

        elif model_name == "M6_Threat" and "predicted_activity_model" in X_model.columns:
            dummies = pd.get_dummies(X_model["predicted_activity_model"].astype(str), prefix="activity")
            X_model = pd.concat([X_model.drop(columns=["predicted_activity_model"]), dummies], axis=1)
            X_model = X_model.reindex(columns=model6_feature_names, fill_value=0.0)

        else:
            for col in X_model.columns:
                if X_model[col].dtype == object or isinstance(X_model[col].iloc[0], str):
                    X_model[col] = X_model[col].astype('category').cat.codes

        X_model = X_model.astype(float)

        # 3. Κανονικοποίηση
        if preprocessor is not None:
            X_model = preprocessor.transform(X_model)

        # 4. LSTM Reshape
        if model_name == "M3_Energy":
            X_model_np = X_model.to_numpy() if hasattr(X_model, 'to_numpy') else X_model
            X_model = np.repeat(
                X_model_np[:, np.newaxis, :],
                12,
                axis=1
            ).reshape(-1, 12, 5)

        # 5. Τελική Πρόβλεψη (Διαχωρισμός Classification / Regression)
        if model_type == "classification":
            
            if hasattr(model, "predict_proba"):
                return model.predict_proba(X_model)
            elif model_name == "M5_Anomaly":
                # Το IsolationForest δεν δέχεται verbose και επιστρέφει -1 ή 1
                preds = model.predict(X_model)
                probs = np.zeros((len(preds), 2))
                probs[preds == -1, 0] = 1.0  # -1 (Ανωμαλία)
                probs[preds == 1, 1] = 1.0   # 1 (Φυσιολογικό)
                return probs
            else:
                # Νευρωνικά δίκτυα Keras
                preds = model.predict(X_model, verbose=0)
                if preds.shape[1] == 1:
                    preds = np.hstack([1 - preds, preds])
                return preds

        elif model_type == "regression":
            prediction = model.predict(X_model)
            return np.asarray(prediction)

        else:
            raise ValueError(f"Unknown model type: {model_type}")

    # =========================================================
    # 7. RUN LIME
    # =========================================================

    if model_type == "classification":

        probabilities = predict_fn(
            X.reshape(1, -1)
        )

        predicted_index = int(
            np.argmax(probabilities[0])
        )

        # -----------------------------------------------------
        # Get class label
        # -----------------------------------------------------

        if hasattr(model, "classes_"):

            predicted_class = model.classes_[
                predicted_index
            ]

        else:

            # For models such as Keras,
            # use LIME's categorical class names
            predicted_class = predicted_index

        # -----------------------------------------------------
        # Explain predicted class
        # -----------------------------------------------------

        explanation = explainer.explain_instance(
            X,
            predict_fn,
            num_features=len(input_names),
            labels=[predicted_index]
        )

        lime_map = explanation.as_map()[
            predicted_index
        ]

        prediction = predicted_class

    # =========================================================
    # 8. REGRESSION
    # =========================================================

    else:

        explanation = explainer.explain_instance(
            X,
            predict_fn,
            num_features=len(input_names)
        )

        #labels = explanation.available_labels()

        #label = labels[0]

        lime_map = explanation.as_map()[0] #[label]


        prediction = predict_fn(
            X.reshape(1, -1)
        )[0]

        predicted_class = None

    # =========================================================
    # 9. FEATURE -> WEIGHT
    # =========================================================

    weights = {}

    for feature_index, weight in lime_map:

        feature_name = input_names[
            feature_index
        ]

        weights[feature_name] = float(weight)

    return (
        weights,
        prediction,
        predicted_class
    )


# Initialize raw feature score vector to 0
raw_scores = {feat: 0.0 for feat in raw_features}

def recursive_lime_explain(model_name, sample_index, graph, explainer_dict, scale=1.0):

    """
    Recursive LIME explanation for stacked models.

    Parameters:
    - model_name: current model node to explain
    - sample: dict {raw_feature_name: value}
    - graph: dict of models with input_names and input_sources
    - explainer_dict: LimeTabularExplainer for each model
    - full_scores: dict to accumulate all features
    - raw_scores: dict to accumulate raw features only
    - scale: scaling factor from downstream contribution
    """
    # 1. Initiate params
    node = graph[model_name]
    model = node["model"]
    input_names = node["input_names"]
    input_sources = node["input_sources"]


    # 2. Run LIME explanation
    missing_cols = [c for c in input_names if c not in train_full.columns]
    for c in missing_cols:
            if 'df' in globals() and c in df.columns:
                train_full[c] = df[c]
            else:
                train_full[c] = 0.0
                
    sample = train_full.iloc[sample_index][input_names]
    explainer = explainer_dict[model_name]
    lime_exp, _, _ = get_lime_weights(model_name, sample, graph, explainer_dict, preprocessors[model_name])

    print(lime_exp)

    # 3. Calculate importance scores
    for f in input_names:
      if input_sources[f]==None:
        raw_scores[f] += scale * lime_exp[f]
      else:
        recursive_lime_explain(input_sources[f], sample_index, graph, explainer_dict, scale=lime_exp[f])


# Initialize raw feature score vector to 0



current_index = 12

def on_message(client, userdata, msg):
    global current_index
    global raw_scores
    
    topic = msg.topic
    payload = msg.payload.decode().strip()
    
    if topic == "home/simulation/current_row":
        try:
            current_index = int(payload)
        except ValueError:
            pass
        return

    if topic == "home/commands/run_xai":
        model_mapping = {
            "Occupancy Model": "M1_Occupancy",
            "Vibration Model": "M2_Vibration",
            "Energy Model": "M3_Energy",
            "Activity Recognition": "M4_Activity",
            "Anomaly Detection": "M5_Anomaly",
            "Threat Assessment": "M6_Threat"
        }
        
        target_model = model_mapping.get(payload, payload)
        
        if target_model not in graph:
            print(f"Ignored message. '{payload}' is not a valid model.")
            return

        print(f"\nStarting LIME analysis for: {target_model}")
        
        raw_scores = {feat: 0.0 for feat in raw_features}
        
        recursive_lime_explain(target_model, current_index, graph, explainer_dict)

        script_dir = os.path.dirname(os.path.abspath(__file__))
        www_path = os.path.join(script_dir, "ha_config", "www", "xai_plots")
        os.makedirs(www_path, exist_ok=True)
        
        svg_filename = os.path.join(www_path, f"{target_model}_explanations.svg")

        filtered_scores = {k: v for k, v in raw_scores.items() if abs(v) > 0.0}

        fixed_items = sorted(filtered_scores.items(), key=lambda x: abs(x[1]))
        
        features = [k for k, v in fixed_items]
        scores = [v for k, v in fixed_items]
        colors = ['green' if x > 0 else 'red' for x in scores]

        plt.figure(figsize=(12, 10), facecolor='white')
        ax = plt.gca()
        ax.set_facecolor('white')
        
        bars = plt.barh(features, scores, color=colors)
        
        for bar in bars:
            width = bar.get_width()
            if abs(width) > 0.0001:
                max_score = max([abs(s) for s in scores]) if any(scores) else 1
                x_offset = 0.01 * max_score if width > 0 else -0.01 * max_score
                ha = 'left' if width > 0 else 'right'
                plt.text(width + x_offset, bar.get_y() + bar.get_height()/2, f'{width:.6f}', 
                         va='center', ha=ha, color='black', fontsize=11)

        plt.axvline(0, color='#1f77b4', linewidth=1.5)
        plt.title(f"TRACE-XAI Explanation - {target_model}", color='black', fontsize=14)
        plt.tick_params(axis='x', colors='black', labelsize=10)
        plt.tick_params(axis='y', colors='black', labelsize=12)
        
        x_min, x_max = plt.xlim()
        plt.xlim(x_min - abs(x_min)*0.2, x_max + abs(x_max)*0.2)
        
        plt.tight_layout()
        plt.savefig(svg_filename, format="svg", facecolor='white', edgecolor='none')
        plt.close()

        raw_prediction = train_full.iloc[current_index][target_model]
        print(f"\nI ask for explaination from llm for the model: {target_model}...")
        llm_answer = generate_llm_answer(target_model, str(raw_prediction), filtered_scores)
        print(f"LLM answer: {llm_answer}")
        payload = json.dumps({"explanation": llm_answer})
        client.publish(f"home/xai/{target_model}/llm_answer", payload, retain=True)
        print(f"Sent to MQTT topic: home/xai/{target_model}/llm_answer\n")

        client.publish(
            f"home/security/xai/{target_model}",
            json.dumps({"model": target_model, "row": current_index, "scores": raw_scores})
        )
        print(f"Plot saved successfully at: {svg_filename}")

mqtt_client = mqtt.Client()
mqtt_client.on_message = on_message

print(f"Connecting to MQTT Broker: {BROKER}...")
mqtt_client.connect(BROKER, 1883, 60)
mqtt_client.subscribe("home/commands/run_xai")
mqtt_client.subscribe("home/simulation/current_row")

print("XAI Daemon is running...")
mqtt_client.loop_forever()


### raw_scores contains the final explanations

