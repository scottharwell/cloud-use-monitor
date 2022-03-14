# Cloud Use Monitor Scripts

Simple scripts to help get info for Azure use.

Each script has unique cli inputs.  Use `-h` for information about the parameters required for each script.

Most scripts will require a service principal so that operations may be run against the Azure APIs.  The following environment variables may be set to omit the need for input for each script.

* CLIENT_ID
* CLIENT_SECRET
* SUBSCRIPTION_ID
* TENANT_ID
* REGION

## Scripts

1. `container_instances.py` Outputs the core use of container instance data from an Azure Region.

### Container Instance Core Usage

Will monitor the `https://management.azure.com/subscriptions/{subscription_id}/providers/Microsoft.ContainerInstance/locations/{region}/usages?api-version=2021-09-01` API over the time provided when the script is called.  This will output data transformed across the different CPU types for easy charting over time.
