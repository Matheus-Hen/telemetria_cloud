import cv2 as cv
import numpy as np
import matplotlib.pyplot as plt
import easyocr

reader = easyocr.Reader(['pt', 'en'])
distancia_total = np.array([])
distancia = 0
velocidade = 0
frame_count = 0
fig, ax = plt.subplots(figsize=(20, 6))
acelerador =np.array([])
freio =np.array([])
# Open video file
cap = cv.VideoCapture("test_telemetria.mp4")
while True:
    ret,frame = cap.read()
    if not ret:
        break
    frameHSV = cv.cvtColor(frame, cv.COLOR_BGR2HSV)
    verde_inferior = np.array([35, 40, 40])
    verde_superior = np.array([85, 255, 255])
    rosa_inferior = np.array([140, 100, 100])
    rosa_superior = np.array([168, 255, 255])
    mask_acel = cv.inRange(frameHSV[585:690, 1053:1095], verde_inferior, verde_superior)
    mask_freio = cv.inRange(frameHSV[575:677, 1053:1095], rosa_inferior, rosa_superior)
    acelerador = np.append(acelerador, [cv.countNonZero(mask_acel)])
    freio = np.append(freio, [cv.countNonZero(mask_freio)])
    frame_rgb = cv.cvtColor(frame[610:640, 1128:1212], cv.COLOR_BGR2RGB)
    results = reader.readtext(frame_rgb)
    for (bbox, text, confidence) in results:
        if confidence > 0.5 and text.isdigit():  # Filtra por confiança mínima de 50% e texto numérico
            velocidade = int(text)
    distancia = distancia + (velocidade/3.6)*0.033
    distancia_total = np.append(distancia_total, [distancia])
maximum_acel = np.max(acelerador)
for i, acelerar in enumerate(acelerador):
    acelerador[i] = (acelerar/maximum_acel)*100
ax.plot(distancia_total, acelerador, '-', color='green')
maximum_freio = np.max(freio)
for i, freiar in enumerate(freio):
    freio[i] = (freiar/maximum_freio)*100
ax.plot(distancia_total, freio, '-', color='red')
plt.style.use('dark_background')
ax.fill_between(distancia_total, acelerador, alpha=0.3, color='green')
ax.fill_between(distancia_total, freio, alpha=0.3, color='red')
ax.grid(alpha=0.2)
ax.set(title='Telemetria', xlabel='Distância (m)', ylabel='% aceleração/freio') 
plt.show()
cap.release()
