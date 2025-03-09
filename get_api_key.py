from app import app, APIKey

with app.app_context():
    api_key = APIKey.query.first()
    if api_key:
        print(f'API Key: {api_key.key}')
    else:
        print('No API key found')
