"""
Storage service to consume messages from the Kafka queue to insert into
a mySQL database, and retrieve entries between specific timestamps,
user and trace ids, and counts from the mySQL database.
"""

from datetime import datetime as dt
import json
import logging.config
from threading import Thread
import functools

import connexion
import yaml

from sqlalchemy import select, func
from pykafka import KafkaClient
from pykafka.common import OffsetType

import db
import models
import create_db

# App Config
with open("config/storage.prod.yaml", "r", encoding="utf-8") as f:
    app_config = yaml.safe_load(f.read())

# Logging
with open("logger/log.prod.yaml", "r", encoding="utf-8") as f:
    log_config = yaml.safe_load(f.read())
    logging.config.dictConfig(log_config)


logger = logging.getLogger("basicLogger")


def log_event(event_type, trace_id):
    """Creates log for events with type and trace ID."""
    logger.debug("Stored event %s with a trace id of %s", event_type, trace_id)


def use_db_session(func):
    """Decorator to create SQLAlchemy session and then commit and close the
    session.
    """

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
    """Consumes Kafka queue messages and inserts them into mySQL database."""
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
        logger.info("Message: %s", msg)

        payload = msg["payload"]

        if msg["type"] == "attraction_info":

            session.add(cons_attraction_info(payload))
            session.commit()

            logger.info(
                "Attraction event with trace id %s stored via Kafka.",
                payload["trace_id"],
            )
        elif msg["type"] == "expense_info":

            session.add(cons_expense_info(payload))
            session.commit()

            logger.info(
                "Expense event with trace id %s stored via Kafka.", payload["trace_id"]
            )

        # Commit the new message as being read
        consumer.commit_offsets()


def cons_attraction_info(body):
    """Constructs attraction database entry for submission to a mySQL database."""
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


def cons_expense_info(body):
    """Constructs expense database entry for submission to a mySQL database."""
    event = models.ExpenseInfo(
        user_id=body["user_id"],
        amount=body["amount"],
        expense_category=body["expense_category"],
        expense_timestamp=dt.strptime(body["expense_timestamp"], "%Y-%m-%d %H:%M:%S"),
        trace_id=body["trace_id"],
    )

    return event


def get_attraction_info(start_timestamp, end_timestamp):
    """Gets new attraction entries from the mySQL database between the start and end timestamps
    and returns the result as a list of dictionaries."""
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
    """Gets new expense entries from the mySQL database between the start and end timestamps
    and returns the result as a list of dictionaries."""
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


def get_counts():
    """Gets counts of each event from the mySQL database."""
    session = db.make_session()

    attr_statement = select(func.count("*")).select_from(models.AttractionInfo)
    exp_statement = select(func.count("*")).select_from(models.ExpenseInfo)

    num_attr = session.execute(attr_statement).scalar()
    num_exp = session.execute(exp_statement).scalar()

    results = {"num_attr": num_attr, "num_exp": num_exp}

    logger.info(
        "Found %s attraction entries and found %s expense entries.", num_attr, num_exp
    )

    session.close()

    return results


def get_attr_ids():
    """Gets all user and trace IDs of attraction events from the mySQL database and
    returns them as a list of dictionaries."""
    session = db.make_session()

    statement = select(models.AttractionInfo)

    results = [
        result.to_dict_id() for result in session.execute(statement).scalars().all()
    ]

    logger.info("Found %d attraction id entries", len(results))

    session.close()

    return results


def get_exp_ids():
    """Gets all user and trace IDs of expense events from the mySQL database and
    returns them as a list of dictionaries."""
    session = db.make_session()

    statement = select(models.ExpenseInfo)

    results = [
        result.to_dict_id() for result in session.execute(statement).scalars().all()
    ]

    logger.info("Found %d expense id entries", len(results))

    session.close()

    return results


def setup_kafka_thread():
    """Creates thread for Kafka consumer."""
    t1 = Thread(target=process_messages)
    t1.daemon = True
    t1.start()


app = connexion.FlaskApp(__name__, specification_dir="")
app.add_api("storage.yaml", strict_validation=True, validate_responses=True)


if __name__ == "__main__":
    setup_kafka_thread()
    create_db.create_tables()
    app.run(port=8090, host="0.0.0.0")
