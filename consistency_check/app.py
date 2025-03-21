# Connexion
import connexion

# Basic Modules
import time
import yaml
import json
import logging.config
import httpx
from datetime import timezone, datetime as dt
from connexion.middleware import MiddlewarePosition
from starlette.middleware.cors import CORSMiddleware

# add documentation to all apps
# create bind mount folders in ansible script
# # log, config, json
# test deployment

# App Config
with open("config/check.prod.yaml", "r") as f:
    app_config = yaml.safe_load(f.read())

# Logging
with open("logger/log.prod.yaml", "r") as f:
    log_config = yaml.safe_load(f.read())
    logging.config.dictConfig(log_config)

logger = logging.getLogger("basicLogger")


def compare_ids(analyzer_data, storage_data):
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
    # log info started processing
    logger.info(f"Consistency checks started.")
    start_time = time.time()

    # get storage counts
    storage_counts_resp = httpx.get(app_config["eventstores"]["storage_counts"]["url"])

    # get storage ids
    storage_attr_ids_resp = httpx.get(
        app_config["eventstores"]["storage_attr_ids"]["url"]
    )
    storage_exp_ids_resp = httpx.get(
        app_config["eventstores"]["storage_exp_ids"]["url"]
    )

    # get analyzer counts
    analyzer_counts_resp = httpx.get(
        app_config["eventstores"]["analyzer_counts"]["url"]
    )

    # get analyzer ids
    analyzer_ids_resp = httpx.get(app_config["eventstores"]["analyzer_ids"]["url"])

    # get processing stats
    proc_stats_resp = httpx.get(app_config["eventstores"]["proc_stats"]["url"])

    # JSON response conversion
    storage_counts = storage_counts_resp.json()
    storage_attr_ids, storage_exp_ids = (
        storage_attr_ids_resp.json(),
        storage_exp_ids_resp.json(),
    )

    analyzer_counts, analyzer_ids = (
        analyzer_counts_resp.json(),
        analyzer_ids_resp.json(),
    )

    proc_stats = proc_stats_resp.json()

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
    with open(app_config["datastore"]["filepath"], "w") as w:
        json.dump(check_stats, w, indent=4)

    end_time = time.time()

    # calculate processing time
    elapsed_time = round((end_time - start_time) * 1000)

    # log processing time and missing stats
    logger.info(
        f"Consistency checks completed | processing_time_ms={elapsed_time} | missing_in_db = {len(missing_in_db)} | missing_in_queue = {len(missing_in_queue)}"
    )

    # return JSON
    return check_stats, 200


def get_checks():
    logger.info("A request to get consistency check stats was received.")

    try:
        with open(app_config["datastore"]["filepath"], "r") as read_content:
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
app.add_api("consistency_check.yaml", strict_validation=True, validate_responses=True)
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
