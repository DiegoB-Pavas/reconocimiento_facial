import cv2 as cv
import os
import numpy as np
from time import time
import shutil  # Para eliminar carpetas
import json    # Para guardar nombres de usuarios

# Ruta base del script actual
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

dataRuta = os.path.join(BASE_DIR, 'Data')
listaData=os.listdir(dataRuta)
#print('data',listaData)
ids=[]
rostrosData=[]
id=0
tiempoInicial=time()
for fila in listaData:
    rutacompleta=dataRuta+'/'+ fila
    print('Iniciando lectura...')
    for archivo in os.listdir(rutacompleta):
       
        print('Imagenes: ',fila +'/'+archivo)
    
        ids.append(id)
        rostrosData.append(cv.imread(rutacompleta+'/'+archivo,0))  
      

    id=id+1
    tiempofinalLectura=time()
    tiempoTotalLectura=tiempofinalLectura-tiempoInicial
    print('Tiempo total lectura: ',tiempoTotalLectura)

entrenamientoEigenFaceRecognizer=cv.face.EigenFaceRecognizer_create()
print('Iniciando el entrenamiento...espere')
entrenamientoEigenFaceRecognizer.train(rostrosData,np.array(ids))
TiempofinalEntrenamiento=time()
tiempoTotalEntrenamiento=TiempofinalEntrenamiento-tiempoTotalLectura
print('Tiempo entrenamiento total: ',tiempoTotalEntrenamiento)
entrenamientoEigenFaceRecognizer.write(os.path.join(BASE_DIR, 'EntrenamientoEigenFaceRecognizer.xml'))
print('Entrenamiento concluido')

# --- Lógica de limpieza ---
# Guardar los nombres para que el reconocedor pueda usarlos sin las carpetas físicas
with open(os.path.join(BASE_DIR, 'nombres.json'), 'w', encoding='utf-8') as f:
    json.dump(listaData, f, ensure_ascii=False, indent=4)
print('Nombres guardados en nombres.json')

# Eliminar cada subcarpeta de fotos
for nombre in listaData:
    ruta_usuario = os.path.join(dataRuta, nombre)
    if os.path.isdir(ruta_usuario):
        try:
            shutil.rmtree(ruta_usuario)
            print(f'Carpeta de fotos eliminada: {nombre}')
        except Exception as e:
            print(f'Error al eliminar la carpeta de {nombre}: {e}')

print('Limpieza completada.')