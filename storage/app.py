import connexion
import functools
import logging.config
import yaml
import json
import db
import models
from datetime import datetime as dt
from sqlalchemy import select, func
from pykafka import KafkaClient
from pykafka.common import OffsetType
from threading import Thread
import create_db

# App Config
with open("config/storage.prod.yaml", "r") as f:
    app_config = yaml.safe_load(f.read())

# Logging
with open("logger/log.prod.yaml", "r") as f:
    log_config = yaml.safe_load(f.read())
    logging.config.dictConfig(log_config)


logger = logging.getLogger("basicLogger")


def log_event(event_type, trace_id):
    logger.debug(f"Stored event {event_type} with a trace id of {trace_id}")


def use_db_session(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        session = db.make_session()
        try:
            return func(session, *args, **kwargs)
        finally:
            session.commit()
            session.close()

    return wrapper


@use_db_session
def process_messages(session):
    """Process event messages"""
    hostname = f"{app_config['events']['hostname']}:{app_config['events']['port']}"
    client = KafkaClient(hosts=hostname)
    topic = client.topics[str.encode(f"{app_config['events']['topic']}")]

    # Create a consume on a consumer group, that only reads new messages
    # (uncommitted messages) when the service re-starts (i.e., it doesn't
    # read all the old messages from the history in the message queue).

    consumer = topic.get_simple_consumer(
        consumer_group=b"event_group",
        reset_offset_on_start=False,
        auto_offset_reset=OffsetType.LATEST,
    )

    # This is blocking - it will wait for a new message
    for msg in consumer:
        msg_str = msg.value.decode("utf-8")
        msg = json.loads(msg_str)
        logger.info("Message: %s" % msg)

        payload = msg["payload"]

        if msg["type"] == "attraction_info":

            session.add(report_attraction_info(payload))
            session.commit()

            logger.info(
                f"Attraction event with trace id {payload["trace_id"]} stored via Kafka."
            )
        elif msg["type"] == "expense_info":

            session.add(report_expense_info(payload))
            session.commit()

            logger.info(
                f"Expense event with trace id {payload["trace_id"]} stored via Kafka."
            )

        # Commit the new message as being read
        consumer.commit_offsets()


def setup_kafka_thread():
    t1 = Thread(target=process_messages)
    t1.setDaemon(True)
    t1.start()


def report_attraction_info(body):
    event = models.AttractionInfo(
        user_id=body["user_id"],
        attraction_category=body["attraction_category"],
        hours_open=body["hours_open"],
        attraction_timestamp=dt.strptime(
            body["attraction_timestamp"], "%Y-%m-%d %H:%M:%S"
        ),
        trace_id=body["trace_id"],
    )
    return event


def report_expense_info(body):
    event = models.ExpenseInfo(
        user_id=body["user_id"],
        amount=body["amount"],
        expense_category=body["expense_category"],
        expense_timestamp=dt.strptime(body["expense_timestamp"], "%Y-%m-%d %H:%M:%S"),
        trace_id=body["trace_id"],
    )

    return event


def get_attraction_info(start_timestamp, end_timestamp):
    """Gets new attraction entries between the start and end timestamps"""
    session = db.make_session()

    start = dt.fromisoformat(start_timestamp)
    end = dt.fromisoformat(end_timestamp)

    statement = (
        select(models.AttractionInfo)
        .where(models.AttractionInfo.date_created >= start)
        .where(models.AttractionInfo.date_created < end)
    )

    results = [
        result.to_dict() for result in session.execute(statement).scalars().all()
    ]

    session.close()

    logger.info(
        "Found %d attraction entries (start: %s, end: %s)", len(results), start, end
    )

    return results


def get_expense_info(start_timestamp, end_timestamp):
    """Gets new expense entries between the start and end timestamps"""
    session = db.make_session()

    start = dt.fromisoformat(start_timestamp)
    end = dt.fromisoformat(end_timestamp)

    statement = (
        select(models.ExpenseInfo)
        .where(models.ExpenseInfo.date_created >= start)
        .where(models.ExpenseInfo.date_created < end)
    )

    results = [
        result.to_dict() for result in session.execute(statement).scalars().all()
    ]

    session.close()

    logger.info(
        "Found %d expense entries (start: %s, end: %s)", len(results), start, end
    )

    return results


def get_records():
    session = db.make_session()

    attr_statement = (
        select(func.count("*")).select_from(models.AttractionInfo)
    )

    exp_statement = (
        select(func.count("*")).select_from(models.ExpenseInfo)
    )

    num_attr = session.execute(attr_statement)
    num_exp = session.execute(exp_statement)

    results = {
        "num_attr" : num_attr,
        "num_exp" : num_exp
    }

    logger.info(
        f"Found {num_attr} attraction entries and found {num_exp} expense entries."
    )

    session.close()

    return results


def get_full_attr():
    session = db.make_session()

    statement = (
        select(models.AttractionInfo.user_id, models.AttractionInfo.trace_id)
    )

    results = [
        result.to_dict_id() for result in session.execute(statement).scalars().all()
    ]

    logger.info(
        "Found %d attraction entries", len(results)
    )

    session.close()

    return results


def get_full_exp():
    session = db.make_session()

    statement = (
        select(models.ExpenseInfo.user_id, models.ExpenseInfo.trace_id)
    )

    results = [
        result.to_dict_id() for result in session.execute(statement).scalars().all()
    ]

    logger.info(
        "Found %d expense entries", len(results)
    )

    session.close()

    return results


app = connexion.FlaskApp(__name__, specification_dir="")
app.add_api("storage.yaml", strict_validation=True, validate_responses=True)


if __name__ == "__main__":
    setup_kafka_thread()
    create_db.create_tables()
    app.run(port=8090, host="0.0.0.0")
