import os
import time
import json
import logging.config
from threading import Thread

import connexion
from connexion import NoContent
import yaml
from pykafka import KafkaClient

# App Config
with open("config/anomaly.prod.yaml", "r", encoding="utf-8") as f:
    app_config = yaml.safe_load(f.read())

# Logging
with open("logger/log.prod.yaml", "r", encoding="utf-8") as f:
    log_config = yaml.safe_load(f.read())
    logging.config.dictConfig(log_config)

logger = logging.getLogger("basicLogger")

# Kafka Client Settings
HOST_NAME = f"{app_config['events']['hostname']}:{app_config['events']['port']}"
client = KafkaClient(hosts=HOST_NAME)
topic = client.topics[str.encode(f"{app_config['events']['topic']}")]

def update_anomalies():
    logger.debug("Request to update anomalies process started.")
    start_time = time.time()

    # read from kafka queue
    consumer = topic.get_simple_consumer(
        reset_offset_on_start=True, consumer_timeout_ms=1000
    )

    anomalies = []

    for msg in consumer:
        msg_str = msg.value.decode("utf-8")
        msg = json.loads(msg_str)

        # find events with anomalies (based on env variable threshold)
        if msg["type"] == "attraction_info":
            if msg["payload"]["hours_open"] < int(os.environ["MIN_HOURS"]):
                anom_info = {
                    "user_id": msg["payload"]["user_id"],
                    "trace_id": msg["payload"]["trace_id"],
                    "event_type": "attraction_info",
                    "anomaly_type": "Too Low",
                    "description": f"Detected: {msg["payload"]["hours_open"]}; too low (threshold {os.environ["MIN_HOURS"]})"
                }
                logger.debug(f"Detected: {msg["payload"]["hours_open"]}; too low (threshold {os.environ["MIN_HOURS"]})")
                anomalies.append(anom_info)
        else:
            if msg["payload"]["amount"] > int(os.environ["MAX_PRICE"]):
                anom_info = {
                    "user_id": msg["payload"]["user_id"],
                    "trace_id": msg["payload"]["trace_id"],
                    "event_type": "expense_info",
                    "anomaly_type": "Too High",
                    "description": f"Detected: {msg["payload"]["amount"]}; too high (threshold {os.environ["MAX_PRICE"]})"
                }
                logger.debug(f"Detected: {msg["payload"]["amount"]}; too high (threshold {os.environ["MAX_PRICE"]})")
                anomalies.append(anom_info)

    # update the json with the anomaly info
    with open(app_config["datastore"]["filepath"], "w", encoding="utf-8") as w:
        json.dump(anomalies, w, indent=4)

    end_time = time.time()
    # calculate processing time
    elapsed_time = round((end_time - start_time) * 1000)

    logger.info(
        f"Update anomalies process completed | processing_time_ms={elapsed_time}"
        f" | anomalies found = {len(anomalies)}"
    )

    # returns anomalies_count, as an object, { anomalies_count: 1000 }
    return { "anomalies_count": len(anomalies) }, 200

def get_anomalies(event_type=None):
    logger.debug("Request to get anomalies received")
    # wrong event type - return 400
    if event_type not in ["attraction_info", "expense_info"]:
        return 400

    # load json
    try:
        with open(
            app_config["datastore"]["filepath"], "r", encoding="utf-8"
        ) as read_content:
            anom_file = json.load(read_content)
    except FileNotFoundError:
        logger.error("The Anomalies file does not exist.")
        return {"message": "The anomalies datastore is missing or corrupted."}, 404
    except IOError:
        logger.error("An error occurred while reading the anomaly file.")
        return {"message": "The anomalies datastore is corrupted."}, 404

    # no anomalies - return empty response, 204
    if len(anom_file) == 0:
        logger.debug("Anomalies Response returned: No anomalies found in file.")
        return NoContent, 204

    # no event type - return all, or filter
    if event_type == None and len(anom_file) != 0:
        logger.debug("Anomalies Response returned: All anomalies returned.")
        return anom_file, 200
    else:
        logger.debug(f"Anomalies Response returned: {event_type} entries returned.")
        return [ entry for entry in anom_file if entry["event_type"] == event_type ], 200

def setup_kafka_thread():
    """Creates threads for single event extraction from Kafka queue."""
    t1 = Thread(target=update_anomalies)
    t1.daemon = True

    t1.start()

app = connexion.FlaskApp(__name__, specification_dir="")
app.add_api("anomaly.yaml", base_path="/anomaly", strict_validation=True, validate_responses=True)

if __name__ == "__main__":
    logger.info(f"The thresholds are min hours {os.environ["MIN_HOURS"]} and max price {os.environ["MAX_PRICE"]}.")
    setup_kafka_thread()
    app.run(port=8400, host="0.0.0.0")