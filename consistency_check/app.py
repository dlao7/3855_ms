"""
Consistency check service to gather information from processing, storage
and analyzer services about the counts and user/trace ids for comparison.
"""

import os
import time
from datetime import timezone, datetime as dt
import json
import logging.config

import connexion
import yaml
import httpx
from connexion.middleware import MiddlewarePosition
from starlette.middleware.cors import CORSMiddleware

# App Config
with open("config/check.prodprox.yaml", "r", encoding="utf-8") as f:
    app_config = yaml.safe_load(f.read())

# Logging
with open("logger/log.prod.yaml", "r", encoding="utf-8") as f:
    log_config = yaml.safe_load(f.read())
    logging.config.dictConfig(log_config)

logger = logging.getLogger("basicLogger")


def compare_ids(analyzer_data, storage_data):
    """Compares the input ID lists from storage and analyzer
    by trace_id and outputs the differences.

    Parameters:
    analyzer_data (list): list of dictionaries with user and
    trace ids, from the analyzer service
    storage_data (list): list of dictionaries with user and
    trace ids, from the storage service

    Returns:
    A tuple with two lists with the trace/user id entries
    that are either missing in the mySQL database
    or missing in the Kafka queue.

    Example of array
    [ {"user_id": "XXXX", "trace_id": "XXXX"},
    {"user_id": "XXXX", "trace_id": "XXXX"} ]
    """
    # Kafka Queue Entries
    analyzer_set = {item["trace_id"] for item in analyzer_data}

    # mySQL Database Entries
    storage_set = {item["trace_id"] for item in storage_data}

    # present in queue, not in db (missing in db)
    missing_trace_db = analyzer_set.difference(storage_set)
    missing_in_db = [
        entry for entry in analyzer_data if entry["trace_id"] in missing_trace_db
    ]

    # present in db, not in queue (missing in queue)
    missing_trace_queue = storage_set.difference(analyzer_set)
    missing_in_queue = [
        entry for entry in storage_data if entry["trace_id"] in missing_trace_queue
    ]

    # returns tuple of two lists missing_in_db, missing_in_queue
    return missing_in_db, missing_in_queue


def run_consistency_checks():
    """Gathers the counts and ID statistics from storage,
    processing, and analyzer microservices and writes
    the information in a dictionary to a JSON file.

    Returns:
    A JSON with the gathered statistics
    """
    # log info started processing
    logger.info("Consistency checks started.")
    start_time = time.time()

    # get storage counts
    storage_counts = httpx.get(
        app_config["eventstores"]["storage_counts"]["url"]
    ).json()

    # get storage ids
    storage_attr_ids = httpx.get(
        app_config["eventstores"]["storage_attr_ids"]["url"]
    ).json()
    storage_exp_ids = httpx.get(
        app_config["eventstores"]["storage_exp_ids"]["url"]
    ).json()

    # get analyzer counts
    analyzer_counts = httpx.get(
        app_config["eventstores"]["analyzer_counts"]["url"]
    ).json()

    # get analyzer ids
    analyzer_ids = httpx.get(app_config["eventstores"]["analyzer_ids"]["url"]).json()

    # get processing stats
    proc_stats = httpx.get(app_config["eventstores"]["proc_stats"]["url"]).json()

    # Combine the id entries from storage
    all_storage_ids = storage_attr_ids + storage_exp_ids

    # Compare trace_ids
    missing_in_db, missing_in_queue = compare_ids(analyzer_ids, all_storage_ids)

    # Construct JSON
    check_stats = {
        "last_updated": dt.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "counts": {
            # storage
            "db": {
                "attractions": storage_counts["num_attr"],
                "expenses": storage_counts["num_exp"],
            },
            # analyzer
            "queue": {
                "attractions": analyzer_counts["num_attr"],
                "expenses": analyzer_counts["num_exp"],
            },
            # processing
            "processing": {
                "attractions": proc_stats["num_attr"],
                "expenses": proc_stats["num_exp"],
            },
        },
        "missing_in_db": missing_in_db,
        "missing_in_queue": missing_in_queue,
    }

    # write to file
    with open(app_config["datastore"]["filepath"], "w", encoding="utf-8") as w:
        json.dump(check_stats, w, indent=4)

    end_time = time.time()

    # calculate processing time
    elapsed_time = round((end_time - start_time) * 1000)

    # log processing time and missing stats
    logger.info(
        f"Consistency checks completed | processing_time_ms={elapsed_time}"
        f" | missing_in_db = {len(missing_in_db)} | missing_in_queue = {len(missing_in_queue)}"
    )

    # return JSON
    return check_stats, 200


def get_checks():
    """Reads the consistency check JSON file and
    returns the JSON.

    Returns:
    The JSON from the check JSON file with the
    gathered counts and missing ID entries.
    """

    logger.info("A request to get consistency check stats was received.")

    try:
        with open(
            app_config["datastore"]["filepath"], "r", encoding="utf-8"
        ) as read_content:
            check_file = json.load(read_content)
    except FileNotFoundError:
        logger.error("The check stats file does not exist.")
        return "Statistics do not exist.", 404
    except IOError:
        logger.error("An error occurred while reading the check stats file.")

    logger.debug(check_file)
    logger.info("The consistency check request was completed.")

    return check_file, 200


app = connexion.FlaskApp(__name__, specification_dir="")
app.add_api("consistency_check.yaml", base_path="/consistency_check", strict_validation=True, validate_responses=True)

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
    app.run(port=8300, host="0.0.0.0")
