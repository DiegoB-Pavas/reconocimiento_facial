import cv2 as cv
import os
import imutils

# Ruta base del script actual
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)

modelo='FotosBuitrago'
ruta1 = os.path.join(BASE_DIR, 'Data')
rutacompleta = os.path.join(ruta1, modelo)
if not os.path.exists(rutacompleta):
    os.makedirs(rutacompleta)

camara=cv.VideoCapture(0)
if not camara.isOpened():
    print("ERROR: No se pudo abrir la camara. Verifica que tu webcam este conectada.")
    exit(1)

cascadePath = os.path.join(PROJECT_DIR, 'entrenamientos opencv ruidos', 'opencv-master', 'data', 'haarcascades', 'haarcascade_frontalface_default.xml')
ruidos=cv.CascadeClassifier(cascadePath)
if ruidos.empty():
    print("ERROR: No se pudo cargar el clasificador Haar en:", cascadePath)
    exit(1)

print("Capturando rostros... Presiona 'S' para salir antes de las 350 fotos.")
id=0
while True:
    respuesta,captura=camara.read()
    if respuesta==False:break
    captura=imutils.resize(captura,width=640)

    grises=cv.cvtColor(captura, cv.COLOR_BGR2GRAY)
    idcaptura=captura.copy()

    cara=ruidos.detectMultiScale(grises,1.3,5)

    for(x,y,e1,e2) in cara:
        cv.rectangle(captura, (x,y), (x+e1,y+e2), (0,255,0),2)
        rostrocapturado=idcaptura[y:y+e2,x:x+e1]
        rostrocapturado=cv.resize(rostrocapturado, (160,160),interpolation=cv.INTER_CUBIC)
        cv.imwrite(rutacompleta+'/imagen_{}.jpg'.format(id), rostrocapturado)
        id=id+1
    
    cv.imshow("Resultado rostro", captura)

    # waitKey es NECESARIO para que OpenCV procese eventos de ventana
    if cv.waitKey(1) == ord('s') or id >= 350:
        break
camara.release()
cv.destroyAllWindows()