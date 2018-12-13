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

aws --version
filename=$(basename $1)
aws s3 cp $1 s3://kinapp-static/discovery/kinit/android/mdpi/ --acl public-read
aws s3 cp $1 s3://kinapp-static/discovery/kinit/android/hdpi/ --acl public-read
aws s3 cp $1 s3://kinapp-static/discovery/kinit/android/xhdpi/ --acl public-read
aws s3 cp $1 s3://kinapp-static/discovery/kinit/android/xxhdpi/ --acl public-read
aws s3 cp $1 s3://kinapp-static/discovery/kinit/android/xxxhdpi/ --acl public-read
aws s3 cp $1 s3://kinapp-static/discovery/kinit/ios/ --acl public-read
aws s3 cp $1 s3://kinapp-static/discovery/kinit/ios/$filename@2x --acl public-read
aws s3 cp $1 s3://kinapp-static/discovery/kinit/ios/$filename@3x --acl public-read