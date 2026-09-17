import paho.mqtt.client as mqtt
import csv
import time
from mqtt_models import Model, run_pipeline

BROKER_ADDRESS = "your_ip"
CSV_FILENAME = "filename.csv"
ROW_INTERVAL_SECONDS = 7

TOPIC_MAPPING = {
    "time_of_day": "home/sensors/time_of_day",
    "temperature": "home/sensors/temperature",
    "humidity": "home/sensors/humidity",
    "co2": "home/sensors/co2",
    "light": "home/sensors/light",
    "PIR": "home/sensors/pir",
    "door_state": "home/sensors/door_state",
    "outdoor_temperature": "home/sensors/outdoor_temperature",
    "smoke_level": "home/sensors/smoke_level",
    "occupant_count": "home/sensors/occupant_count",
    "vibration_rms": "home/sensors/vibration_rms",
    "peak_acceleration": "home/sensors/peak_acceleration",
    "dominant_frequency": "home/sensors/dominant_frequency",
    "spectral_energy": "home/sensors/spectral_energy",
    "spectral_entropy": "home/sensors/spectral_entropy",
    "vibration_duration": "home/sensors/vibration_duration",
    "acceleration_x": "home/sensors/accel_x",
    "acceleration_y": "home/sensors/accel_y",
    "acceleration_z": "home/sensors/accel_z",
    "Plug 1 energy": "home/sensors/plug_1_energy",
    "plug 2 energy": "home/sensors/plug_2_energy",
    "cumulative energy": "home/sensors/cumulative_energy",
    "actual_consumption": "home/sensors/actual_consumption",
}

GROUND_TRUTH_COLUMNS = {
    "occupant_presence",
    "event_type",
    "predicted_activity",
    "anomaly_true",
    "threat_type",
}

PIPELINE = [
    Model(
        name="Occupancy Estimation",
        model_path="occupancy_random_forest.joblib",
        input_keys=["temperature", "humidity", "co2", "light", "PIR"],
        output_key="occupant_presence",
        output_topic="home/predictions/occupant_presence"
    ),
    Model(
        name="Vibration Analysis",
        model_path="vibration_gradient_boosting.joblib",
        input_keys=["vibration_rms", "peak_acceleration", "dominant_frequency", "spectral_energy", "spectral_entropy", "vibration_duration", "acceleration_x", "acceleration_y", "acceleration_z", "occupant_presence"],
        output_key="event_type",
        output_topic="home/predictions/event_type",
        output_encoder_path="event_type_encoder.joblib"
    ),
    Model(
        name="Energy Consumption (LSTM)",
        model_path="energy_lstm.keras",
        input_keys=["temperature", "humidity", "co2", "light", "occupant_presence"],
        output_key="predicted_consumption",
        output_topic="home/predictions/predicted_consumption",
        scaler_path="energy_scaler_x.joblib",
        output_scaler_path="energy_scaler_y.joblib",
        window_size=12
    ),
    Model(
        name="Activity Recognition",
        model_path="activity_recognition_nn.keras",
        input_keys=["occupant_count", "PIR", "outdoor_temperature", "light", "predicted_consumption", "time_of_day", "door_state"],
        output_key="predicted_activity",
        output_topic="home/predictions/predicted_activity",
        feature_names_path="har_feature_names.joblib",
        scaler_path="har_scaler.joblib",
        one_hot_configs={"event_type": "event_"},
        output_encoder_path="activity_encoder.joblib",
        needs_argmax=True
    ),
    Model(
        name="Anomaly Detection",
        model_path="anomaly_isolation_forest.joblib",
        input_keys=["actual_consumption", "predicted_consumption", "event_type", "temperature", "humidity", "PIR", "door_state", "time_of_day"],
        output_key="anomaly_pred",
        output_topic="home/predictions/anomaly",
        scaler_path="anomaly_scaler.joblib",
        input_label_col="event_type",
        input_label_encoder_path="anomaly_event_encoder.joblib",
        is_anomaly_model=True
    ),
    Model(
        name="Threat Assessment",
        model_path="threat_assessment_nn.keras",
        input_keys=["PIR", "predicted_consumption", "actual_consumption", "anomaly_pred", "door_state", "smoke_level", "co2", "time_of_day", "outdoor_temperature", "temperature"],
        output_key="threat_type",
        output_topic="home/predictions/threat_type",
        feature_names_path="threat_feature_names.joblib",
        scaler_path="threat_scaler.joblib",
        one_hot_configs={"predicted_activity": "activity_"},
        output_encoder_path="threat_encoder.joblib",
        needs_argmax=True
    )
]

print("\n--- Loading ML Models ---")
for _model in PIPELINE:
    _model.load()

client = mqtt.Client()

try:
    print(f"Connecting to MQTT Broker: {BROKER_ADDRESS}...")
    client.connect(BROKER_ADDRESS, 1883, 60)
    print("Connected!")

    with open(CSV_FILENAME, mode='r', encoding='utf-8') as file:
        csv_reader = csv.DictReader(file)

        for index, row in enumerate(csv_reader):
            client.publish("home/simulation/current_row", str(index))
            
            print("-" * 30)
            if "timestamp" in row:
                print(f"Timestamp: {row['timestamp']}")

            for column_name, value in row.items():
                if column_name == "timestamp" or column_name in GROUND_TRUTH_COLUMNS:
                    continue
                topic = TOPIC_MAPPING.get(column_name)
                if topic is not None:
                    client.publish(topic, str(value))
                    print(f"[{topic}] -> {value}")

            values = dict(row)
            for gt_col in GROUND_TRUTH_COLUMNS:
                values.pop(gt_col, None)

            run_pipeline(PIPELINE, values)

            for model in PIPELINE:
                if model.output_key in values:
                    prediction = values[model.output_key]
                    client.publish(model.output_topic, str(prediction))
                    print(f"[PREDICT] {model.name} -> [{model.output_topic}] {prediction}")

            time.sleep(ROW_INTERVAL_SECONDS)

    print("\nEnd of simulation")

except FileNotFoundError:
    print(f"\nError: The file '{CSV_FILENAME}' wasn't found! Make sure it's in the same folder.")
except KeyboardInterrupt:
    print("\nUser Interrupt (Ctrl+C). Ending simulator...")
except Exception as e:
    print(f"\nError: {e}")
finally:
    client.disconnect()