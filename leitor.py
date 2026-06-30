import cv2 as cv
import numpy as np
import matplotlib.pyplot as plt
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
    frame = cv.cvtColor(frame, cv.COLOR_BGR2HSV)
    verde_inferior = np.array([35, 40, 40])
    verde_superior = np.array([85, 255, 255])
    rosa_inferior = np.array([140, 100, 100])
    rosa_superior = np.array([168, 255, 255])
    mask_acel = cv.inRange(frame[585:690, 1053:1095], verde_inferior, verde_superior)
    mask_freio = cv.inRange(frame[575:677, 1053:1095], rosa_inferior, rosa_superior)
    acelerador = np.append(acelerador, [cv.countNonZero(mask_acel)])
    freio = np.append(freio, [cv.countNonZero(mask_freio)])
maximum_acel = np.max(acelerador)
km = np.array([])
for i, acelerar in enumerate(acelerador):
    acelerador[i] = (acelerar/maximum_acel)*100
    km = np.append(km, [(acelerar/13600)*100])
ax.plot(km, acelerador, '-', color='green')
maximum_freio = np.max(freio)
km2 = np.array([])
for i, freiar in enumerate(freio):
    freio[i] = (freiar/maximum_freio)*100
    km2 = np.append(km2, [(freiar/13600)*100])
tempo=np.arange(len(freio)) / 13660
ax.plot(km2, freio, '-', color='red')
ax.set(title='Contagem de pixels vermelhos por segundo', xlabel='Tempo (s)', ylabel='% aceleração/freio') 
plt.show()
cap.release()
