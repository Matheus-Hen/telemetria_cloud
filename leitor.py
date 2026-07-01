import cv2 as cv
import numpy as np
import matplotlib.pyplot as plt
import easyocr

reader = easyocr.Reader(['pt', 'en'])
distancia = np.array([])
frame_count = 0
fig, ax = plt.subplots()
acelerador =np.array([])
freio =np.array([])
# Open video file
cap = cv.VideoCapture("test_telemetria.mp4")
while True:
    ret,frame = cap.read()
    if not ret:
        break
 
    frame_count += 1
    if(frame_count % 15 == 0):  # Processa a cada 30 frames
        frame_rgb = cv.cvtColor(frame[610:640, 1128:1212], cv.COLOR_BGR2RGB)
        results = reader.readtext(frame_rgb)
        print(f"--- Frame {frame_count} ---")
        for (bbox, text, confidence) in results:
            if confidence > 0.5:  # Filtra por confiança mínima de 50%
                frameHSV = cv.cvtColor(frame, cv.COLOR_BGR2HSV)
                verde_inferior = np.array([35, 40, 40])
                verde_superior = np.array([85, 255, 255])
                rosa_inferior = np.array([140, 100, 100])
                rosa_superior = np.array([168, 255, 255])
                mask_acel = cv.inRange(frameHSV[585:690, 1053:1095], verde_inferior, verde_superior)
                mask_freio = cv.inRange(frameHSV[575:677, 1053:1095], rosa_inferior, rosa_superior)
                acelerador = np.append(acelerador, [cv.countNonZero(mask_acel)])
                freio = np.append(freio, [cv.countNonZero(mask_freio)])
                distancia = np.append(distancia, [(int(text)/3.6)*(0.033*15)])
                print(f"Texto: {text} | Confiança: {confidence:.2f}")
maximum_acel = np.max(acelerador)
for i, acelerar in enumerate(acelerador):
    acelerador[i] = (acelerar/maximum_acel)*100
ax.plot(distancia, acelerador, '-', color='green')
maximum_freio = np.max(freio)
for i, freiar in enumerate(freio):
    freio[i] = (freiar/maximum_freio)*100
ax.plot(distancia, freio, '-', color='red')
ax.set(title='Telemetria', xlabel='Distância (m)', ylabel='% aceleração/freio') 
plt.show()
cap.release()
