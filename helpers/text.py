def split_text(text, chunk_size=1000, chunk_overlap=200):
    docs = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        docs.append(text[start:end])
        start += chunk_size - chunk_overlap
    return docs
