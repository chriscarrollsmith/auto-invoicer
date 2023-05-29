# Automatic invoicing

## Setup

Fork and clone repo
Install dependencies

## Customize invoice template

If you add any CSS, make sure open and close braces are on different lines, or they will be interpreted as variables to be replaced.

## Set environment variables

All variables referenced in braces in the template (e.g., `{variable_name}`) must be defined in the .env file except `invoice_number`, which will be constructed dynamically based on `start_date`, `interval_unit`, and `interval_quantity`.

## Build and send invoices locally

In `generate_invoice.py`, change `html_output` and `pdf_output` to `True`. The script will now build files and put them in the `output` directory.

Change `send_email` to True to send the invoice by email.

## Automate invoicing with Github Actions
If you're going to be invoicing from a public repo, set `html_output` and `pdf_output` to `False` in `generate_invoice.py`. This is very important for protecting any personal information in your invoice from being shared in a public repo!
Set up Github CLI: https://cli.github.com/manual/
Create Github secrets from .env file: `gh secret set -f .env`
Generate a Github Actions workflow from .env file: `auto_invoicer/create_workflow.py`
Commit and push Github Actions workflow
DO NOT PUSH `.env` FILE TO A PUBLIC REPO! It is listed in `.gitignore` to protect you from accidentally sharing personal info!