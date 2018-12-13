#! /bin/bash

# this script uploads a file from your local machine to our s3 bucket.

for file in $(find $1 -name '*.png' -or -name '*.jpg' -maxdepth 1)
do
filename=$(basename -- "$file")
extension="${filename##*.}"
filename="${filename%.*}"
aws s3 cp $file s3://kinapp-static/discovery/{}/android/mdpi/ --acl public-read
aws s3 cp $file s3://kinapp-static/discovery/{}/android/hdpi/ --acl public-read
aws s3 cp $file s3://kinapp-static/discovery/{}/android/xhdpi/ --acl public-read
aws s3 cp $file s3://kinapp-static/discovery/{}/android/xxhdpi/ --acl public-read
aws s3 cp $file s3://kinapp-static/discovery/{}/android/xxxhdpi/ --acl public-read
aws s3 cp $file s3://kinapp-static/discovery/{}/ios/ --acl public-read
aws s3 cp $file s3://kinapp-static/discovery/{}/ios/$filename@2x.$extension --acl public-read
aws s3 cp $file s3://kinapp-static/discovery/{}/ios/$filename@3x.$extension --acl public-read
echo $file
done

 aws s3 cp $1/logo/ s3://kinapp-static/discovery/{}/logo --recursive --acl public-read