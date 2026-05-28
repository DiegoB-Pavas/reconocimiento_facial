import logging
import os

import cv2
import numpy as np
import torch
from torchvision import transforms

from config import ANTISPOOF_MODEL_DIR, ANTISPOOF_REAL_THRESHOLD

logger = logging.getLogger(__name__)


class AntiSpoofing:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.model = None
        self.available = False
        self.device = torch.device('cpu')

        weights_path = os.path.join(ANTISPOOF_MODEL_DIR, 'DeePixBiS.pth')
        model_py_path = os.path.join(ANTISPOOF_MODEL_DIR, 'Model.py')

        if not os.path.exists(weights_path):
            logger.warning("DeePixBiS weights not found: %s", weights_path)
            return
        if not os.path.exists(model_py_path):
            logger.warning("DeePixBiS Model.py not found: %s", model_py_path)
            return

        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "DeePixBiS_model", model_py_path
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            self.model = mod.DeePixBiS(pretrained=False)
            self.model.load_state_dict(
                torch.load(
                    weights_path, map_location=self.device, weights_only=True
                )
            )
            self.model.eval()

            self.transform = transforms.Compose([
                transforms.ToPILImage(),
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
            ])

            self.available = True
            logger.info("DeePixBiS loaded from %s", ANTISPOOF_MODEL_DIR)
        except Exception as e:
            logger.error("Failed to load DeePixBiS model: %s", e)

    def predict(self, image_bgr, bbox):
        if not self.available or self.model is None:
            return True, 1.0

        x, y, w, h = bbox
        if w < 10 or h < 10:
            return True, 1.0

        frame_h, frame_w = image_bgr.shape[:2]
        face_ratio = (w * h) / (frame_w * frame_h)

        if face_ratio > 0.40:
            logger.info(
                "Spoof detected (face too large): %.1f%%", face_ratio * 100
            )
            return False, round(1.0 - face_ratio, 4)

        face_bgr = image_bgr[y:y + h, x:x + w]
        if face_bgr.size == 0:
            return True, 1.0

        face_gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
        lap_var = float(cv2.Laplacian(face_gray, cv2.CV_64F).var())
        if lap_var < 8:
            logger.info(
                "Spoof detected (low texture): lap_var=%.1f", lap_var
            )
            return False, round(lap_var / 100, 4)

        try:
            face_rgb = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2RGB)
            input_tensor = self.transform(face_rgb)
            input_tensor = input_tensor.unsqueeze(0)

            with torch.no_grad():
                mask, binary = self.model(input_tensor)

            score = float(torch.mean(mask).item())

            logger.info(
                "DeePixBiS: score=%.4f lap_var=%.1f", score, lap_var
            )

            if score < ANTISPOOF_REAL_THRESHOLD:
                logger.info(
                    "Spoof detected (DeePixBiS): score=%.4f", score
                )
                return False, round(score, 4)

            return True, round(score, 4)
        except Exception as e:
            logger.error("DeePixBiS inference error: %s", e)
            return True, 1.0
