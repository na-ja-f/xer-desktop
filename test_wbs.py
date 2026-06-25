import json
import requests
res = requests.get('http://127.0.0.1:8000/project/wbs_hierarchy?context=controller')
data = res.json()
if data.get('records'):
    root = data['records'][0]
    print(list(root.keys()))
