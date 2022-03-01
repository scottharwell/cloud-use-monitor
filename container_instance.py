#!/usr/bin/env python3

import csv
from datetime import datetime, timedelta
import json
import os
import requests
import time

# Get environment variables
client_id = os.getenv('CLIENT_ID')
client_secret = os.environ.get('CLIENT_SECRET')
subscription_id = os.environ.get('SUBSCRIPTION_ID')
tenant_id = os.environ.get('TENANT_ID')
region = os.environ.get('REGION')
min_to_run = float(os.environ.get('MINS_TO_RUN'))

# MSFT Variables
access_token_url = "https://login.microsoftonline.com/{}/oauth2/token".format(
    tenant_id)
data = {'grant_type': 'client_credentials', 'client_id': client_id,
        'client_secret': client_secret, 'resource': 'https://management.azure.com'}

# Get Bearer Token - Tokens live for 1 hour
auth = requests.post(access_token_url, data=data)
auth_data = auth.json()

# Setup URL
url = "https://management.azure.com/subscriptions/{}/providers/Microsoft.ContainerInstance/locations/{}/usages?api-version=2021-09-01".format(
    subscription_id, region)
headers = {"Authorization": "{} {}".format(
    auth_data['token_type'], auth_data['access_token'])}

# Open csv file
json_data_file = open('output.json', 'w')
json_data_file.write("[")

# Create loop for 30 mins that writes data to a CSV file every 10 seconds
now = datetime.now()
timeout_time = now + timedelta(minutes=min_to_run)

print("Starting data collection.")

row = 0
while now < timeout_time:
    print("{}: Getting Data -- Row {}".format(now, row))
    if row > 0:
        json_data_file.write(",\n")

    # Submit Request
    response = requests.get(url, headers=headers)
    response_data = response.json()

    if "value" in response_data:
        response_value = json.dumps(response_data['value'])
        # Write data
        json_data_file.write(response_value)
    else:
        # Something happened!
        print(response_data)

    # Sleep 10 seconds
    time.sleep(10)

    # Set next row
    row = row + 1
    now = datetime.now()

json_data_file.write("]")

print("Data collection finished. Writing to CSV.")

# Finished writing so close file
json_data_file.close()

# Read all output back into memory to convert to CSV
json_data_file = open('output.json', 'r')
output_data_str = json_data_file.read()
json_data_file.close()
output_data = json.loads(output_data_str)

# Open CSV for raw data migration
csv_file = csv.writer(open("output.csv", "w"))

# Create header row
csv_file.writerow(["id", "unit", "currentValue", "limit",
                  "name.value", "name.localizedValue"])

for row in output_data:
    # print(row)
    for record in row:
        # print(record)
        csv_file.writerow([
            record['id'],
            record['unit'],
            record['currentValue'],
            record['limit'],
            record['name']['value'],
            record['name']['localizedValue']
        ])

# Open CSV for data transposition
transposed_csv_file = csv.writer(open("output_transposed.csv", "w"))

# Create header row
transposed_csv_file.writerow(["ContainerGroups", "StandardCores", "StandardK80Cores", "StandardP100Cores",
                              "StandardV100Cores", "DedicatedContainerGroups"])

for row in output_data:
    container_groups = row[0]['currentValue']
    standard_cores = row[1]['currentValue']
    standard_k80_cores = row[2]['currentValue']
    standard_p100_cores = row[3]['currentValue']
    standard_v100_cores = row[4]['currentValue']
    dedicated_container_groups = row[5]['currentValue']

    transposed_csv_file.writerow([
        container_groups,
        standard_cores,
        standard_k80_cores,
        standard_p100_cores,
        standard_v100_cores,
        dedicated_container_groups
    ])

print("Finished")
