# Automatic invoicing

Github gives away an extraordinary amount of cloud storage and cloud compute for free. You can use these resources for pretty much whatever you want, including email automation. To that end, this repo is an open source implementation that uses Github Actions to automate sending billing invoices by email.

Sample output: [HTML]( https://htmlpreview.github.io/?https://github.com/chriscarrollsmith/auto-invoicer/blob/main/sample_output/2023-05-29.html) | [PDF](https://github.com/chriscarrollsmith/auto-invoicer/blob/main/sample_output/2023-05-29.pdf)

![](https://github.com/chriscarrollsmith/auto-invoicer/blob/main/sample_output/2023-05-29.jpg)

## Setup

Fork your own copy of the repo using the "Fork" button on Github. From a command line interface, clone the forked repo locally with the command,

```
git clone https://github.com/{YOURUSERNAME}/auto-invoicer.git
```

Make sure to replace {YOURUSERNAME} with your actual username.

Next, open the project folder:

```
cd auto-invoicer
```

Before proceeding, you will need to [install the poetry package manager](https://python-poetry.org/docs/) on your machine. To install poetry in most shells:

```
curl -sSL https://install.python-poetry.org | python3 -
```

To install poetry in Windows Powershell:

```
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -
```

Once you've installed poetry, you can install package dependencies with the command,

```
poetry install
```

Also copy the `sample.env` file to `.env`:

```
cp sample.env .env
```

## Customize invoice template

In the `template` folder, you will find a markdown template that controls the look of your invoice. Customize it to your liking.

The code for this application is designed to be fairly flexible and extensible, so it should be able to accommodate a lot of different invoice formats (or even other types of documents).

If you add any CSS to the template, make sure that opening and closing braces are on different lines, or they will be interpreted as variables to be replaced. Note that separate stylesheets are not supported, so all CSS styling must go in the template file.

## Set environment variables

All variables referenced in braces in the template (e.g., `{variable_name}`) must be defined in the .env file except `invoice_number`, which will be constructed dynamically based on `start_date`, `interval_unit`, and `interval_quantity`.

If you add any variables to the template, you will need to add them to `.env`. If you delete any variables, you should delete them from `.env`. Private information should *always* be handled with variables, especially if you are uploading any code to Github.

## Build and send invoices locally

To build invoices locally, open `auto_invoicer/generate_invoice.py` and change the `html_output` and `pdf_output` options to `True`. Built HTML and PDF files will go into the `output` directory.

To send your invoice by email, open `auto_invoicer/generate_invoice.py` and change the `send_email` option to `True`.

Once you've set your desired options, run,

```
poetry shell
python generate_invoice.py
```

## Automate invoicing with Github Actions

If you're going to be invoicing from a public repo, set `html_output` and `pdf_output` to `False` and `send_email` to `True` in `auto_invoicer/generate_invoice.py`, and then commit and push your changes to Github.

Next, set up Github CLI by following the instructions [here](https://github.com/cli/cli#installation). Then log in to Github with the command,

```
gh auth login
```

You will be prompted to log in to Github in your browser. Once you've logged in, you can create Github secrets from your `.env` file with the command,

```
gh secret set -f .env
```

This will save your private variables to a secure Github vault, where they will be accessible to Github Actions. You can check that your secrets were saved correctly with the command,

```
gh secret list
```

Next, you will need to create a Github Actions workflow from the command line with the command,

```
python auto_invoicer/create_workflow.py
```

This will create a workflow file in the `.github/workflows` directory. You can check that the workflow was created correctly with the command,

```
gh workflow list
```

Commit and push your Github Actions workflow to Github. Make sure the workflow is enabled by following the instructions [here](https://docs.github.com/en/actions/managing-workflow-runs/disabling-and-enabling-a-workflow). Your email invoice will now be sent automatically on the schedule you specified in the `.env` file.

To test that your email is sent correctly, try setting `recipient_email` in the `.env` file to your own email address and `send_email` to `True` in `auto_invoicer/generate_invoice.py`, and edit `send_invoice.yml` so that it executes on push rather than on a schedule:

```
on:
  push:
```

Then commit and push your changes to Github. You should now be able to see your workflow running in the "Actions" tab of your repo, and you should receive an invoice by email.

## An important note about security

DO NOT PUSH YOUR `.env` FILE OR `output` FILES TO A PUBLIC REPO! These are listed in `.gitignore` to protect you from accidentally sharing personal info!

## Contributing

If you have any questions, comments, or suggestions, please feel free to open an issue or submit a pull request. I'm always happy to hear from you!

Items that still need work:

- Add support for automatically building a workflow that executes on push or a manual trigger (for testing purposes)
- Add support for BCC/CC and multiple recipients
- Add support for including a custom message in the email
- Add more control over whether HTML invoice is included in email body and whether PDF invoice is attached to email
- Address the issue of spam filters blocking the email (maybe would be fixed by custom message mentioned above, or by initial message on push, asking recipient to add sender to contacts)
- Figure out how to get Gmail SMTP auth to work
- Figure out if it would be best to recommend doing deployment on a separate branch from main, and what it would take to do multiple deployments on multiple branches (can you set secrets by branch rather than by repo?)
