# Home Assistant UI & TRACE-XAI 

## Project Overview & Architecture

This project implements a transparent, AI-driven Smart Home Security system by integrating Explainable AI (XAI) directly into Home Assistant. The backend consists of a Python pipeline that processes data across six specialized Machine Learning models (Occupancy, Vibration, Energy, Activity, Anomaly, and Threat). 

To ensure these automated decisions are understandable, the system utilizes **LIME** to extract local feature importance scores for every prediction. These raw metrics are dynamically processed by a **LLM** (via the Groq API) to generate simple explanations. Finally, all XAI insights,including visual LIME charts and the LLM-generated text,are published via **MQTT** to a custom Home Assistant dashboard, providing the user with real-time, context-aware security monitoring.

![Home Assistant XAI Dashboard](images/HA_prot.jpg)

## Requirements
* Home Assistant
* MQTT Broker (e.g., Mosquitto)
* Python 3.10+

---
The following steps are for creating the ui from scratch if you want, training the models etc. If you don't: 
1. Download the files and folders from this repo as it is
2. Execute steps 1.2, 5 through 9, 10.3 through 10.5, 12, 13 and 14.
### Step 1: 
1. Create a main folder and add `requirements.txt`, `home_security_xai.py`, `mqtt_csv_simulator.py`, `mqtt_models.py` and `train_models.py` in it (Add to that folder your home assistant config folder as well).
2. Open a terminal inside that folder and run `pip install -r requirements.txt`.

### Step 2: 
1. Copy the `custom_components/model_relationships` folder from this repository into your Home Assistant `config/custom_components` directory.

### Step 3: 
1. Copy `model-relationship-card.js` from this repository's `www` folder into your Home Assistant `config/www` directory. *(Create the `www` folder in your config directory if you don't already have one).*

### Step 4: 
1. Copy the `model_relationships_data.json` file from this repository directly into your main Home Assistant `config` directory.

### Step 5: 
1. Open your `configuration.yaml` file.
2. Paste the provided `sensor:`, `input_boolean:`,`mqtt:` blocks and the `model_relationships:` line as well (Necessary for loading the custom card).

### Step 6: 
1. Navigate to **Developer Tools > YAML** and click **Check Configuration** to ensure your code is valid.
2. Click **Restart**. 

### Step 7: 
1. Go to **Settings > Dashboards**, click the three dots in the top right, and select **Resources**.
2. Click **Add Resource**.
3. Set the **URL** to `/local/model-relationship-card.js`.
4. Set the **Resource Type** to **JavaScript Module**.

### Step 8: Configure MQTT Integration
1. Go to **Settings > Devices & Services**.
2. Click **Add Integration** (bottom right).
3. Search for and select **MQTT**.
4. Fill in the connection form:
   * **Broker:** Enter the Host machine's local IP address *(Do not use `localhost` if running in separate containers).*
   * **Port:** `1883`
   * **Username / Password:** Enter your Mosquitto broker credentials (leave blank if your `mosquitto.conf` permits anonymous access).
5. Click **Submit**.

### Step 9: Setup Dashboard
1. Go to your **Overview** dashboard or create a new one and click the **pencil icon** (Edit) in the top right corner.
2. Click the **three dots** in the top right and select **Raw configuration editor**.
3. Paste the provided raw text code from the RAW_CONFIGURATION file and click **Save**..

### Step 10: Train the Models & Run the Simulator
1. Before running the simulator, you must train the 6-models. Ensure `threat_smart_home_data.csv` is in the same folder as the train_models.py file, open a terminal, and run `python train_models.py`.
2. Wait for the script to complete its evaluation and verify that all the generated models have been successfully saved in your folder.
3. Open `mqtt_csv_simulator.py`.
4. Update the `BROKER_ADDRESS` variable with the IP address of your machine running your MQTT broker. 
5. Run `python mqtt_csv_simulator.py` to start sending data to the models.

### Step 11: Running the XAI (Data Preparation)
Since you are running the project for the first time, you need to generate the LIME background distribution file (`trace_xai_train_full.pkl`):
1. Ensure the `threat_smart_home_data.csv` file (or yours) is in your main folder.
2. Open the XAI script (`home_security_xai.py`).
3. Locate the commented-out lines responsible for data preprocessing and generating the pickle file (Lines 934 - 1131).
4. **Uncomment** these lines, paying special attention to configure the path in the save and reading commands: 
   `train_full.to_pickle(r"path_where_ths_code_is/trace_xai_train_full.pkl")`, `train_full = pd.read_pickle(r"path_where_ths_code_is/trace_xai_train_full.pkl")`.
5. After the file `trace_xai_train_full.pkl` is successfully created, comment out the same lines.

## Step 12: LLM Explanations Setup 

This project uses the Groq API (running the `groq/compound-mini` model) to generate natural language explanations for the AI models' decisions. To enable this feature, you need to provide a Groq API Key.

**Note:** If no API key is provided, the script will not crash. 

   ### How to set up your API Key
   1. **Get a Free Key**: Go to [console.groq.com](https://console.groq.com/), create a free account, and generate a new API Key.
   2. You must update variable named `GROQ_API_KEY` in home_security_xai.py file with your API key.


### Step 13: Configure and Run the XAI Script 
1. Update the `BROKER` variable with the IP address of your MQTT broker.
2. Update the `CSV_PATH` and `MODEL_DIR` variables with the absolute paths to your data and models.
3. **CRITICAL:** This file must be in the main folder that contains the ha_config folder to successfully update the plots. 
4. In order for the code to run with no errors add to the `ha_config\www\xai_plots` folder the .svg files provided, otherwise run the code and press the xai button for each model and then proceed to step 13. (If you don't have the xai_plots folder, create it).
5. Open a new terminal in your main folder and run `python home_security_xai.py`. 


### Step 14: Configure Local File Integration
Now that the XAI plots exist in your `www` folder, you can set them up in Home Assistant:
1. Go to **Settings > Devices & Services**.
2. Click **Add Integration** and search for **Local File**.
3. Add a separate entry for each XAI plot (e.g., *Xai Activity Plot*, *Xai Anomaly Plot*, *Xai Energy Plot*, *Xai Occupancy Plot*, *Xai Threat Plot*, and *Xai Vibration Plot*).
4. For each entry, provide the exact path to the generated `.svg` files:
   * `/config/www/xai_plots/M1_Occupancy_explanations.svg`
   * `/config/www/xai_plots/M2_Vibration_explanations.svg`
   * `/config/www/xai_plots/M3_Energy_explanations.svg`
   * `/config/www/xai_plots/M4_Activity_explanations.svg`
   * `/config/www/xai_plots/M5_Anomaly_explanations.svg`
   * `/config/www/xai_plots/M6_Threat_explanations.svg`

