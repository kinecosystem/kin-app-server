#! /bin/bash

# this script sets a Content-Disposition header for all the file in the /ios/ folder
# thus enabling download of files with "@" in the filename without escaping the url first.
aws s3 ls s3://kinapp-static/brand_img/ios/|awk {'print $4'} > objects.txt

while read line; do aws s3api copy-object --bucket kinapp-static  \
    --copy-source /kinapp-static/brand_img/ios/$line --key brand_img/ios/$line \
    --metadata-directive REPLACE --metadata Content-Disposition=$line --acl public-read; done < objects.txt