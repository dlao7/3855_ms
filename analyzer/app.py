import connexion
import logging.config
import yaml
import json
from pykafka import KafkaClient
from threading import Thread
from connexion.middleware import MiddlewarePosition
from starlette.middleware.cors import CORSMiddleware

# App Config
with open("config/analyzer.prod.yaml", "r") as f:
    app_config = yaml.safe_load(f.read())

# Logging
with open("logger/log.prod.yaml", "r") as f:
    log_config = yaml.safe_load(f.read())
    logging.config.dictConfig(log_config)


logger = logging.getLogger("basicLogger")


hostname = f"{app_config['events']['hostname']}:{app_config['events']['port']}"
client = KafkaClient(hosts=hostname)
topic = client.topics[str.encode(f"{app_config['events']['topic']}")]


def get_attr(index):
    consumer = topic.get_simple_consumer(
        reset_offset_on_start=True, consumer_timeout_ms=1000
    )

    counter = 0
    for msg in consumer:
        msg_str = msg.value.decode("utf-8")
        msg = json.loads(msg_str)

        if msg["type"] == "attraction_info":
            if counter == index:
                logger.info(f"Attraction Message found at index {index}")

                return msg["payload"], 200

            counter += 1

    return {"message": f"No attraction message at index {index}!"}, 404


def get_exp(index):
    consumer = topic.get_simple_consumer(
        reset_offset_on_start=True, consumer_timeout_ms=1000
    )

    counter = 0
    for msg in consumer:
        msg_str = msg.value.decode("utf-8")
        msg = json.loads(msg_str)

        if msg["type"] == "expense_info":
            if counter == index:
                logger.info(f"Expense Message found at index {index}")

                return msg["payload"], 200

            counter += 1

    return {"message": f"No expense message at index {index}!"}, 404


def get_event_stats():
    logger.info("Request received to get number of event type in queue.")

    consumer = topic.get_simple_consumer(
        reset_offset_on_start=True, consumer_timeout_ms=1000
    )

    attr_counter = 0
    exp_counter = 0

    for msg in consumer:
        msg_str = msg.value.decode("utf-8")
        msg = json.loads(msg_str)
        if msg["type"] == "attraction_info":
            attr_counter += 1
        else:
            exp_counter += 1

    logger.info("Request completed to get number of event type in queue.")

    return {
        "num_attr": attr_counter,
        "num_exp": exp_counter,
    }, 200


def setup_kafka_thread():
    t1 = Thread(target=get_attr)
    t1.setDaemon(True)
    t2 = Thread(target=get_exp)
    t2.setDaemon(True)

    t1.start()
    t2.start()


app = connexion.FlaskApp(__name__, specification_dir="")
app.add_api("openapi.yaml", strict_validation=True, validate_responses=True)
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
