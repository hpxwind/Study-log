import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

def call_model(prompt:str) -> str:
    headers = {
        "Authorization": f"Bearer{os.getenv("LLM_API_KEY")}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": os.getenv("LLM_MODEL"),
        "messages": [
            {"role": "user", "content":prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 1024
    }
    resp = requests.post(f"{os.getenv("LLM_BASE_URL")}/chat/completions", headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    # 取出模型原始文本输出，直接丢给parser
    raw_content = data["choices"][0]["message"]["content"].strip()
    return raw_content