from flask import Flask, request, redirect, jsonify
import string
import random
import sqlite3
from datetime import datetime

app = Flask(__name__)

# Database setup
conn = sqlite3.connect('urls.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS urls (
                    short_code TEXT PRIMARY KEY,
                    original_url TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')

def generate_short_code(length=6):
    """Generate a random short code for URLs."""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

@app.route('/shorten', methods=['POST'])
def shorten_url():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data received'}), 400

        if 'url' not in data:
            return jsonify({'error': 'URL is required'}), 400

        original_url = data['url']

        if not original_url.startswith(('http://', 'https://')):
            return jsonify({'error': 'Invalid URL format'}), 400

        short_code = generate_short_code()

        with sqlite3.connect('urls.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM urls WHERE short_code = ?', (short_code,))
            if cursor.fetchone():
                return jsonify({'error': 'Short code already exists'}), 400

            cursor.execute('INSERT INTO urls (short_code, original_url) VALUES (?, ?)', (short_code, original_url))
            conn.commit()

        response_data = {
            'short_code': short_code,
            'original_url': original_url,
            'short_url': f'http://localhost:5002/redirect?code={short_code}'
        }
        return jsonify(response_data)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/redirect', methods=['GET'])
def redirect_to_url():
    short_code = request.args.get('code')

    if not short_code:
        return jsonify({'error': 'Short code is required'}), 400

    with sqlite3.connect('urls.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT original_url FROM urls WHERE short_code = ?', (short_code,))
        result = cursor.fetchone()

    if result:
        return redirect(result[0])
    else:
        return jsonify({'error': 'URL not found'}), 404

# Keep the connection open during requests
@app.teardown_appcontext
def close_connection(exception):
    pass

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)
