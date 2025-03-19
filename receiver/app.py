import connexion
from connexion import NoContent
import logging.config
import uuid
import yaml
import json
from datetime import datetime as dt
from pykafka import KafkaClient

# Endpoint configuration
with open("config/receiver.prod.yaml", "r") as f:
    app_config = yaml.safe_load(f.read())

# Logging
with open("logger/log.prod.yaml", "r") as f:
    log_config = yaml.safe_load(f.read())
    logging.config.dictConfig(log_config)

logger = logging.getLogger("basicLogger")


def make_log(event_type, trace_id):
    logger.info(f"Received event {event_type} with a trace id of {trace_id}")


# Kafka variables
client = KafkaClient(
    hosts=f"{app_config["events"]["hostname"]}:{app_config["events"]["port"]}"
)
topic = client.topics[str.encode(f"{app_config["events"]["topic"]}")]
producer = topic.get_sync_producer()


# Endpoints
def report_attraction_info(body):
    body["trace_id"] = str(uuid.uuid4())
    make_log("attraction_info", body["trace_id"])

    msg = {
        "type": "attraction_info",
        "datetime": dt.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "payload": body,
    }
    msg_str = json.dumps(msg)
    producer.produce(msg_str.encode("utf-8"))
    logger.info(f"Attraction Event posted to Kafka with trace_id {body["trace_id"]}.")

    return NoContent, 201


def report_expense_info(body):
    body["trace_id"] = str(uuid.uuid4())
    make_log("expense_info", body["trace_id"])

    msg = {
        "type": "expense_info",
        "datetime": dt.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "payload": body,
    }
    msg_str = json.dumps(msg)
    producer.produce(msg_str.encode("utf-8"))
    logger.info(f"Expense Event posted to Kafka with trace_id {body["trace_id"]}.")

    return NoContent, 201


app = connexion.FlaskApp(__name__, specification_dir="")
app.add_api("receiver.yaml", strict_validation=True, validate_responses=True)


if __name__ == "__main__":
    app.run(port=8080, host="0.0.0.0")
