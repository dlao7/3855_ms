"""
Processing microservice to gather statistics about the
attraction and expense events, such as the number of each
and averages. Runs periodically, making a query to the
storage service to get new event entries, then re-calculating
and updating the statistics and saving them to a JSON file.
"""

import os
from datetime import datetime as dt, timezone
import json
import logging.config

import connexion
from connexion import NoContent
import yaml
import httpx

from apscheduler.schedulers.background import BackgroundScheduler
from connexion.middleware import MiddlewarePosition
from starlette.middleware.cors import CORSMiddleware

# Variable Loading
with open("config/processing.prod.yaml", "r", encoding="utf-8") as f:
    app_config = yaml.safe_load(f.read())


# Logging
with open("logger/log.prod.yaml", "r", encoding="utf-8") as f:
    log_config = yaml.safe_load(f.read())
    logging.config.dictConfig(log_config)


logger = logging.getLogger("basicLogger")


def calc_stats(past_values, attr, exp):
    """Calculates the stats for the
    two events using the past stored values
    and the new entries.

    Parameters:
    past_values (dict): Contains the contents of the
    json file with the stats calculated the last time
    the populate_stats function was run.
    attr (list): List of dictionaries with the new
    attraction entries since the last time the
    populate_stats function was run.
    exp (list): List of dictionaries with the new
    expense entries since the last time the
    populate_stats function was run.

    Returns:
    Updated statistics for the two events.
    """
    if len(attr) != 0:
        last_timestamp_attr = max(
            (dt.fromisoformat(date["date_created"]) for date in attr)
        )
        first_timestamp_attr = min(
            (dt.fromisoformat(date["date_created"]) for date in attr)
        )

        if last_timestamp_attr > dt.fromisoformat(past_values["last_updated"]):
            # Calculate total attractions, accounting for one off error
            if first_timestamp_attr == dt.fromisoformat(past_values["last_updated"]):
                total_attr = past_values["num_attr"] + len(attr) - 1
            else:
                total_attr = past_values["num_attr"] + len(attr)

            # Calculate average for new time range
            new_avg_hours = sum(hour["hours_open"] for hour in attr) / len(attr)

            # Weighting
            past_attr = past_values["num_attr"] / total_attr
            current_attr = len(attr) / total_attr

            # Calculate new rolling average
            roll_avg_hours = round(
                (
                    new_avg_hours * current_attr
                    + past_values["avg_hours_open"] * past_attr
                ),
                2,
            )
        else:
            # Use old values if no new entries
            total_attr = past_values["num_attr"]
            roll_avg_hours = past_values["avg_hours_open"]
    else:
        # Use old values if no new entries
        total_attr = past_values["num_attr"]
        roll_avg_hours = past_values["avg_hours_open"]

    if len(exp) != 0:
        last_timestamp_exp = max(
            (dt.fromisoformat(date["date_created"]) for date in exp)
        )
        first_timestamp_exp = min(
            (dt.fromisoformat(date["date_created"]) for date in exp)
        )

        if last_timestamp_exp > dt.fromisoformat(past_values["last_updated"]):
            # Calculate total expenses, accounting for one off error
            if first_timestamp_exp == dt.fromisoformat(past_values["last_updated"]):
                total_exp = past_values["num_exp"] + len(exp) - 1
            else:
                total_exp = past_values["num_exp"] + len(exp)

            # Calculate average for new time range
            new_avg_amount = sum(cost["amount"] for cost in exp) / len(exp)

            # Weighting
            past_exp = past_values["num_exp"] / total_exp
            current_exp = len(exp) / total_exp

            # Calculate new rolling average
            roll_avg_amount = round(
                (new_avg_amount * current_exp + past_values["avg_amount"] * past_exp), 2
            )
        else:
            total_exp = past_values["num_exp"]
            roll_avg_amount = past_values["avg_amount"]
    else:
        total_exp = past_values["num_exp"]
        roll_avg_amount = past_values["avg_amount"]

    # Checks for last timestamp
    if len(exp) != 0 and len(attr) != 0:
        last_updated = (
            max(last_timestamp_attr, last_timestamp_exp)
            .isoformat("T", "microseconds")
            .replace("+00:00", "Z")
        )
    elif len(exp) == 0 and len(attr) != 0:
        last_updated = last_timestamp_attr.isoformat("T", "microseconds").replace(
            "+00:00", "Z"
        )
    else:
        last_updated = last_timestamp_exp.isoformat("T", "microseconds").replace(
            "+00:00", "Z"
        )

    # Update with cumulative stats
    updated_stats = {
        "num_attr": total_attr,
        "avg_hours_open": roll_avg_hours,
        "num_exp": total_exp,
        "avg_amount": roll_avg_amount,
        "last_updated": last_updated,
    }

    return updated_stats


def populate_stats():
    """
    Loads from stats file, if not found, uses UNIX time 0 as start
    timestamp. Queries storage endpoint to get entries in a certain time
    frame. Updated statistics are then saved in a JSON file.

    Returns: None
    """

    logger.info("Periodic processing has started.")

    # Read file
    try:
        with open(
            app_config["datastore"]["filepath"], "r", encoding="utf-8"
        ) as read_content:
            stat_file = json.load(read_content)
            start_time = stat_file["last_updated"]
    except FileNotFoundError:
        start_time = "1970-01-01T00:00:00Z"
        stat_file = {
            "num_attr": 0,
            "avg_hours_open": 0,
            "num_exp": 0,
            "avg_amount": 0,
            "last_updated": "1970-01-01T00:00:00Z",
        }
    except IOError:
        logger.error("An error occurred while reading the stats file.")

    end_time = dt.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Get response from storage app
    params = {"start_timestamp": start_time, "end_timestamp": end_time}

    attr_resp = httpx.get(
        app_config["eventstores"]["attraction_info"]["url"], params=params
    )
    exp_resp = httpx.get(
        app_config["eventstores"]["expense_info"]["url"], params=params
    )

    if attr_resp.status_code != 200:
        logger.error(
            f"200 Response code not received for attraction entries "
            f"starting at {start_time} and "
            f"ending at {end_time}."
        )

    if exp_resp.status_code != 200:
        logger.error(
            f"200 Response code not received for expense entries "
            f"starting at {start_time} and "
            f"ending at {end_time}."
        )

    # Get response content as json
    attr_res = attr_resp.json()
    exp_res = exp_resp.json()

    logger.info(
        f"There were {len(attr_res)} attraction entries and "
        f"{len(exp_res)} expense entries received."
    )

    if len(attr_res) == 0 and len(exp_res) == 0:
        updated_stats = stat_file
    else:
        updated_stats = calc_stats(stat_file, attr_res, exp_res)

    with open(app_config["datastore"]["filepath"], "w", encoding="utf-8") as w:
        json.dump(updated_stats, w, indent=4)

    update_string = (
        f"num_attr:{updated_stats['num_attr']}, "
        f"avg_hours_open:{updated_stats['avg_hours_open']}, "
        f"num_exp:{updated_stats['num_exp']}, "
        f"avg_amount:{updated_stats['avg_amount']}, "
        f"last_updated:{updated_stats['last_updated']}"
    )
    logger.debug("The updated stats are %s.", update_string)
    logger.info("Periodic processing has ended.")

    return NoContent, 200


def get_stats():
    """Reads the processing JSON file and
    returns the JSON.

    Returns:
    The JSON from the processing JSON file
    with the counts and averages for the
    two events.
    """
    logger.info("A request was received.")

    try:
        with open(
            app_config["datastore"]["filepath"], "r", encoding="utf-8"
        ) as read_content:
            stat_file = json.load(read_content)
    except FileNotFoundError:
        logger.error("The stats file does not exist.")
        return "Statistics do not exist.", 404
    except IOError:
        logger.error("An error occurred while reading the stats file.")

    logger.debug(stat_file)
    logger.info("Request was completed.")

    return stat_file, 200


def init_scheduler():
    """Runs populate stats every X seconds."""
    sched = BackgroundScheduler(daemon=True)
    sched.add_job(
        populate_stats, "interval", seconds=app_config["scheduler"]["interval"]
    )
    sched.start()


app = connexion.FlaskApp(__name__, specification_dir="")
app.add_api("processing.yaml", base_path="/processing", strict_validation=True, validate_responses=True)
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
    init_scheduler()
    app.run(port=8100, host="0.0.0.0")
