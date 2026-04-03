import json

text = """{
  "keywords": [
    "home decor ideas",
    "interior decor",
    "decorating tips"
  ]
}"""

parsed_result = json.loads(text)
keywords_list = []
if isinstance(parsed_result, dict):
    if "keywords" in parsed_result:
        data = parsed_result["keywords"]
        if isinstance(data, list):
            keywords_list = data
        elif isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, list):
                    keywords_list.extend(v)
    else:
        for k, v in parsed_result.items():
            if isinstance(v, list):
                keywords_list.extend(v)

clean_str = ", ".join(str(w).strip() for w in keywords_list if str(w).strip())
print("RESULT:", clean_str)
