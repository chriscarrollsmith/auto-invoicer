import os
from dotenv import dotenv_values
from crontab import CronSlices

def get_cron_time(interval_unit, interval_quantity):
    if interval_unit == "month":
        cron_time = f'0 0 1 */{interval_quantity} *' # every interval_quantity months
    elif interval_unit == "week":
        cron_time = f'0 0 * * {interval_quantity}' # every interval_quantity weeks
    elif interval_unit == "day":
        cron_time = f'0 0 */{interval_quantity} * *' # every interval_quantity days
    else:
        raise ValueError("interval_unit must be 'month', 'week', or 'day'.")

    if not CronSlices.is_valid(cron_time):
        raise ValueError(f"The cron time '{cron_time}' is not valid.")

    return cron_time

def main():
    # Load .env variables
    config = dotenv_values(".env")

    # Retrieve interval settings from .env file
    start_date = config.get("start_date")
    interval_unit = config.get("interval_unit")
    interval_quantity = int(config.get("interval_quantity", 0))

    # Generate the cron time
    cron_time = get_cron_time(interval_unit, interval_quantity)

    # List all secrets from .env file
    secrets = list(config.keys())

    # Build environment variables for the secrets validation script
    secrets_env = "\n".join([f'            {secret}: ${{{{ secrets.{secret} }}}}' for secret in secrets])

    # Build secret validation script
    secrets_validation_script = "\n".join([f'            if [ -z "${{{secret}}}" ]; then echo "Missing secret: {secret}"; exit 1; fi' for secret in secrets])

    # Build environment variables for the script
    environment_variables = "\n".join([f'          {secret}: ${{{{ secrets.{secret} }}}}' for secret in secrets])

    # Create the Github Actions workflow file
    workflow = f"""name: Monthly Invoice Workflow

on:
  schedule:
    - cron: '{cron_time}'

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.11

      - name: Validate secrets
        env:
{secrets_env}
        run: |
{secrets_validation_script}

      - name: Install and configure Poetry
        uses: snok/install-poetry@v1

      - name: Install project
        run: |
          poetry shell
          poetry install --no-interaction

      - name: Generate invoice
        run: |
          poetry shell
          python auto_invoicer/generate_invoice.py
        env:
{environment_variables}
"""
    # Save the workflow to .github/workflows/send_invoice.yml
    os.makedirs('.github/workflows', exist_ok=True)
    with open('.github/workflows/send_invoice.yml', 'w') as file:
        file.write(workflow)


if __name__ == "__main__":
    main()
