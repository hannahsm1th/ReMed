#!/usr/bin/python3
"""
This program controlls the Raspberry Pi parts of the ReMed system.
"""

import schedule
import time
import serial
import cv2
import os
import sys, getopt
import signal
from edge_impulse_linux.image import ImageImpulseRunner
import requests

sys.argv.append("/home/pi/modelfile.eim") #adding the machine learning model file as an argument
sys.argv.append(0) #adding the camera port as an argument
runner = None
show_camera = False

def medication():
    """
    This method communicates with the Arduino and handles the responses
    based on various sensor data collected from the load cell and the
    USB webcam.
    """
    
    #opening the connection to the Arduino
    ser = serial.Serial('/dev/ttyACM0', 9600, timeout=5)
    ser.flush()
    
    while True:
        #read from the Arduino
        number = ser.read()
        if number != b'':
            
            # if RPi receives a hello byte code from the Arduino, send command to begin the reminder alerts
            if int.from_bytes(number, byteorder='big') == 18:
                ser.write(str(1).encode('utf-8'))
                
            # if RPi receives the code that the cup has been lifted, run the image recognition methods
            if int.from_bytes(number, byteorder='big') == 28:
                # check if cup is empty
                scores_array = []
                main(sys.argv[1:], scores_array)
                # adds together the images and collates the score to determine if the cup is empty or not
                score = 0
                for image_score in range(0, len(scores_array), 2):
                    score += scores_array[image_score]
                    print(scores_array[image_score])
                score = score / 10
                print(score)
                if score < 0.7:
                    #if not empty, send that message to the carer and alert user with LCD screen
                    ser.write(str(2).encode('utf-8'))
                    requests.post('https://maker.ifttt.com/trigger/carer_notify/with/key/cic0DcbB3hVCDHNB8Td3V', params={"value1":"Not all medication was taken."})
                elif score >= 0.7:
                    #if empty, send that message to the carer and send confirmation message to the LCD screen
                    ser.write(str(3).encode('utf-8'))
                    requests.post('https://maker.ifttt.com/trigger/carer_notify/with/key/cic0DcbB3hVCDHNB8Td3V', params={"value1":"Medication was taken."})
                
            # if RPi receives the code that indicates the alert system timed out, send that message to the carer
            if int.from_bytes(number, byteorder='big') == 38:
                requests.post('https://maker.ifttt.com/trigger/carer_notify/with/key/cic0DcbB3hVCDHNB8Td3V', params={"value1":"Medication not taken. The ReMed wasn't used today."})

def now():
    return round(time.time() * 1000)

def get_webcams():
    port_ids = []
    for port in range(5):
        #print("Looking for a camera in port %s:" %port)
        camera = cv2.VideoCapture(port)
        if camera.isOpened():
            ret = camera.read()[0]
            if ret:
                backendName =camera.getBackendName()
                w = camera.get(3)
                h = camera.get(4)
                #print("Camera %s (%s x %s) found in port %s " %(backendName,h,w, port))
                port_ids.append(port)
            camera.release()
    return port_ids

def sigint_handler(sig, frame):
    print('Interrupted')
    if (runner):
        runner.stop()
    sys.exit(0)

signal.signal(signal.SIGINT, sigint_handler)

def help():
    print('python classify.py <path_to_model.eim> <Camera port ID, only required when more than 1 camera is present>')

def main(argv, images_array):
    """
    This is the main code for the machine learning model used to identify if the cup is empty or not.
    It is from the examples in the Edge Impulse documentation on Python SDK.
    """
    try:
        opts, args = getopt.getopt(argv, "h", ["--help"])
    except getopt.GetoptError:
        help()
        sys.exit(2)

    for opt, arg in opts:
        if opt in ('-h', '--help'):
            help()
            sys.exit()

    if len(args) == 0:
        help()
        sys.exit(2)

    model = args[0]

    dir_path = os.path.dirname(os.path.realpath(__file__))
    modelfile = os.path.join(dir_path, model)

    print('MODEL: ' + modelfile)

    with ImageImpulseRunner(modelfile) as runner:
        try:
            model_info = runner.init()
            print('Loaded runner for "' + model_info['project']['owner'] + ' / ' + model_info['project']['name'] + '"')
            labels = model_info['model_parameters']['labels']
            if len(args)>= 2:
                videoCaptureDeviceId = int(args[1])
            else:
                port_ids = get_webcams()
                if len(port_ids) == 0:
                    raise Exception('Cannot find any webcams')
                if len(args)<= 1 and len(port_ids)> 1:
                    raise Exception("Multiple cameras found. Add the camera port ID as a second argument to use to this script")
                videoCaptureDeviceId = int(port_ids[0])

            camera = cv2.VideoCapture(videoCaptureDeviceId)
            ret = camera.read()[0]
            if ret:
                backendName = camera.getBackendName()
                w = camera.get(3)
                h = camera.get(4)
                print("Camera %s (%s x %s) in port %s selected." %(backendName,h,w, videoCaptureDeviceId))
                camera.release()
            else:
                raise Exception("Couldn't initialize selected camera.")

            next_frame = 0 # limit to ~10 fps here
            
            loop_times = 0

            for res, img in runner.classifier(videoCaptureDeviceId):
                if loop_times == 10: #leaves the loop after collecting 10 images
                    break;
                if (next_frame > now()):
                    time.sleep((next_frame - now()) / 1000)

                # print('classification runner response', res)

                if "classification" in res["result"].keys():
                    #print('Result (%d ms.) ' % (res['timing']['dsp'] + res['timing']['classification']), end='')
                    for label in labels:
                        score = res['result']['classification'][label]
                        images_array.append(score)
                        #print('%s: %.2f\t' % (label, score), end='')
                    #print('', flush=True)

                    if (show_camera):
                        cv2.imshow('edgeimpulse', img)
                        if cv2.waitKey(1) == ord('q'):
                            break

                elif "bounding_boxes" in res["result"].keys():
                    print('Found %d bounding boxes (%d ms.)' % (len(res["result"]["bounding_boxes"]), res['timing']['dsp'] + res['timing']['classification']))
                    for bb in res["result"]["bounding_boxes"]:
                        print('\t%s (%.2f): x=%d y=%d w=%d h=%d' % (bb['label'], bb['value'], bb['x'], bb['y'], bb['width'], bb['height']))

                next_frame = now() + 100
                
                loop_times += 1
        finally:
            if (runner):
                runner.stop()

schedule.every().day.at("20:56").do(medication)

while True:
    #scheduler checks for when to run Remed every second
    schedule.run_pending()
    time.sleep(1)