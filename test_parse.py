import json

data = """[{"id":1,"name":"repo1"}][{"id":2,"name":"repo2"}]"""

def decode_concatenated_json(raw_data):
    decoder = json.JSONDecoder()
    pos = 0
    results = []
    while pos < len(raw_data):
        # Skip whitespace
        while pos < len(raw_data) and raw_data[pos].isspace():
            pos += 1
        if pos == len(raw_data):
            break
        obj, end = decoder.raw_decode(raw_data, pos)
        results.append(obj)
        pos = end
    return results

print(decode_concatenated_json(data))
