#!/usr/bin/env python3

import csv
from datetime import datetime, timedelta
import json
import os
import requests
import time

# Constants
oauth_lifespan_mins = 60

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
    json_data_file = open("output.json", "r")
    output_data_str = json_data_file.read()
    json_data_file.close()
    output_data = json.loads(output_data_str)

    return output_data


def create_csv_file(json_data):
    print_message("Transforming JSON to CSV Data")
    # Open CSV for raw data migration
    csv_file = csv.writer(open("output.csv", "w"))

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
    transposed_csv_file = csv.writer(open("output_transposed.csv", "w"))

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

def monitor_deployment(sleep_seconds = 10):
    print_message("Starting data collection")

    # Open csv file
    json_data_file = open("output.json", "w")
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

    # Finished writing so close file
    json_data_file.close()

    print_message("Data collection finished")

print_message("Container Monitoring Script Started")

output_script_runtime()

monitor_deployment()

json_data = read_json_file_data()

create_csv_file(json_data)

transpose_csv_data(json_data)

print_message("Script Finished")
