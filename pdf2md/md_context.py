import json
import os

class MdContext:
    def __init__(self, key_file,config_file):
        self.key_file = key_file
        self.config_file = config_file
        self.load_config()
        self.load_api_key()

    def load_config(self):
        with open(self.config_file, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
            if not self.config:
                self.config = {}

    
    def load_api_key(self):
        if os.path.exists(self.key_file):
            with open(self.key_file, 'r', encoding='utf-8') as f:
                self.api_key = json.load(f)
                if not self.api_key:
                    self.api_key = {}
        else:
            self.api_key = {'glm_api_key':''}
            self.save_api_key()

    def save_config(self):
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=4)

    def save_api_key(self):
        with open(self.key_file, 'w', encoding='utf-8') as f:
            json.dump(self.api_key, f, ensure_ascii=False, indent=4)

