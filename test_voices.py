from fishaudio import FishAudio
from config import FISH_API_KEY

client = FishAudio(api_key=FISH_API_KEY)
voices = client.voices.list()
print(voices)