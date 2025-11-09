from dotenv import load_dotenv
import os

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAQ_API_KEY = os.getenv("OPENAQ_API_KEY", "")
AWS_REGION = os.getenv("AWS_REGION", "us-west-2")
