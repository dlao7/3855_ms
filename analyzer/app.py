"""
Analyzer service to gather individual messages,
event counts and event ids from the Kafka queue.
"""

import os
import json
import logging.config
from threading import Thread

import connexion
import yaml

# from pykafka import KafkaClient
from connexion.middleware import MiddlewarePosition
from starlette.middleware.cors import CORSMiddleware

from wrapper import KafkaWrapper

# App Config
with open("config/analyzer.prod.yaml", "r", encoding="utf-8") as f:
    app_config = yaml.safe_load(f.read())

# Logging
with open("logger/log.prod.yaml", "r", encoding="utf-8") as f:
    log_config = yaml.safe_load(f.read())
    logging.config.dictConfig(log_config)

logger = logging.getLogger("basicLogger")


kafka_attr = KafkaWrapper(
    "get_attr",
    f"{app_config['events']['hostname']}:{app_config['events']['port']}",
    b"events",
)
kafka_exp = KafkaWrapper(
    "get_exp",
    f"{app_config['events']['hostname']}:{app_config['events']['port']}",
    b"events",
)
kafka_stats = KafkaWrapper(
    "get_event_stats",
    f"{app_config['events']['hostname']}:{app_config['events']['port']}",
    b"events",
)
kafka_ids = KafkaWrapper(
    "get_event_ids",
    f"{app_config['events']['hostname']}:{app_config['events']['port']}",
    b"events",
)


def get_attr(index):
    """Gets Attraction Event Message at an Index

    Parameters:
    index (int): Index of the attraction event

    Returns:
    Message that matches the index, or 404 if there is no message at that index.
    """

    counter = 0
    found = False

    for msg in kafka_attr.messages():
        msg_str = msg.value.decode("utf-8")
        msg = json.loads(msg_str)

        if msg["type"] == "attraction_info":
            if counter == index:
                logger.info("Attraction Message found at index %s", index)
                found = True
                found_msg = msg["payload"]
                break

            counter += 1

    kafka_attr.consumer.reset_offsets()

    if found == True:
        return found_msg, 200
    else:
        return {"message": f"No attraction message at index {index}!"}, 404


def get_exp(index):
    """Gets Expense Event Message at an Index

    Parameters:
    index (int): Index of the expense event

    Returns:
    Message that matches the index, or 404 if there is no message at that index.
    """

    counter = 0
    found = False

    for msg in kafka_exp.messages():
        msg_str = msg.value.decode("utf-8")
        msg = json.loads(msg_str)

        if msg["type"] == "expense_info":
            if counter == index:
                logger.info("Expense Message found at index %s", index)
                found = True
                found_msg = msg["payload"]
                break

            counter += 1

    kafka_exp.consumer.reset_offsets()

    if found == True:
        return found_msg, 200
    else:
        return {"message": f"No expense message at index {index}!"}, 404


def get_event_stats():
    """Gets the numbers of each event in the queue

    Returns:
    A dictionary with the numbers of each event

    Example:
    {
        "num_attr": 10,
        "num_exp": 10,
    }
    """
    logger.info("Request received to get number of event type in queue.")

    attr_counter = 0
    exp_counter = 0

    for msg in kafka_stats.messages():
        msg_str = msg.value.decode("utf-8")
        msg = json.loads(msg_str)

        if msg["type"] == "attraction_info":
            attr_counter += 1
        else:
            exp_counter += 1

    kafka_stats.consumer.reset_offsets()

    logger.info("Request completed to get number of event type in queue.")

    return {
        "num_attr": attr_counter,
        "num_exp": exp_counter,
    }, 200


def get_event_ids():
    """Gets the user and trace ids for events in queue

    Returns:
    A list of dictionaries with the user and trace ids for
    each event in the queue

    Example:
    [ {"user_id": "XXXX", "trace_id": "XXXX"}, {"user_id": "XXXX", "trace_id": "XXXX"} ]
    """

    all_entries = []

    for msg in kafka_ids.messages():
        msg_str = msg.value.decode("utf-8")
        msg = json.loads(msg_str)

        event_id = {
            "user_id": msg["payload"]["user_id"],
            "trace_id": msg["payload"]["trace_id"],
            "type": msg["type"],
        }
        all_entries.append(event_id)

    kafka_ids.consumer.reset_offsets()

    logger.info("%s entry ids found.", len(all_entries))

    return all_entries, 200


def setup_kafka_thread():
    """Creates threads for functions consuming from Kafka queue."""
    t1 = Thread(target=get_attr)
    t1.daemon = True

    t2 = Thread(target=get_exp)
    t2.daemon = True

    t3 = Thread(target=get_event_stats)
    t3.daemon = True

    t4 = Thread(target=get_event_ids)
    t4.daemon = True

    t1.start()
    t2.start()
    t3.start()
    t4.start()


app = connexion.FlaskApp(__name__, specification_dir="")
app.add_api(
    "analyzer.yaml",
    base_path="/analyzer",
    strict_validation=True,
    validate_responses=True,
)

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
    setup_kafka_thread()
    app.run(port=8200, host="0.0.0.0")
