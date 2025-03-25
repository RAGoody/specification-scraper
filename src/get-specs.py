import os
import sys
import csv
import re
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from google import genai
import json  # Import json module
import time  # Import time module for adding delays

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
    """
    Sends the extracted text data to the Gemini API to generate specifications.
    
    Args:
        data (str): The extracted text data from the webpage.
    
    Returns:
        str: The parsed JSON response from the Gemini API.
    """
    enablePause = False
    prompt = """break down this '""" + data + """'into specifications

    Use this JSON schema:

    Specs = {
        'equipment_name': str,
        'specifications': {
                'specificationSection' : {
                        specificationName:specificationValue
                    }
            }
    }
    Return: Specs"""

    print(f"{prompt}")    
    client = genai.Client(api_key=API_KEY)
    response = client.models.generate_content(
        model='gemini-1.5-flash',
        contents=prompt,
    )
    print(f"")
    print(f"")
    print(f"{response.text}")
    
    # Remove all escaped characters and new line characters from the response text
    cleaned_response_text = response.text.replace('n\n', '')
    cleaned_response_text = response.text.replace('\n', '')
    cleaned_response_text = response.text.replace('\"', '"')

    # Extract JSON from the cleaned response text
    start_index = cleaned_response_text.find("```json")
    end_index = cleaned_response_text.find("```", start_index + 6)
    if start_index != -1 and end_index != -1:
        json_response = cleaned_response_text[start_index + 6:end_index].strip()
    else:
        json_response = "{}"  # Return empty JSON if delimiters are not found

    # Prompt the user to continue or not
    if enablePause == True:
        user_input = input("Do you want to continue? (Y/N): ")
        if user_input.strip().upper() != 'Y':
            print("Program execution stopped by user.")
            sys.exit(0)  # Exit the program if the user types 'N'
    
    # Return the parsed JSON response
    return json_response

def fetch_webpage(url, webRequestHeader):
    """
    Fetches a webpage using requests and handles potential errors.
    
    Args:
        url (str): The URL of the webpage to fetch.
        webRequestHeader (dict): The headers to use for the web request.
    
    Returns:
        str: The HTML content of the fetched webpage, or None if an error occurred.
    """
    try:
        response = requests.get(url, headers=webRequestHeader, timeout=10)  # Add a timeout for safety
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None

def extract_text(html_content):
    """
    Extracts text content from HTML using BeautifulSoup.
    
    Args:
        html_content (str): The HTML content of the webpage.
    
    Returns:
        str: The extracted text content.
    """
    if not html_content:
        return ""

    soup = BeautifulSoup(html_content, "html.parser")

    # Remove script and style elements
    for script in soup(["script", "style"]):
        script.extract()

    text = soup.get_text(separator='\n')  # Use newline as separator for better readability
    lines = (line.strip() for line in text.splitlines())  # Remove empty lines and leading/trailing whitespace
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))  # Remove extra spaces
    text = '\n'.join(chunk for chunk in chunks if chunk)  # Rejoin with newlines and filter out empty chunks.
    return text

def pause_with_countdown(seconds):
    """
    Pauses execution for a specified number of seconds with a countdown display.
    
    Args:
        seconds (int): The number of seconds to pause.
    """
    for remaining in range(seconds, 0, -1):
        print(f"Waiting {remaining} seconds...", end="\r")
        time.sleep(1)
    print(" " * 30, end="\r")  # Clear the line after countdown

def clean_json_data(data):
    """
    Cleans the data to ensure it is JSON-compatible by removing invalid characters.
    
    Args:
        data (str): The raw data to clean.
    
    Returns:
        str: The cleaned JSON-compatible data.
    """
    # Remove non-printable characters and control characters
    data = re.sub(r'[^\x20-\x7E]', '', data)  # Keeps only printable ASCII characters

    # Escape invalid JSON characters
    try:
        json.loads(data)  # Validate if the data is already valid JSON
    except json.JSONDecodeError:
        data = json.dumps(data)  # Escape invalid characters if not valid JSON

    return data

def process_csv(csv_filepath, timeToPause):
    """
    Reads URLs from a CSV and processes each webpage.
    
    Args:
        csv_filepath (str): The file path of the CSV file containing URLs.
        timeToPause (int): The number of seconds to pause between processing each line.
    """
    counter = 0
    results = []  # Initialize a list to collect results
    try:
        with open(csv_filepath, 'r', encoding='utf-8') as csvfile:  # Handle potential encoding issues
            reader = csv.DictReader(csvfile)  # Assumes CSV has a header row
            for row in reader:
                url = row.get("url")  # Assumes the URL column is named "url"
                make = row.get("manufacturer")
                extracted = False
                if url:
                    print(f"Processing: {url}")
                    filename = "./data/results/" + make + "_extract_" + url.replace("://", "_").replace("/", "_") + ".txt"  # Create safe filename
                    if os.path.exists(filename):
                        with open(filename, 'r', encoding='utf-8') as content:
                            extracted_text = content.read()
                            extracted = True
                    else:
                        html_content = fetch_webpage(url, webRequestHeader)                 
                    if extracted == False:
                        if html_content:
                            extracted_text = extract_text(html_content)
                            with open(filename, 'w', encoding='utf-8') as content:
                                content.write(extracted_text)
                        else:
                            print(f"Failed to fetch {url}")
                            results.append({"url": url, "error": "Failed to fetch"})
                    if extracted_text:      
                        specData = sendtoGemini(extracted_text)
                        specData = clean_json_data(specData)  # Clean the data
                        specFileName = "./data/results/" + make + "_specs_" + url.replace("://", "_").replace("/", "_") + ".json"  # Create safe json filename
                        with open(specFileName, 'w', encoding='utf-8') as outfile:
                            outfile.write(specData)
                            results.append({"url": url, "specData": specData})  # Collect the cleaned specData
                    else:
                        print(f"No extractable text found on {url}")
                        results.append({"url": url, "error": "No extractable text found"})
                else:
                    print("URL not found in row.")
                    results.append({"url": None, "error": "URL not found in row"})
                counter += 1

                # Write results to JSON file every 2 lines
                if counter % 2 == 0:
                    with open("./data/results/generated-specifications.json", 'w', encoding='utf-8') as jsonfile:
                        json.dump(results, jsonfile, ensure_ascii=False, indent=4)
                    results = []  # Reset results list

                # Pause for timeToPause seconds after processing each line
                pause_with_countdown(timeToPause)

            # Write any remaining results to JSON file
            if results:
                with open("./data/results/generated-specifications.json", 'w', encoding='utf-8') as jsonfile:
                    json.dump(results, jsonfile, ensure_ascii=False, indent=4)

    except FileNotFoundError:
        print(f"CSV file not found: {csv_filepath}")
    except csv.Error as e:
        print(f"Error reading CSV: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    csv_file = "./data/locations/urls.csv"  # Default CSV file to process

    # Accept timeToPause as a CLI argument, default to 60 seconds if not provided
    timeToPause = int(sys.argv[1]) if len(sys.argv) > 1 else 60

    process_csv(csv_file, timeToPause)