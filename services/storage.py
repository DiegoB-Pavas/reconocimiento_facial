import numpy as np
from database import (
    save_embedding_blob as _save_blob,
    load_all_embedding_blobs as _load_all_blobs,
    delete_embedding_blobs_by_user as _delete_user,
    delete_all_embedding_blobs as _delete_all,
    count_embedding_blobs as _count
)


class EmbeddingStorage:
    """Manages storage and in-memory caching of face embeddings."""

    def __init__(self):
        self.cache = {}
        self.refresh()

    def refresh(self):
        blobs = _load_all_blobs()
        cache = {}
        for usr_id, blob in blobs:
            emb = np.frombuffer(blob, dtype=np.float32)
            if usr_id not in cache:
                cache[usr_id] = []
            cache[usr_id].append(emb)
        self.cache = cache

    def save_user_embeddings(self, usr_id, embeddings, thumbnails=None):
        _delete_user(usr_id)
        for i, emb in enumerate(embeddings):
            thumb = thumbnails[i] if thumbnails and i < len(thumbnails) else None
            _save_blob(usr_id, emb.tobytes(), thumb)
        self.refresh()

    def delete_user_embeddings(self, usr_id):
        _delete_user(usr_id)
        self.refresh()

    def delete_all(self):
        _delete_all()
        self.refresh()

    def get_all(self):
        return self.cache

    def count(self, usr_id=None):
        return _count(usr_id)
