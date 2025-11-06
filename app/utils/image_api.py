import os
import requests
from typing import Optional,List

class ImageGenerator:
    """Free image generation using multiple APIs"""
    
    def __init__(self):
        self.pexels_api_key = os.getenv("PEXELS_API_KEY")
    
    def generate_lexica(self, prompt: str) -> Optional[str]:
        """
        Generate image using Lexica.art API (free, no key needed)
        Returns image URL
        """
        try:
            # Clean and format prompt
            clean_prompt = prompt.replace(" ", "+")
            url = f"https://lexica.art/api/v1/search?q={clean_prompt}"
            
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data.get("images") and len(data["images"]) > 0:
                return data["images"][0]["src"]
            
            return None
        except Exception as e:
            print(f"Lexica API error: {e}")
            return None
    
    def generate_pexels(self, query: str) -> Optional[str]:
        """
        Generate image using Pexels API (free with API key)
        Returns image URL
        """
        if not self.pexels_api_key:
            return None
        
        try:
            headers = {"Authorization": self.pexels_api_key}
            url = f"https://api.pexels.com/v1/search?query={query}&per_page=1"
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data.get("photos") and len(data["photos"]) > 0:
                return data["photos"][0]["src"]["large"]
            
            return None
        except Exception as e:
            print(f"Pexels API error: {e}")
            return None
    
    def generate_unsplash_free(self, query: str) -> Optional[str]:
        """
        Use Unsplash Source (no API key needed)
        Returns image URL
        """
        try:
            # Unsplash Source provides random images based on query
            clean_query = query.replace(" ", ",")
            image_url = f"https://source.unsplash.com/1200x630/?{clean_query}"
            
            # Verify URL is accessible
            response = requests.head(image_url, timeout=5)
            if response.status_code == 200:
                return image_url
            
            return None
        except Exception as e:
            print(f"Unsplash Source error: {e}")
            return None
    
    def generate_image(self, prompt: str, keywords: List[str] = None) -> Optional[str]:
        """
        Try multiple free image APIs in order of preference
        Returns first successful image URL
        """
        # Combine prompt with keywords for better results
        if keywords:
            search_query = f"{prompt} {' '.join(keywords[:3])}"
        else:
            search_query = prompt
        
        # Try Lexica first (AI-generated, high quality)
        image_url = self.generate_lexica(search_query)
        if image_url:
            print(f"✅ Image generated via Lexica")
            return image_url
        
        # Try Pexels if API key available
        if self.pexels_api_key:
            image_url = self.generate_pexels(search_query)
            if image_url:
                print(f"✅ Image generated via Pexels")
                return image_url
        
        # Fallback to Unsplash Source
        image_url = self.generate_unsplash_free(search_query)
        if image_url:
            print(f"✅ Image generated via Unsplash")
            return image_url
        
        print("⚠️ All image APIs failed, using placeholder")
        return f"https://via.placeholder.com/1200x630.png?text={search_query.replace(' ', '+')}"
    def generate_alt_text(self, image_url: str, keyphrase: str, title: str) -> str:
        """
        Generate SEO-optimized alt text for images
        Alt text should include the focus keyphrase
        """
        # Keep it concise but descriptive (max 125 characters)
        alt_text = f"{keyphrase} - {title}"
        
        if len(alt_text) > 125:
            alt_text = f"{keyphrase} illustration"
        
        return alt_text[:125]