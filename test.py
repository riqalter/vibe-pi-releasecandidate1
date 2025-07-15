import uuid

def generate_uuid():
    return str(uuid.uuid4())

# test
print(generate_uuid())
