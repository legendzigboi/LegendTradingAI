import os
import requests

def generate_banner(direction):
    """Uses local buy.png or sell.png if they exist, otherwise generates one."""
    if direction == "LONG":
        local_file = "buy.png"
        color = "00C851"
        text = "BUY"
    else:
        local_file = "sell.png"
        color = "ff4444"
        text = "SELL"

    # 1. CHECK FOR LOCAL FILE FIRST (Instant)
    if os.path.exists(local_file):
        return local_file

    # 2. FALLBACK TO GENERATION (Slow)
    url = f"https://dummyimage.com/800x400/{color}/ffffff.png&text={text}"
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            file_path = f"generated_{local_file}"
            with open(file_path, "wb") as f:
                f.write(response.content)
            return file_path
    except Exception as e:
        print(f"Banner generation error: {e}")
    return None
