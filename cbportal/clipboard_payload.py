import json

class ClipboardPayload:
    def __init__(self, content_hash, content_type, content):
        self.hash = content_hash
        self.type = content_type
        self.content = content

    def to_json(self):
        return json.dumps(self.__dict__)

    @classmethod
    def from_json(cls, json_str):
        data = json.loads(json_str)
        return cls(data['hash'], data['type'], data['content'])