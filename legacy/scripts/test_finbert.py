import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")
tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")

print("Model label mapping config:", model.config.id2label)

text = "Apple stock surges 10% after blowout earnings"
inputs = tokenizer(text, return_tensors="pt")
with torch.no_grad():
    outputs = model(**inputs)
    probs = torch.softmax(outputs.logits, dim=-1)
    
print("Text:", text)
print("Logits:", outputs.logits)
print("Probs:", probs)
