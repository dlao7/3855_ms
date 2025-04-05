"""
Receiver service to accept event entries from post requests
and publish them to a Kafka queue.
"""
import os
from datetime import datetime as dt
import json
import logging.config
import uuid

import connexion
from connexion import NoContent
import yaml
from connexion.middleware import MiddlewarePosition
from starlette.middleware.cors import CORSMiddleware

from wrapper import KafkaWrapper

# Endpoint configuration
with open("config/receiver.prod.yaml", "r", encoding="utf-8") as f:
    app_config = yaml.safe_load(f.read())

# Logging
with open("logger/log.prod.yaml", "r", encoding="utf-8") as f:
    log_config = yaml.safe_load(f.read())
    logging.config.dictConfig(log_config)

logger = logging.getLogger("basicLogger")

def make_log(event_type, trace_id):
    """Creates log for events with type and trace ID."""
    logger.info("Received event %s with a trace id of %s", event_type, trace_id)

kafka_wrapper = KafkaWrapper(
    f"{app_config['events']['hostname']}:{app_config['events']['port']}", b"events"
)

# Endpoints
def report_attraction_info(body):
    """Recieves JSON from post request and attaches attraction type and time received
    and publishes this message to the Kafka queue.

    Parameters:
    body (JSON): contains attraction event information including user id, attraction
    category, attraction time stamp and hours open.

    Example body:
      {
      "user_id": "fa2e2624-daff-43c3-82cd-c1ced1095ccd",
      "attraction_category": "Test",
      "hours_open": 5,
      "attraction_timestamp": "2030-07-08 21:00:49"
      }

    Returns: None
    """
    body["trace_id"] = str(uuid.uuid4())
    make_log("attraction_info", body["trace_id"])

    msg = {
        "type": "attraction_info",
        "datetime": dt.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "payload": body,
    }
    msg_str = json.dumps(msg)

    kafka_wrapper.produce_msg(msg_str)

    logger.info("Attraction Event posted to Kafka with trace_id %s.", body["trace_id"])

    return NoContent, 201


def report_expense_info(body):
    """Receives JSON from post request and attaches expense type and time received
    and publishes this message to the Kafka queue.

    Parameters:
    body (JSON): contains expense event information including user id, expense
    category, expense time stamp and amount.

    Example body:
      {
      "user_id": "fa2e2624-daff-43c3-82cd-c1ced1095ccd",
      "amount": 55.00,
      "expense_category": "Test",
      "expense_timestamp":"2025-07-08 21:00:49"
      }

    Returns: None
    """
    body["trace_id"] = str(uuid.uuid4())
    make_log("expense_info", body["trace_id"])

    msg = {
        "type": "expense_info",
        "datetime": dt.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "payload": body,
    }
    msg_str = json.dumps(msg)

    kafka_wrapper.produce_msg(msg_str)

    logger.info("Expense Event posted to Kafka with trace_id %s.", body["trace_id"])

    return NoContent, 201


app = connexion.FlaskApp(__name__, specification_dir="")
app.add_api("receiver.yaml", base_path="/receiver", strict_validation=True, validate_responses=True)

if "CORS_ALLOW_ALL" in os.environ and os.environ["CORS_ALLOW_ALL"] == "yes":
    app.add_middleware(
        CORSMiddleware,
        position=MiddlewarePosition.BEFORE_EXCEPTION,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


if __name__ == "__main__":
    app.run(port=8080, host="0.0.0.0")
