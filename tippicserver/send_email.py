# -*- coding: utf-8 -*-
# pip install boto3
import boto3
# the email package was already included, so no need to install
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

ses_client = boto3.client('ses', region_name='us-east-1')


def send_mail(sender: str, recipients: list, title: str, body: str, attachments: dict) -> list:
    '''
    This sends a new Mail to every recipient in the recipients lists. It sends one mail per recipient
    It returns a  list of responses (one per mail)
    attachments look like this {"filename1": "/path/to/file1", "filename2": "/path/to/file2" ... }
    '''
    # create raw email
    msg = MIMEMultipart()
    msg['Subject'] = title
    msg['From'] = sender

    charset = "utf-8"

    part = MIMEText(body.encode(charset), 'html', charset)
    msg.attach(part)

    for attachment in attachments:
        part = MIMEApplication(open(attachments[attachment], 'rb').read())
        part.add_header('Content-Disposition', 'attachment', filename=attachment)
        msg.attach(part)

    # end create raw email
    responses = []
    for recipient in recipients:
        # important: msg['To'] has to be a string. If you want more than one recipient,
        # you need to do sth. like ", ".join(recipients)
        msg['To'] = recipient
        response = ses_client.send_raw_email(
            Source=sender,
            Destinations=[recipient],  # here it has to be a list, even if it is only one recipient
            RawMessage={
                'Data': msg.as_string()  # this generates all the headers and stuff for a raw mail message
            })
        responses.append(response)
    return responses


def send_mail_with_qr_attachment(sender: str, recipients: list, title: str, body: str, qr_input) -> list:
    '''
    Sends an email via ses with a qr attachment called 'qr_code.png' which is generated on the fly
    '''
    # create raw email
    msg = MIMEMultipart()
    msg['Subject'] = title
    msg['From'] = sender

    charset = "utf-8"

    # qr attachment from png stream
    part = MIMEApplication(create_qr_buffer(qr_input).getvalue())
    part.add_header('Content-Disposition', 'attachment', filename='qr_code.png')
    part.add_header('Content-ID', '<qr_code.png>')
    msg.attach(part)

    # attach static images
    attachments = {'@2xbeta_logo.png': '/opt/tippic-server/tippicserver/statics/@2xbeta_logo.png'}
    for attachment in attachments:
        part = MIMEApplication(open(attachments[attachment], 'rb').read())
        part.add_header('Content-Disposition', 'attachment', filename=attachment)
        part.add_header('Content-ID', '<%s>' % attachment)
        msg.attach(part)

    # html content
    part = MIMEText(body.encode(charset), 'html', charset)
    msg.attach(part)

    # end create raw email
    responses = []
    for recipient in recipients:
        # important: msg['To'] has to be a string. If you want more than one recipient,
        # you need to do sth. like ", ".join(recipients)
        msg['To'] = recipient
        response = ses_client.send_raw_email(
            Source=sender,
            Destinations=[recipient],  # here it has to be a list, even if it is only one recipient
            RawMessage={
                'Data': msg.as_string()  # this generates all the headers and stuff for a raw mail message
            })
        responses.append(response)
    return responses


def create_qr_buffer(qr_input):
    import io
    import pyqrcode
    import png
    buffer = io.BytesIO()
    qr = pyqrcode.create(qr_input)
    qr.png(buffer, scale=10)
    return buffer