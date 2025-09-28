from dotenv import load_dotenv
import google.generativeai as genai
import os

# Load environment variables from .env file
load_dotenv()

GEMINI_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_KEY:
    print("❌ GEMINI_API_KEY not found!")
    print("Please set GEMINI_API_KEY environment variable")
else:
    print("✅ API Key found!")
    genai.configure(api_key=GEMINI_KEY)
    
    try:
        models = genai.list_models()
        for model in models:
            print(model.name)
    except Exception as e:
        print(f"❌ Error: {e}")