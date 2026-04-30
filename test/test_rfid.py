# test_rfid.py
from mfrc522 import SimpleMFRC522

reader = SimpleMFRC522()

print("카드 갖다 대봐")
id, text = reader.read()
print(f"태그 ID: {id}")