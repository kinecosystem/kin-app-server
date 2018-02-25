import requests

task = { 'title': 'do you know horses?',
          'desc': 'horses_4_dummies',
          'type': 'questionnaire',
          'kin_reward': 1,
          'min_to_complete': 2,
          'start_date': '2013-05-11T21:23:58.970460+00:00',
          'tags': ['music', 'crypto', 'movies', 'kardashians', 'horses'],
          'author': 
            {'name': 'om-nom-nom-food', 'image_url': 'http://inter.webs/horsie.jpg'},
          'items': [
            {
             'id': '435', 
             'text': 'what animal is this?',
             'type': 'textimage',
                 'results': [
                        {'id': '235',
                         'text': 'a horse!', 
                         'image_url': 'cdn.helllo.com/horse.jpg'},
                            {'id': '2465436',
                         'text': 'a cat!', 
                         'image_url': 'cdn.helllo.com/kitty.jpg'},
                         ],
            }]
        }

resp = requests.post('http://localhost:8000/task/add', json={'id': 1, 'task': task})
print(resp.status_code)
