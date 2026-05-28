import cv2
import numpy as np
from insightface.app import FaceAnalysis


class FaceDetector:
    """Face detection and embedding extraction using InsightFace."""

    _instance = None

    @classmethod
    def get_instance(cls, model_name='buffalo_l'):
        if cls._instance is None:
            cls._instance = cls(model_name)
        return cls._instance

    def __init__(self, model_name='buffalo_l'):
        self.app = FaceAnalysis(name=model_name, providers=['CPUExecutionProvider'])
        self.app.prepare(ctx_id=0, det_size=(640, 640))

    def detect_and_extract(self, frame_bgr):
        """Detect faces and extract embeddings from a full BGR frame.

        Returns list of dicts with keys: bbox, embedding, det_score, landmarks.
        """
        faces = self.app.get(frame_bgr)
        results = []
        for face in faces:
            bbox = face.bbox.astype(int)
            results.append({
                'bbox': [int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])],
                'embedding': face.embedding.astype(np.float32),
                'det_score': float(face.det_score),
                'landmarks': face.landmarks.astype(int).tolist() if face.landmarks is not None else None
            })
        return results

    def extract_embedding(self, face_img_bgr):
        h, w = face_img_bgr.shape[:2]
        if max(h, w) < 160:
            scale = 160.0 / max(h, w)
            face_img_bgr = cv2.resize(face_img_bgr, None, fx=scale, fy=scale,
                                      interpolation=cv2.INTER_CUBIC)
            h, w = face_img_bgr.shape[:2]
        px, py = int(w * 0.5), int(h * 0.5)
        padded = cv2.copyMakeBorder(face_img_bgr, py, py, px, px,
                                    cv2.BORDER_REPLICATE)
        faces = self.app.get(padded)
        if faces:
            return faces[0].embedding.astype(np.float32), float(faces[0].det_score)
        return None, 0.0
