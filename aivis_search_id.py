import requests
# AivisSpeechのキャラクター一覧を取得
try:
    response = requests.get('http://127.0.0.1:10101/speakers')
    for sp in response.json():
        for style in sp['styles']:
            print(f"{sp['name']} ({style['name']}): {style['id']}")
except:
    print("AivisSpeechを起動してください")