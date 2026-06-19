import requests

import os

api_key = os.environ.get("GROQ_API_KEY", "")
url = "https://api.groq.com/openai/v1/models"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

response = requests.get(url, headers=headers)
if response.status_code == 200:
    models = response.json().get('data', [])
    print("Available Models:")
    for model in models:
        # We look for models that might be vision-enabled
        if 'vision' in model['id'].lower():
            print(f"- {model['id']} (Vision capable)")
        else:
            print(f"- {model['id']}")
else:
    print(f"Error: {response.status_code}")
    print(response.text)
