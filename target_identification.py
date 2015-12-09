#!/usr/bin/python
# import the necessary packages
import argparse
import cv2
from picamera import PiCamera
from picamera.array import PiRGBArray
from time import sleep
import numpy as np
import time
from multiprocessing import Queue, Process
import sys

# Inter-process queues
original_queue = Queue(maxsize=3)
final_queue = Queue(maxsize=3)
time_queue = Queue(maxsize=3)

# Constants
RESOLUTION = 480

def identifySquare(pid):
    while True:
        image = original_queue.get(block=True, timeout=None)
        # print '%s got image: %s' % (str(pid), str(int(round(time.time()*1000)) - start_time))

        # blue, green, red = cv2.split(frame)
        # Cast the image to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Gaussian blur the image
        blur = cv2.GaussianBlur(gray, (7, 7), 0)
            
        # Detect the edges
        edge = cv2.Canny(blur, 50, 150)

        # find contours in the edge map
        # edge.copy() -> edge
        (_, cnts, _) = cv2.findContours(edge, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # loop over the contours
        for c in cnts:
            # approximate the contour
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.01 * peri, True)

            # ensure that the approximated contour is "roughly" rectangular
            if len(approx) >= 4 and len(approx) <= 6:
                # compute the bounding box of the approximated contour and
                # use the bounding box to compute the aspect ratio
                (x, y, w, h) = cv2.boundingRect(approx)
                aspectRatio = w / float(h)

                # compute the solidity of the original contour
                area = cv2.contourArea(c)
                hullArea = cv2.contourArea(cv2.convexHull(c))
                solidity = area / float(hullArea)

                # compute whether or not the width and height, solidity, and
                # aspect ratio of the contour falls within appropriate bounds
                keepDims = w > 10 and h > 10
                keepSolidity = solidity > 0.8
                keepAspectRatio= aspectRatio >= 0.8 and aspectRatio <= 1.2

                # ensure that the contour passes all our tests
                if keepDims and keepSolidity and keepAspectRatio:
                    # draw an outline around the target and update the status
                    # text
                    cv2.drawContours(image, [approx], -1, (255, 0, 0), 4)

                    try:
                        # compute the center of the contour region and draw the
                        # crosshairs
                        M = cv2.moments(approx)
                        (cX, cY) = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))
                        (startX, endX) = (int(cX - (w * 0.15)), int(cX + (w * 0.15)))
                        (startY, endY) = (int(cY - (h * 0.15)), int(cY + (h * 0.15)))
                        cv2.line(image, (startX, cY), (endX, cY), (0, 0, 255), 3)
                        cv2.line(image, (cX, startY), (cX, endY), (0, 0, 255), 3)
                    except Exception:
                        print "Divide by zero"

        final_queue.put(image, block=True, timeout=None) 

def putImage():
    global RESOLUTION

    # Set up the PiCamera
    camera = PiCamera()
    camera.framerate = 30

    if RESOLUTION == 1080:
        camera.resolution = (1920, 1080)
        rawCapture = PiRGBArray(camera, size=(1920, 1080))
    elif RESOLUTION == 720:
        camera.resolution = (1280, 720)
        rawCapture = PiRGBArray(camera, size=(1280, 720))
    elif RESOLUTION == 480:
        camera.resolution = (640, 480)
        rawCapture = PiRGBArray(camera, size=(640, 480))
    else:
        print 'Wrong Resolution'
        exit()

    # allow the camera to warmup
    sleep(0.1)

    # capture frames from the camera
    for frame in camera.capture_continuous(rawCapture, format="bgr", use_video_port=True):
        time_queue.put(int(time.time() * 1000))
        frame = frame.array
        #frame = frame.array[:, 280:1000] # Crop the image to 720x720 p

        # Add the next image to process. If it blocks and times out, continue without adding a frame
        original_queue.put(frame, block=False)
        # print 'put image: %s' % (str(int(round(time.time()*1000)) - start_time))

        # clear the stream in preparation for the next frame
        rawCapture.truncate(0)

    # cleanup the camera and close any open windows
    camera.release()
    cv2.destroyAllWindows()
    exit()


def displayImage():
    last_time = 0
    while True:
        # Get the final image to be displayed, if there is none, continue the loop
        final_image = final_queue.get(block=True, timeout=None)
        # draw the status text on the frame
        # cv2.putText(final_image, status, (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        # show the frame and record if a key is pressed
        cv2.imshow("Frame", final_image)
        key = cv2.waitKey(1) & 0xFF # DONT DELETE NEED TO SHOW IMAGE
        start_time = time_queue.get()
        #print "Latency: ", int(time.time() * 1000) - start_time

        # Print the time between frames
        current_time = int(round(time.time()*1000))
        # print current_time - last_time
        last_time = current_time
        sys.stdout.write(final_image.tostring())


def main():
    global start_time

    start_time = int(round(time.time()*1000))

    # Start all the processes
    P1 = Process(target=identifySquare, args=(1,))
    P2 = Process(target=identifySquare, args=(2,))
    P3 = Process(target=identifySquare, args=(3,))
    disp = Process(target=displayImage)
    put = Process(target=putImage)

    P1.start()
    P2.start()
    P3.start()
    disp.start()
    put.start()

    put.join() 


if __name__ == '__main__':
    main()
