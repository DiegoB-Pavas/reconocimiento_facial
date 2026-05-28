import cv2


def check_liveness(face_gray, face_bgr=None, det_score=None):
    lap_var = cv2.Laplacian(face_gray, cv2.CV_64F).var()
    return lap_var > 8, round(lap_var, 1)
