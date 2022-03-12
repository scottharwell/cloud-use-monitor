#!/usr/bin/env python3

import csv
from datetime import datetime, timedelta
import json
import os
import requests
import shutil
import sys
import time

# Constants
oauth_lifespan_mins = 60
output_folder = os.getenv("OUTPUT_FOLDER") if os.getenv("OUTPUT_FOLDER") else "output"

# Operation State
collecting_data = False

# Get environment variables
client_id = os.getenv("CLIENT_ID")
client_secret = os.environ.get("CLIENT_SECRET")
subscription_id = os.environ.get("SUBSCRIPTION_ID")
tenant_id = os.environ.get("TENANT_ID")
region = os.environ.get("REGION")
min_to_run = float(os.environ.get("MINS_TO_RUN")) if os.environ.get("MINS_TO_RUN") else 45  # must be fewer than 60 so that the OAuth token does not expire

# MSFT Variables
headers = None
oauth_refresh_time = None
access_token_url = "https://login.microsoftonline.com/{}/oauth2/token".format(tenant_id)
url = "https://management.azure.com/subscriptions/{}/providers/Microsoft.ContainerInstance/locations/{}/usages?api-version=2021-09-01".format(subscription_id, region)


def print_message(text: str):
    now = datetime.now()
    print("{}: {}".format(now, text))


def prep_output_folder():
    try:
        shutil.rmtree(output_folder)
    except Exception as e:
        print_message(e)
    finally:
        os.mkdir(output_folder)


def output_script_runtime():
    now = datetime.now()
    end_time = now + timedelta(minutes=min_to_run)
    print_message("Script will finish at {}".format(end_time))


def setup_oauth_token():
    print_message("Getting Auth Token")

    data = {"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret, "resource": "https://management.azure.com"}

    # Get Bearer Token - Tokens live for 1 hour
    auth = requests.post(access_token_url, data=data)
    auth_data = auth.json()

    # Setup Headers
    global headers
    headers = {"Authorization": "{} {}".format(auth_data["token_type"], auth_data["access_token"])}

    # Set Auth Refresh Time
    global oauth_refresh_time
    oauth_refresh_time = datetime.now()
    print_message("Auth Token Result: {}".format(auth.status_code))


def read_json_file_data() -> any:
    # Read all output back into memory to convert to CSV
    with open("{}/output.json".format(output_folder), "r") as json_data_file:
        output_data_str = json_data_file.read()
        output_data = json.loads(output_data_str)

        return output_data


def create_csv_file(json_data):
    print_message("Transforming JSON to CSV Data")

    # Open CSV for raw data migration
    csv_file = csv.writer(open("{}/output.csv".format(output_folder), "w"))
    
    # Create header row
    csv_file.writerow(["id", "unit", "currentValue", "limit",
                    "name.value", "name.localizedValue"])

    for row in json_data:
        # print(row)
        for record in row:
            # print(record)
            csv_file.writerow([
                record["id"],
                record["unit"],
                record["currentValue"],
                record["limit"],
                record["name"]["value"],
                record["name"]["localizedValue"]
            ])


def transpose_csv_data(json_data):
    print_message("Transposing CSV to core counts as columns")
    
    # Open CSV for data transposition
    transposed_csv_file = csv.writer(open("{}/output_transposed.csv".format(output_folder), "w"))
    
    # Create header row
    transposed_csv_file.writerow(["ContainerGroups", "StandardCores", "StandardK80Cores", "StandardP100Cores",
                                "StandardV100Cores", "DedicatedContainerGroups"])

    for row in json_data:
        container_groups = row[0]["currentValue"]
        standard_cores = row[1]["currentValue"]
        standard_k80_cores = row[2]["currentValue"]
        standard_p100_cores = row[3]["currentValue"]
        standard_v100_cores = row[4]["currentValue"]
        dedicated_container_groups = row[5]["currentValue"]

        transposed_csv_file.writerow([
            container_groups,
            standard_cores,
            standard_k80_cores,
            standard_p100_cores,
            standard_v100_cores,
            dedicated_container_groups
        ])


def handle_monitor_stop():
    with open("{}/output.json".format(output_folder), "r") as json_data_file:
        json_data_str = json_data_file.read()

        if json_data_str[-2:] != "]]":
            print_message("JSON does not appear complete. Attempting to correct the file.")
            json_data_file = open("{}/output.json".format(output_folder), "a+")
            json_data_file.write("]")
            json_data_str = json_data_str + "]"

        convert_files = ""
        while convert_files == "" or (convert_files.lower() != "n" and convert_files.lower() != "y"):
            convert_files = input("Convert collected JSON to CSV data? (y or n): ")

        if convert_files.lower() == "y":

            json_data = json.loads(json_data_str)
            create_csv_file(json_data)
            transpose_csv_data(json_data)


def monitor_deployment(sleep_seconds = 10):
    print_message("Starting data collection")

    # Open csv file
    with open("{}/output.json".format(output_folder), "w") as json_data_file:
        json_data_file.write("[")

        # Create loop for 30 mins that writes data to a CSV file every 10 seconds
        now = datetime.now()
        timeout_time = now + timedelta(minutes=min_to_run)

        row = 0

        while now < timeout_time:
            # Get new access token if required
            refresh_token = False

            if oauth_refresh_time is not None:
                refresh_token_time = oauth_refresh_time + timedelta(minutes=(oauth_lifespan_mins - 5))

                if now > refresh_token_time:
                    refresh_token = True
            else:
                refresh_token = True

            if refresh_token:
                setup_oauth_token()

            print_message("Getting Data -- Row {}".format(row))
            if row > 0:
                json_data_file.write(",\n")

            try:
                # Ensure that the collecting data flag is true
                global collecting_data
                collecting_data = True

                # Submit Request
                response = requests.get(url, headers=headers)
                response_data = response.json()

                if "value" in response_data:
                    response_value = json.dumps(response_data["value"])
                    # Write data
                    json_data_file.write(response_value)
                else:
                    # Something happened!
                    print_message("MS APIs returned an unexpected response")
                    print(response_data)

                # Sleep 10 seconds
                time.sleep(sleep_seconds)
            except Exception as e:
                print_message("An exception occurred communicating with MS APIs")
                print(e)

            # Set next row
            row = row + 1
            now = datetime.now()

        json_data_file.write("]")

    print_message("Data collection finished")


def main():
    # Start Monitoring Process
    print_message("Container Monitoring Script Started")

    # Prep data output locations
    prep_output_folder()
    output_script_runtime()

    # Run monitoring
    monitor_deployment()

    # Create CSV files from monitored data
    json_data = read_json_file_data()
    create_csv_file(json_data)
    transpose_csv_data(json_data)

    # Wrap up tasks
    print_message("Script Finished")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print_message('Process interrupted')

        handle_monitor_stop()

        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
