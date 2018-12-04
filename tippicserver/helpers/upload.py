import os


def run(command):
	os.system(command)

def upload(task_ids, filenames):
	resolutions = ['mdpi', 'hdpi', 'xhdpi', 'xxhdpi', 'xxxhdpi']
	mac_resolutions = ['', '@2x', '@3x']


	command = 'aws s3 cp %s s3://kinapp-static/tasks/%s/android/%s/ --acl public-read'
	for filename in filenames:
		for task_id in task_ids:
			for resolution in resolutions:
				run(command % (filename, task_id, resolution))
				pass

	command = 'aws s3 cp %s s3://kinapp-static/tasks/%s/ios/%s --acl public-read'
	for filename in filenames:
		for task_id in task_ids:
			for resolution in mac_resolutions:
				dot_index = filename.find('.')
				mac_filename = filename[:dot_index] + resolution + filename[dot_index:]
				run(command % (filename, task_id, mac_filename))



upload(['34'],['5aae99d5fdf66d72ee05812d_zoom.png'])
upload(['35'],['5aae99d5fdf66d72ee057584_zoom.png'])
upload(['36'],['5aae99d5fdf66d72ee057695_zoom.png'])
upload(['37'],['5aae99d5fdf66d72ee057a21_zoom.png'])
upload(['38'],['5aae99d8fdf66d72ee05f317_zoom.png'])
upload(['39'],['5aae99d5fdf66d72ee057693_zoom.png'])
upload(['40'],['5aae99d5fdf66d72ee0582d9_zoom.png'])
upload(['41'],['5aae99d5fdf66d72ee057516_zoom.png'])
upload(['42'],['5aae99d5fdf66d72ee057b23_zoom.png'])
upload(['43'],['5aae99d5fdf66d72ee057abb_zoom.png'])
upload(['44'],['5aae99d5fdf66d72ee0577a6_zoom.png'])