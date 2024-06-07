from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
import subprocess
import json
import os
import requests
from dotenv import load_dotenv
from xml.etree import ElementTree as ET

load_dotenv()

app = Flask(__name__)

cred = credentials.Certificate('firebase_credentials.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

@app.route('/search', methods=['POST'])
def search():
    try:
        data = request.json
        query = data.get('query')

        # Step 1: Get keywords from ChatGPT
        curl_command = [
            'curl',
            'https://api.openai.com/v1/chat/completions',
            '-H', 'Content-Type: application/json',
            '-H', f'Authorization: Bearer {os.getenv("OPENAI_API_KEY")}',
            '-d', json.dumps({
                "model": "gpt-4o",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": f"Extract keywords from the following query: {query}"}
                ]
            })
        ]

        result = subprocess.run(curl_command, capture_output=True, text=True)

        if result.returncode != 0:
            return jsonify({'error': 'Failed to communicate with OpenAI API'}), 500

        response_json = json.loads(result.stdout)
        keywords = response_json.get('choices', [{}])[0].get('message', {}).get('content', '').strip()

        # Log the extracted keywords
        print(f"Extracted keywords: {keywords}")

        # Step 2: Fetch papers from arXiv
        arxiv_url = f'http://export.arxiv.org/api/query?search_query=all:{keywords}&start=0&max_results=10'
        response = requests.get(arxiv_url)

        if response.status_code != 200:
            return jsonify({'error': 'Failed to fetch data from arXiv API'}), 500

        papers = []
        root = ET.fromstring(response.content)
        for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
            paper = {
                'title': entry.find('{http://www.w3.org/2005/Atom}title').text,
                'summary': entry.find('{http://www.w3.org/2005/Atom}summary').text,
                'id': entry.find('{http://www.w3.org/2005/Atom}id').text,
                'published': entry.find('{http://www.w3.org/2005/Atom}published').text,
                'authors': [author.find('{http://www.w3.org/2005/Atom}name').text for author in entry.findall('{http://www.w3.org/2005/Atom}author')]
            }
            papers.append(paper)

        # Log the number of papers fetched
        print(f"Number of papers fetched: {len(papers)}")

        # Step 3: Summarize papers using ChatGPT
        summaries = []
        for paper in papers:
            summary_curl_command = [
                'curl',
                'https://api.openai.com/v1/chat/completions',
                '-H', 'Content-Type: application/json',
                '-H', f'Authorization: Bearer {os.getenv("OPENAI_API_KEY")}',
                '-d', json.dumps({
                    "model": "gpt-4o",
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": f"Summarize the following paper: {paper['summary']}"}
                    ]
                })
            ]

            summary_result = subprocess.run(summary_curl_command, capture_output=True, text=True)

            if summary_result.returncode != 0:
                return jsonify({'error': 'Failed to communicate with OpenAI API for summarizing'}), 500

            summary_response_json = json.loads(summary_result.stdout)
            summary_text = summary_response_json.get('choices', [{}])[0].get('message', {}).get('content', '').strip()

            summaries.append({
                'title': paper['title'],
                'summary': summary_text,
                'citation': f"{', '.join(paper['authors'])} ({paper['published'][:4]}). {paper['title']}. Retrieved from {paper['id']}"
            })

        # Log the summaries
        print(f"Summaries: {summaries}")

        # Step 4: Store results in Firebase
        db.collection('search_results').add({'query': query, 'keywords': keywords, 'results': summaries})

        return jsonify({'keywords': keywords, 'results': summaries})

    except Exception as e:
        print(e)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
