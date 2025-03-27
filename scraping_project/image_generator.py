import os
import requests
import time
import random
import logging
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from config import Config

class ImageGenerator:
    """
    Generate images based on text analysis results.
    Can use a local placeholder or the Stability AI API.
    """
    
    def __init__(self):
        self.api_key = Config.STABILITY_API_KEY
        self.output_dir = Config.IMAGE_OUTPUT_DIR
        self.model = Config.IMAGE_MODEL
        self.image_size = Config.IMAGE_SIZE
        self.style = Config.IMAGE_STYLE
        os.makedirs(self.output_dir, exist_ok=True)
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def generate_from_text(self, prompt, num_images=1):
        """
        Generate an image based on text prompt.
        Falls back to a placeholder if API key not configured.
        """
        if not self.api_key:
            self.logger.warning("No Stability API key provided. Generating placeholder.")
            return self._generate_placeholder(prompt)
        
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"generated_{timestamp}.png"
            output_path = os.path.join(self.output_dir, filename)
            
            # Set API parameters based on config
            full_prompt = f"{prompt}, {self.style}"
            
            # Make API request to Stability AI
            response = self._stability_api_request(full_prompt, num_images)
            
            # Save the generated image
            with open(output_path, 'wb') as f:
                f.write(response.content)
            
            self.logger.info(f"Image generated successfully: {output_path}")
            return output_path
            
        except Exception as e:
            self.logger.error(f"Error generating image: {str(e)}")
            return self._generate_placeholder(prompt)
    
    def _stability_api_request(self, prompt, num_images=1):
        """Make request to Stability AI API"""
        url = f"https://api.stability.ai/v1/generation/{self.model}/text-to-image"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "image/png"
        }
        
        payload = {
            "text_prompts": [{"text": prompt}],
            "cfg_scale": 7,
            "height": self.image_size[1],
            "width": self.image_size[0],
            "samples": num_images,
            "steps": 50,
        }
        
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            raise Exception(f"API request failed with status {response.status_code}: {response.text}")
        
        return response
    
    def _generate_placeholder(self, text):
        """Generate a placeholder image with text"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"placeholder_{timestamp}.png"
        output_path = os.path.join(self.output_dir, filename)
        
        # Create a simple colored background with text
        width, height = self.image_size
        image = Image.new('RGB', (width, height), color=self._random_pastel_color())
        
        # Add text to the image
        draw = ImageDraw.Draw(image)
        try:
            # Try to use a system font
            font = ImageFont.truetype("arial.ttf", 24)  # Adjust path for your system
        except IOError:
            font = ImageFont.load_default()
        
        # Wrap text to fit the image
        wrapped_text = self._wrap_text(text, font, width - 40)
        draw.text((20, 20), wrapped_text, fill="black", font=font)
        
        # Add a note about the placeholder
        note = "API key not configured - placeholder image"
        draw.text((20, height - 40), note, fill="black", font=font)
        
        # Save the image
        image.save(output_path)
        self.logger.info(f"Placeholder image created: {output_path}")
        
        return output_path
    
    def _random_pastel_color(self):
        """Generate a random pastel color"""
        # Pastel colors have high values in all channels
        r = random.randint(180, 255)
        g = random.randint(180, 255)
        b = random.randint(180, 255)
        return (r, g, b)
    
    def _wrap_text(self, text, font, max_width):
        """Wrap text to fit within a given width"""
        words = text.split()
        wrapped_lines = []
        current_line = []
        
        for word in words:
            # Add the word to the current line
            test_line = ' '.join(current_line + [word])
            text_width = font.getsize(test_line)[0] if hasattr(font, 'getsize') else 0
            
            if current_line and text_width > max_width:
                # Line would be too long with this word, start a new line
                wrapped_lines.append(' '.join(current_line))
                current_line = [word]
            else:
                # Word fits, add it to the current line
                current_line.append(word)
        
        # Add the last line
        if current_line:
            wrapped_lines.append(' '.join(current_line))
            
        # Join lines with newlines
        return '\n'.join(wrapped_lines)

if __name__ == "__main__":
    # Test the image generator
    generator = ImageGenerator()
    image_path = generator.generate_from_text("A beautiful landscape with mountains and lakes")
    print(f"Test image generated at: {image_path}")
