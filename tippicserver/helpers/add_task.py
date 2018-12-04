import requests

task = { 'title': 'do you know horses?',
          'desc': 'horses_4_dummies',
          'type': 'questionnaire',
          'price': 1,
          'min_to_complete': 2,
          'tags': ['music', 'crypto', 'movies', 'kardashians', 'horses'],
          'provider': 
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

resp = requests.post('http://localhost:80/internal/task/add', json={'id': '1', 'task': task})
print(resp.status_code)
