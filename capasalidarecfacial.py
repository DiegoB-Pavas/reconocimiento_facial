import cv2 as cv
import os
import imutils
import json  # Para leer los nombres guardados

# Ruta base del script actual
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)

# Intentar cargar nombres desde nombres.json, de lo contrario usar os.listdir
nombres_path = os.path.join(BASE_DIR, 'nombres.json')
if os.path.exists(nombres_path):
    with open(nombres_path, 'r', encoding='utf-8') as f:
        listaData = json.load(f)
else:
    dataRuta = os.path.join(BASE_DIR, 'Data')
    listaData = os.listdir(dataRuta)

entrenamientoEigenFaceRecognizer = cv.face.EigenFaceRecognizer_create()
modelo_xml = os.path.join(BASE_DIR, 'EntrenamientoEigenFaceRecognizer.xml')

if not os.path.exists(modelo_xml):
    print(f"ERROR: No se encuentra el modelo {modelo_xml}. Primero ejecuta capaocultaentrenamiento.py")
    exit(1)

entrenamientoEigenFaceRecognizer.read(modelo_xml)

cascadePath = os.path.join(PROJECT_DIR, 'entrenamientos opencv ruidos', 'opencv-master', 'data', 'haarcascades', 'haarcascade_frontalface_default.xml')
ruidos = cv.CascadeClassifier(cascadePath)

if ruidos.empty():
    print(f"ERROR: No se pudo cargar el clasificador Haar en {cascadePath}")
    exit(1)

camara = cv.VideoCapture(0)  # 0 = webcam en vivo

while True:
    respuesta, captura = camara.read()
    if not respuesta:
        break
    
    captura = imutils.resize(captura, width=640)
    grises = cv.cvtColor(captura, cv.COLOR_BGR2GRAY)
    idcaptura = grises.copy()
    cara = ruidos.detectMultiScale(grises, 1.3, 5)

    for (x, y, e1, e2) in cara:
        rostrocapturado = idcaptura[y:y+e2, x:x+e1]
        rostrocapturado = cv.resize(rostrocapturado, (160, 160), interpolation=cv.INTER_CUBIC)
        resultado = entrenamientoEigenFaceRecognizer.predict(rostrocapturado)
        
        cv.putText(captura, '{}'.format(resultado), (x, y-5), 1, 1.3, (0, 255, 0), 1, cv.LINE_AA)
        
        # LBPH o EigenFaces confidence check
        if resultado[1] < 8000:
            nombre = listaData[resultado[0]] if resultado[0] < len(listaData) else "Desconocido"
            cv.putText(captura, '{}'.format(nombre), (x, y-20), 2, 1.1, (0, 255, 0), 1, cv.LINE_AA)
            cv.rectangle(captura, (x, y), (x+e1, y+e2), (255, 0, 0), 2)
        else:
            cv.putText(captura, "No encontrado", (x, y-20), 2, 0.7, (0, 255, 0), 1, cv.LINE_AA)
            cv.rectangle(captura, (x, y), (x+e1, y+e2), (255, 0, 0), 2)

    cv.imshow("Resultados", captura)
    if cv.waitKey(1) == ord('s'):
        break

camara.release()
cv.destroyAllWindows()
