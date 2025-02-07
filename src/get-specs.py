import os
import csv
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from google import genai

load_dotenv()  # Load variables from .env file

# Replace with your actual Gemini API key
API_KEY = os.environ.get("GEMINI_API_KEY")  # Best practice: store API key in environment variable
if not API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set.")

# Gemini end point
# genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

webRequestHeader = {
    "User-Agent": "My-Custom-User-Agent/1.0",  # Example User-Agent
    "Accept-Language": "en-US,en;q=0.9",      # Example Accept-Language
    "Content-Type": "text/html"
}

def sendtoGemini(data):
    prompt = """break down this text into specifications:{data}

    Use this JSON schema:

    Specs = {'equipment_name': str, 'specifications': list[str]}
    Return: list[Specs]"""
    
    client = genai.Client(api_key=API_KEY)
    response = client.models.generate_content(
        model='gemini-2.0-flash',
        contents=prompt,
    )

    # Use the response as a JSON string.
    print(response.text)

def fetch_webpage(url,webRequestHeader):
    """Fetches a webpage using requests and handles potential errors."""
    try:
        response = requests.get(url, headers=webRequestHeader, timeout=10)  # Add a timeout for safety
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None


def extract_text(html_content):
    """Extracts text content from HTML using BeautifulSoup."""
    if not html_content:
        return ""

    soup = BeautifulSoup(html_content, "html.parser")

    # Remove script and style elements
    for script in soup(["script", "style"]):
        script.extract()

    text = soup.get_text(separator='\n')  # Use newline as separator for better readability
    lines = (line.strip() for line in text.splitlines())  # Remove empty lines and leading/trailing whitespace
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))  # Remove extra spaces
    text = '\n'.join(chunk for chunk in chunks if chunk) # Rejoin with newlines and filter out empty chunks.
    return text


def process_csv(csv_filepath):
    """Reads URLs from a CSV and processes each webpage."""
    try:
        with open(csv_filepath, 'r', encoding='utf-8') as csvfile:  # Handle potential encoding issues
            reader = csv.DictReader(csvfile)  # Assumes CSV has a header row
            for row in reader:
                url = row.get("url")  # Assumes the URL column is named "url"
                make = row.get("manufacturer")
                if url:
                    print(f"Processing: {url}")
                    html_content = fetch_webpage(url,webRequestHeader)
                    if html_content:
                        extracted_text = extract_text(html_content)
                        if extracted_text:
                            # Save the extracted text to a file (optional):
                            filename = "./data/results/" + make + "_extract_" + url.replace("://", "_").replace("/", "_") + ".txt"  # Create safe filename
                            with open(filename, 'w', encoding='utf-8') as outfile:
                                outfile.write(extracted_text)
                            print(f"Extracted text saved to {filename}")
                            specData = sendtoGemini(extracted_text)
                        else:
                            print(f"No extractable text found on {url}")
                    else:
                        print(f"Failed to fetch {url}")
                else:
                    print("URL not found in row.")

    except FileNotFoundError:
        print(f"CSV file not found: {csv_filepath}")
    except csv.Error as e:
        print(f"Error reading CSV: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")



if __name__ == "__main__":
    csv_file = "./data/locations/urls.csv"  # Replace with your CSV filename
    process_csv(csv_file)