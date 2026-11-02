import requests

def generate_banner(direction):
    """Generates a massive text banner using dummyimage.com."""
    if direction == "LONG":
        text = "BUY"
        color = "00C851" # Green
        text_color = "ffffff"
    else:
        text = "SELL"
        color = "ff4444" # Red
        text_color = "ffffff"

    # DummyImage creates a perfect solid color image with huge text
    url = f"https://dummyimage.com/800x400/{color}/{text_color}.png&text={text}"
    
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            file_path = "banner.png"
            with open(file_path, "wb") as f:
                f.write(response.content)
            return file_path
    except Exception as e:
        print(f"Banner generation error: {e}")
    return None
