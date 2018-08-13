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
