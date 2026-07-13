import tools.gemini_client as client



image_path = "../docs/test.jpg"

#print(client.ask_llm("Hello, how are you?","gemini-2.5-flash"))
prompt=" décirs ce que tu vois dans cette image en francais"
print(client.ask_vision(image_path,prompt))