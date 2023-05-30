# Import required modules
import datetime
from dateutil import relativedelta
import markdown
from markdown.extensions.tables import TableExtension
import os
from dotenv import load_dotenv
import smtplib, ssl
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from pyhtml2pdf import converter
import tempfile


def get_required_env_vars(template_filepath):
    '''Get list of required environment variables by detecting placeholders in
    template file'''
    required_env_vars = []
    with open(template_filepath, 'r') as f:
        for line in f.readlines():
            if '{' in line and '}' in line:
                for i in range(line.count('{')):
                    required_env_vars.append(line.split('{')[i+1].split('}')[0])

    return required_env_vars


def calculate_invoice_number():
    current_date = datetime.datetime.now().date()
    start_date = datetime.datetime.strptime(os.environ["start_date"], '%Y-%m-%d').date()
    interval_quantity = int(os.environ["interval_quantity"])
    if os.environ["interval_unit"] == "month":
        invoice_number = (relativedelta.relativedelta(current_date, start_date).months + 1) / interval_quantity
    elif os.environ["interval_unit"] == "week":
        invoice_number = (relativedelta.relativedelta(current_date, start_date).weeks + 1) / interval_quantity
    elif os.environ["interval_unit"] == "day":
        invoice_number = (relativedelta.relativedelta(current_date, start_date).days + 1) / interval_quantity
    invoice_number = int(round(invoice_number, 0))
    return(str(invoice_number).zfill(3))


def validate_env_variables(required_env_vars: list):
    '''Check that all required environment variables are set'''
    # If not all required environment variables are set, raise error
    for env_var in required_env_vars:
        if env_var not in os.environ:
            print(f'Environment variable {env_var} not set.')
            raise ValueError(f'Environment variable {env_var} not set.')

    return None


def build_html_invoice(template_filepath, required_env_vars):
    '''Build HTML invoice from markdown template file and environment
    variables'''
    # Read the template file
    with open(template_filepath, 'r') as f:
        template = f.read()

    # Replace placeholders with real values
    for var in required_env_vars:
        template = template.replace('{'+var+'}', os.environ[var])

    # Convert markdown to html
    html = markdown.markdown(template, extensions=[TableExtension(use_align_attribute=True)])

    return html


def write_to_html_file(filepath: str, html: str):
    '''Write to HTML file at the given filepath with the given HTML content'''
    with open(filepath, 'w') as f:
        f.write(html)


def extract_assets_from_html(html: str) -> list:
    '''Extract asset filepaths from 'src' attributes in the HTML string'''
    assets = []
    # For any string in html of format 'src="*"', extract the filepath
    for i in range(html.count('src="')):
        filepath = html.split('src="')[i+1].split('"')[0]
        assets.append(filepath)
    return assets


def modify_html_asset_paths(html: str, original_assets: list, new_assets: list) -> str:
    '''Replace asset filepaths in 'src' attributes in the HTML string with new filepaths'''
    for original_asset, new_asset in zip(original_assets, new_assets):
        html = html.replace(f'src="{original_asset}"', f'src="{new_asset}"')
    return html


def get_assets_paths_from_output_folder(assets_dir: str, html_dir: str, original_assets: list) -> list:
    '''Modify the links to correctly render from the HTML file's new directory'''
    # Get the assets paths relative to the Python process
    python_assets_paths = get_assets_paths_from_python_process(assets_dir, original_assets)

    # Now convert these Python-process paths into paths relative to the output folder
    new_assets = [os.path.relpath(path, start=html_dir) for path in python_assets_paths]

    return new_assets


def get_assets_paths_from_email(original_assets: list):
        new_assets_paths = []
        for asset in original_assets:
            # Get the filename and prefix it with 'cid:'
            basename = os.path.basename(asset)
            new_assets_paths.append(f'cid:{basename}')
        return new_assets_paths


def get_assets_paths_from_python_process(assets_dir: str,
                                         original_assets: list) -> list:
    '''Prepend assets_dir prefix to the asset filenames to get paths
    accessible by the Python process'''
    python_assets_paths = []
    for asset in original_assets:
        asset_path = os.path.join(assets_dir, os.path.basename(asset))
        if not os.path.exists(asset_path):
            raise ValueError(f"Asset {os.path.basename(asset)} not found in the provided assets directory {assets_dir}")
        python_assets_paths.append(asset_path)
    return python_assets_paths


def output_files(output_dir: str, html: str, assets_dir: str = "/",
                 html_output: bool = True, pdf_output: bool = True):
    '''Output HTML and PDF files and copy any assets to output directory'''

    if not html_output and not pdf_output:
        return None, None
    
    # Create the output directory if it does not exist
    os.makedirs(output_dir, exist_ok=True)

    temp_file = None  
    try:
        original_assets = extract_assets_from_html(html)
        if html_output:
            html_filepath = os.path.join(output_dir, f"{datetime.datetime.now():%Y-%m-%d}.html")
            new_assets = get_assets_paths_from_output_folder(assets_dir, output_dir, original_assets)
            html = modify_html_asset_paths(html, original_assets, new_assets)
            write_to_html_file(html_filepath, html)
        elif pdf_output:
            # Creating an HTML tempfile if we only need it for creating a PDF
            temp_file = tempfile.NamedTemporaryFile(suffix=".html", delete=False)
            html_filepath = temp_file.name
            temp_dir = os.path.dirname(html_filepath)
            new_assets = get_assets_paths_from_output_folder(assets_dir, temp_dir, original_assets)
            html = modify_html_asset_paths(html, original_assets, new_assets)
            write_to_html_file(html_filepath, html)
        else:
            return None, None

        # pdf_output condition
        if pdf_output:
            pdf_filepath = os.path.join(output_dir, f"{datetime.datetime.now():%Y-%m-%d}.pdf")
            # Convert HTML to PDF and save it to pdf_filepath
            converter.convert(f'file:///{os.path.abspath(html_filepath)}', pdf_filepath)
        else:
            pdf_filepath = None

    finally:
        # If we needed an HTML tempfile, clean it up
        if temp_file:
            temp_file.close()
            os.remove(html_filepath)

    return html_filepath, pdf_filepath


def send_email_invoice(subject: str, html: str, assets_dir: str = "/", pdf_filepath: str = None):
    '''Send email with HTML body and optional PDF attachment'''
    
    original_assets = extract_assets_from_html(html)
    email_assets_paths = get_assets_paths_from_email(original_assets)
    email_html = modify_html_asset_paths(html, original_assets, email_assets_paths)
    files_to_attach = get_assets_paths_from_python_process(assets_dir, original_assets)

    # Construct MIME email object
    message = MIMEMultipart("related")
    message["Subject"] = subject
    message["From"] = os.environ['email']
    message["To"] = os.environ['recipient_email']
    msgAlternative = MIMEMultipart('alternative')
    message.attach(msgAlternative)
    msgText = MIMEText(email_html, 'html')
    msgAlternative.attach(msgText)

    # Attach files
    for f in files_to_attach:
        basename = os.path.basename(f)
        with open(f, "rb") as fil:
            part = MIMEImage(fil.read())
            part.add_header('Content-ID', '<{}>'.format(basename))
            part.add_header('Content-Disposition', 'inline', filename=basename)
        message.attach(part)

    # If PDF filepath is specified, attach it to the email
    if pdf_filepath is not None:
        with open(pdf_filepath, "rb") as fil:
            part = MIMEApplication(fil.read(), Name=os.path.basename(pdf_filepath))
            part['Content-Disposition'] = f'attachment; filename="{os.path.basename(pdf_filepath)}"'
        message.attach(part)

    # Otherwise, make HTML tempfile and convert it to PDF tempfile
    else:
        html_file_descriptor, html_file_path = tempfile.mkstemp(suffix=".html")
        pdf_file_descriptor, pdf_file_path = tempfile.mkstemp(suffix=".pdf")
        try:
            # Make tempfiles for any assets referenced in the html
            temp_dir = os.path.dirname(html_file_path)
            new_assets = get_assets_paths_from_output_folder(assets_dir, temp_dir, original_assets)
            tempfile_html = modify_html_asset_paths(html, original_assets, new_assets)
            write_to_html_file(html_file_path, tempfile_html)
            converter.convert(f'file:///{html_file_path}', pdf_file_path)
            with open(pdf_file_path, "rb") as fil:
                pdf_filename = str(datetime.datetime.now().strftime('%Y-%m-%d'))+'.pdf'
                part = MIMEApplication(fil.read(), Name=pdf_filename)
                part['Content-Disposition'] = f'attachment; filename="{pdf_filename}"'
            # attach PDF to the email
            message.attach(part)
        # Delete tempfiles
        finally:
            os.close(html_file_descriptor)
            os.close(pdf_file_descriptor)
            os.remove(html_file_path)
            os.remove(pdf_file_path)

    # Log in to email server and send email
    context = ssl.create_default_context()
    with smtplib.SMTP(os.environ['email_server'], port = 587, timeout=30) as server:
        server.ehlo()  # Can be omitted
        server.starttls(context=context)
        server.ehlo()  # Can be omitted
        server.login(os.environ['email_username'], os.environ['email_password'])
        server.sendmail(os.environ['email'], os.environ['recipient_email'], message.as_string())


if __name__ == '__main__':

    # Adjust option to control template file path, whether we send email, 
    # and whether and where we output HTML and PDF files. Use relative paths.
    template_filepath = 'template/invoice_template.md'
    assets_dir = 'template/assets'
    output_dir = 'output'
    send_email = True
    html_output = False
    pdf_output = False

    # If .env exists, load environment variables from .env
    # (Note: .env should not be committed to version control! For cloud
    # deployment, use secrets instead.)
    if os.path.exists('.env'):
        load_dotenv()

    # Get list of required environment variables by detecting placeholders in
    # template file
    required_env_vars = get_required_env_vars(template_filepath)

    # If date is a required environment variable, set it to today's date
    if "date" in required_env_vars:
        date = datetime.datetime.now().strftime('%Y-%m-%d')
        os.environ['date'] = date
    
    # If invoice_number is a required environment variable, calculate it as the
    # number of intervals since start_date   
    if "invoice_number" in required_env_vars and os.environ["start_date"] is not None:
        os.environ['invoice_number'] = calculate_invoice_number()
    elif "invoice_number" in required_env_vars and os.environ["start_date"] is None:
        raise ValueError("start_date environment variable is required to calculate invoice_number")
    
    # Check that all required environment variables are set
    validate_env_variables(required_env_vars)

    # Build HTML invoice from markdown template file and environment
    # variables
    html = build_html_invoice(template_filepath, required_env_vars)

    # Output HTML and PDF files
    html_filepath, pdf_filepath = output_files(output_dir, html, assets_dir, html_output, pdf_output)

    # If we're not sending email, exit here
    if send_email:
        # If invoice_number is a required environment variable, add it to the
        # subject line
        if os.environ["invoice_number"] in required_env_vars:
            subject_line = "Invoice " + os.environ["invoice_number"]
        else:
            subject_line = "Invoice"
        # Send email with HTML body and, optionally, PDF attachment
        if pdf_output:
            send_email_invoice(subject_line, html, assets_dir, pdf_filepath)
        else:
            send_email_invoice(subject_line, html, assets_dir)
