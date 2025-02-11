from flask import Flask, request, redirect, jsonify
import string
import random
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///urls.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class URL(db.Model):
    short_code = db.Column(db.String(6), primary_key=True)
    original_url = db.Column(db.String, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<URL {self.short_code}>'

# Initialize the database
with app.app_context():
    db.create_all()

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

        existing_url = URL.query.filter_by(short_code=short_code).first()
        if existing_url:
            return jsonify({'error': 'Short code already exists'}), 400

        new_url = URL(short_code=short_code, original_url=original_url)
        db.session.add(new_url)
        db.session.commit()

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

    url = URL.query.filter_by(short_code=short_code).first()

    if url:
        return redirect(url.original_url)
    else:
        return jsonify({'error': 'URL not found'}), 404

# Keep the connection open during requests
@app.teardown_appcontext
def close_connection(exception):
    pass

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)
