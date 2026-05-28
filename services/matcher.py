import numpy as np


class FaceMatcher:
    """Matches face embeddings against stored gallery using cosine similarity."""

    def find_best_match(self, query_embedding, user_embeddings, threshold=0.5):
        """Find the best matching user for a query embedding.

        Args:
            query_embedding: 512-dim float32 numpy array.
            user_embeddings: dict of {usr_id: list of 512-dim numpy arrays}.
            threshold: minimum cosine similarity to accept a match.

        Returns:
            (usr_id, similarity) or (None, max_similarity).
        """
        best_usr_id = None
        best_sim = -1.0

        query_norm = query_embedding / np.linalg.norm(query_embedding)

        for usr_id, embs in user_embeddings.items():
            for emb in embs:
                emb_norm = emb / np.linalg.norm(emb)
                sim = float(np.dot(query_norm, emb_norm))
                if sim > best_sim:
                    best_sim = sim
                    best_usr_id = usr_id

        if best_sim >= threshold:
            return best_usr_id, best_sim
        return None, best_sim
