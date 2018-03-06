#! /bin/bash

# this script uploads a file from your local machine to our s3 bucket.
# specifically, the files are uploaded to the brand_img folder. 
# once uploaded they become available through this url:
# https://s3.amazonaws.com/kinapp-static/brand_img/<your file name>
# to use this script, you need a few things:
# open a terminal and then - 
# install the AWSCLI with 'brew install awscli' (you only need to do this once)
# then export the secret key which Ami sent you via slack, using this command:
# export AWS_SECRET_ACCESS_KEY=<the secret access key you got from Ami>
# finally, you can now use the script to upload files:
# ./upload_to_s3.sh <your file>
# for example,
# ./upload_to_s3.sh ~/Downloads/cats_r_great.png

unset AWS_SESSION_TOKEN
unset AWS_SECURITY_TOKEN
export AWS_ACCESS_KEY_ID=AKIAJFKNURYVUAHA3ORQ
if [[ -z "${AWS_SECRET_ACCESS_KEY}" ]]; then
  echo "did you forget to export AWS_SECRET_ACCESS_KEY? aborting!"
  exit
 fi
aws --version
aws s3 cp $1 s3://kinapp-static/brand_img/ --acl public-read

filename=$(basename $1)
echo "your file is now at: https://s3.amazonaws.com/kinapp-static/brand_img/$filename"
