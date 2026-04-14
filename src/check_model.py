import requests, json

def test_ollama():
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "qwen2.5-coder:7b-instruct-q4_k_m",
        "prompt": "Say 'OK'",
        "stream": False,
        "options": {"num_ctx": 4096, "num_predict": 50}
    }
    r = requests.post(url, json=payload)
    print("Status:", r.status_code)
    print("Response:", json.loads(r.text).get("response", "")[:100])

if __name__ == "__main__":
    test_ollama()