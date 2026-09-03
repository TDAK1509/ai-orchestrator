def build_follow_up_message(text: str) -> dict:
    return {"type": "user", "message": {"role": "user", "content": text}}
