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
import shutil
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


def output_files(output_dir: str, html: str, assets_dir: str = None,
                 html_output: bool = True, pdf_output: bool = True):
    '''Output HTML and PDF files and copy any assets to output directory'''
    html_filepath = os.path.join(output_dir, str(datetime.datetime.now().strftime('%Y-%m-%d'))+'.html')
    pdf_filepath = os.path.join(output_dir, str(datetime.datetime.now().strftime('%Y-%m-%d'))+'.pdf')
    
    if html_output:
        # Write to an HTML file
        with open(html_filepath, 'w') as f:
            f.write(html)
        if assets_dir is not None:
            # Copy any assets referenced in the html to the output directory
            output_assets_dir = os.path.join(output_dir, os.path.basename(assets_dir))
            os.makedirs(output_assets_dir, exist_ok=True)
            for filename in os.listdir(assets_dir):
                if filename in html:
                    original = os.path.join(assets_dir, filename)
                    copy = os.path.join(output_assets_dir, filename)
                    shutil.copy(original, copy)

    if pdf_output:
        # Convert HTML to PDF
        converter.convert(f'file:///{os.path.abspath(html_filepath)}', pdf_filepath)

    return html_filepath, pdf_filepath


def send_email_invoice(subject: str, html: str, assets_dir: str = None, pdf_filepath: str = None):
    '''Send email with HTML body and optional PDF attachment'''
    files_to_attach = []
    
    # For any string in html of format 'src="*"', extract the filepath
    for i in range(html.count('src="')):
        filepath = html.split('src="')[i+1].split('"')[0]
        # Prefix the filepath with the prefix of the assets directory
        # (necessary because the HTML file's root directory isn't the same as
        # the root directory of the Python app)
        if assets_dir is not None:
            assets_prefix = os.path.dirname(assets_dir)
            modified_filepath = os.path.join(assets_prefix, filepath)
        # add the filepath to attachments list
        files_to_attach.append(modified_filepath)
        # get the filename
        basename = os.path.basename(modified_filepath)
        # replace the filepath with the filename in the html
        html = html.replace(filepath, ("cid:"+basename))

    # Construct MIME email object
    message = MIMEMultipart("related")
    message["Subject"] = subject
    message["From"] = os.environ['email']
    message["To"] = os.environ['recipient_email']
    msgAlternative = MIMEMultipart('alternative')
    message.attach(msgAlternative)
    msgText = MIMEText(html, 'html')
    msgAlternative.attach(msgText)
    for f in files_to_attach or []:
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
            if assets_dir is not None:
                html = html.replace('cid:', '')
                assets_file_descriptors = []
                assets_file_paths = []
                for filename in files_to_attach:
                    suffix = os.path.splitext(filename)[1]
                    asset_file_descriptor, asset_file_path = tempfile.mkstemp(suffix=suffix)
                    assets_file_descriptors.append(asset_file_descriptor)
                    assets_file_paths.append(asset_file_path)
                    # copy the asset file content to the temp file
                    shutil.copyfile(filename, asset_file_path)
                    # replace the asset filename in the html with the temp file path
                    html = html.replace(os.path.basename(filename), asset_file_path)
            with open(html_file_path, "w+b") as html_file:
                html_file.write(html.encode('utf-8'))
                html_file.seek(0)
                converter.convert(f'file:///{html_file.name}', pdf_file_path)
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
            for assets_file_descriptor in assets_file_descriptors:
                os.close(assets_file_descriptor)
            for assets_file_path in assets_file_paths:
                os.remove(assets_file_path)

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
    # and whether and where we output HTML and PDF files
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
