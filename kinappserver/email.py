# -*- coding: utf-8 -*-
# pip install boto3
import boto3
# the email package was already included, so no need to install
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# replace the following with your values
sender = "backup@kinitapp.com"  # this has to be a verified mail in SES
recipients = ["ami.blonder@kik.com"]  # replace with valid mails
mail_subject = "This is the mail subject line"
mail_body = """\
<html>
<head></head>
<body>
<h1>Hello!</h1>
<p>Please save the attached backup code somewhere nobody can read</p>
</body>
</html>
"""
attachments = {"test.png": "./test.png"}
aws_access_key_id = ""
aws_secret_access_key = ""
aws_region = "us-east-1"  # pick the right one
charset = "utf-8"


def send_mail(sender: str, recipients: list, title: str, body: str, attachments: dict, client: object) -> list:
    '''
    This sends a new Mail to every recipient in the recipients lists. It sends one mail per recipient
    It returns a  list of responses (one per mail)
    attachments look like this {"filename1": "/path/to/file1", "filename2": "/path/to/file2" ... }
    '''
    # create raw email
    msg = MIMEMultipart()
    msg['Subject'] = title
    msg['From'] = sender

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
        response = client.send_raw_email(
            Source=sender,
            Destinations=[recipient],  # here it has to be a list, even if it is only one recipient
            RawMessage={
                'Data': msg.as_string()  # this generates all the headers and stuff for a raw mail message
            })
        responses.append(response)
    return responses


ses_client = boto3.client('ses', region_name=aws_region)

if __name__ == '__main__':
    responses = send_mail(
        sender,
        recipients,
        mail_subject,
        mail_body,
        attachments,
        ses_client)

    print(responses)