import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_search(client):
    response = client.post('/search', json={'query': 'machine learning'})
    assert response.status_code == 200

def test_store(client):
    response = client.post('/store', json={'query': 'machine learning', 'result': 'result text'})
    assert response.status_code == 201
