import os, sys
import shutil


def run(command):
    os.system(command)
    print("Done")


def upload(task_id, folder, filenames):
    print('will upload %s for task id %s' % (filenames, task_id))
    resolutions = ['mdpi', 'hdpi', 'xhdpi', 'xxhdpi', 'xxxhdpi']
    mac_resolutions = ['', '@2x', '@3x']

    command = 'aws s3 cp %s s3://kinapp-static/tasks/%s/android/%s --recursive --acl public-read'
    for resolution in resolutions:
        run(command % (folder, task_id, resolution))
        pass

    if not os.path.isdir('%s/ios' % folder):
        os.mkdir('%s/ios' % folder)

    for filename in filenames:
        full_src_path = '%s/%s' % (folder, filename)
        if os.path.isfile(full_src_path):
            for resolution in mac_resolutions:
                dot_index = filename.find('.')
                mac_filename = filename[:dot_index] + resolution + filename[dot_index:]
                full_dst_path = '%s/ios/%s' % (folder, mac_filename)
                shutil.copy2(full_src_path, full_dst_path)

    run('aws s3 cp %s/ios s3://kinapp-static/tasks/%s/ios --recursive --acl public-read' % (folder, task_id))


if len(sys.argv) < 4:
    print("usage upload <base fold> <from-task-num> <to-task-num>")
    exit(1)

for taskNum in range(int(sys.argv[2]), int(sys.argv[3])):
    imagesFolder = '%s/%s/Images' % (sys.argv[1], taskNum)
    files = os.listdir(imagesFolder)
    print('will upload files for task %s, from %s' % (taskNum, imagesFolder))
    upload(taskNum, imagesFolder, files)

