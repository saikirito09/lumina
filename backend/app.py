from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
import subprocess
import json
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

cred = credentials.Certificate('firebase_credentials.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

@app.route('/search', methods=['POST'])
def search():
    data = request.json
    query = data.get('query')

    curl_command = [
        'curl',
        'https://api.openai.com/v1/chat/completions',
        '-H', 'Content-Type: application/json',
        '-H', f'Authorization: Bearer {os.getenv("OPENAI_API_KEY")}',
        '-d', json.dumps({
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": query}
            ]
        })
    ]

    result = subprocess.run(curl_command, capture_output=True, text=True)

    if result.returncode != 0:
        return jsonify({'error': 'Failed to communicate with OpenAI API'}), 500

    response_json = json.loads(result.stdout)
    completion_text = response_json.get('choices', [{}])[0].get('message', {}).get('content', '')

    return jsonify({'result': completion_text})

@app.route('/store', methods=['POST'])
def store():
    data = request.json
    query = data.get('query')
    result = data.get('result')

    # Store in Firebase
    db.collection('search_results').add({'query': query, 'result': result})
    return jsonify({"status": "success"}), 201

if __name__ == '__main__':
    app.run(debug=True)
