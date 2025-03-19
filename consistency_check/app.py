# Connexion
import connexion
from connexion import NoContent

# Basic Modules
import time
import yaml
import json
import logging.config
import httpx
from datetime import timezone, datetime as dt

# create bind mount folders in ansible script
# # log, config, json
# update analyzer yaml for endpoints
# update storage yaml for endpoints
# synchronize consistency_check.yaml with functions
# write trace id compare function

# App Config
with open("config/check.prod.yaml", "r") as f:
    app_config = yaml.safe_load(f.read())

# Logging
with open("logger/log.prod.yaml", "r") as f:
    log_config = yaml.safe_load(f.read())
    logging.config.dictConfig(log_config)

logger = logging.getLogger("basicLogger")

def compare_ids(analyzer_data, storage_attr_ids, storage_exp_ids):
    pass
    # same as doing a left join and a right join
    # contains [ {user_id: "something", trace_id: "something"}, ... ]
    # returns tuple of two lists missing_in_db, missing in queue

def update_check():
    # log info started processing
    logger.info(f"Consistency checks started.")
    start_time = time.time()

    # get processing stats
    proc_stats_resp = httpx.get(
        app_config["eventstores"]["proc_stats"]["url"]
    )

    # get analyzer counts
    analyzer_counts_resp = httpx.get(
        app_config["eventstores"]["analyzer_counts"]["url"]
    )

    # get analyzer ids
    analyzer_ids_resp = httpx.get(
        app_config["eventstores"]["analyzer_ids"]["url"]
    )

    # get storage counts
    storage_counts_resp = httpx.get(
        app_config["eventstores"]["storage_counts"]["url"]
    )

    # get storage ids
    storage_attr_ids_resp = httpx.get(
        app_config["eventstores"]["storage_attr_ids"]["url"]
    )
    storage_exp_ids_resp = httpx.get(
        app_config["eventstores"]["storage_exp_ids"]["url"]
    )

    # JSON response conversion
    proc_stats = proc_stats_resp.json()

    analyzer_counts, analyzer_ids = analyzer_counts_resp.json(), analyzer_ids_resp.json()

    storage_counts = storage_counts_resp.json()
    storage_attr_ids, storage_exp_ids = storage_attr_ids_resp.json(), storage_exp_ids_resp.json()

    # compare trace_ids
    missing_in_db, missing_in_queue = compare_ids(analyzer_ids, storage_attr_ids, storage_exp_ids)

    # construct JSON
    check_stats = {
      "last_updated" : dt.now(timezone.utc).isoformat().replace("+00:00", "Z"),
      "counts": {
            # storage
            "db": {
                "attractions": storage_counts["num_attr"],
                "expenses": storage_counts["num_exp"]
            },
            # analyzer
            "queue": {
                "attractions": analyzer_counts["num_attr"],
                "expenses": analyzer_counts["num_exp"]
            },
            # processing
            "processing": {
                "attractions": proc_stats["num_attractions"],
                "expenses": proc_stats["num_expenses"]
            }
        },
        "missing_in_db": missing_in_db,
        "missing_in_queue": missing_in_queue
    }

    # write to file
    with open(app_config["datastore"]["filepath"], "w") as w:
        json.dump(check_stats, w, indent=4)

    end_time = time.time()

    # calculate processing time
    elapsed_time = (end_time - start_time) * 1000

    # log processing time and missing stats
    logger.info(f"Consistency checks completed | processing_time_ms={elapsed_time} | missing_in_db = {len(missing_in_db)} | missing_in_queue = {len(missing_in_queue)}")

    # return JSON
    return check_stats, 200

def get_check():
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

if __name__ == "__main__":
    app.run(port=8300, host="0.0.0.0")