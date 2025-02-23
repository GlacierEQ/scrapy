from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from PIL import Image
import os
import requests
from io import BytesIO
from datetime import datetime
from config import Config

class ImageGenerator:
    def __init__(self):
        self.api_key = Config.STABILITY_API_KEY
        self.api_host = 'https://api.stability.ai'
        self.output_dir = Config.IMAGE_OUTPUT_DIR

    def generate_from_text(self, text, style=None, size=None):
        """
        Generate an image based on text description using Stability AI API
        """
        if not Config.ENABLE_IMAGE_GENERATION:
            return None

        if not self.api_key:
            print("Warning: No Stability AI API key provided. Skipping image generation.")
            return None

        try:
            # Prepare the prompt
            style = style or Config.IMAGE_STYLE
            prompt = f"{text} {style}"
            
            # Set image size
            size = size or Config.IMAGE_SIZE
            
            # API endpoint
            engine_id = Config.IMAGE_MODEL
            url = f"{self.api_host}/v1/generation/{engine_id}/text-to-image"

            # Request headers
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }

            # Request payload
            payload = {
                "text_prompts": [{"text": prompt}],
                "cfg_scale": 7,
                "height": size[1],
                "width": size[0],
                "samples": 1,
                "steps": 30,
            }

            # Make the API request
            response = requests.post(url, headers=headers, json=payload)
            
            if response.status_code != 200:
                raise Exception(f"Non-200 response: {response.text}")

            data = response.json()
            
            # Process and save the image
            for i, image in enumerate(data["artifacts"]):
                image_data = BytesIO(image["base64"])
                img = Image.open(image_data)
                
                # Generate filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"generated_{timestamp}_{i}.png"
                filepath = os.path.join(self.output_dir, filename)
                
                # Save the image
                img.save(filepath)
                return filepath

        except Exception as e:
            print(f"Error generating image: {str(e)}")
            return None

if __name__ == "__main__":
    # Test the image generator
    generator = ImageGenerator()
    test_text = "A modern professional website with clean design"
    result = generator.generate_from_text(test_text)
    if result:
        print(f"Generated image saved to: {result}")
    else:
        print("Image generation failed")
