# import the necessary packages
import argparse
import cv2
from picamera import PiCamera
from picamera.array import PiRGBArray
from time import sleep
import numpy as np
import time
import multiprocessing


# Variables
last_time = int(round(time.time()*1000))
status = "No Targets"

# Inter-process queues
frame_queue = Queue(maxsize=1)
blur_queue = Queue(maxsize=1)
edge_queue = Queue(maxsize=1)
image_queue = Queue(maxsize=4)
final_image_queue = Queue(maxsize=4)


def grayAndBlur(): 
    # blue, green, red = cv2.split(frame)
    # Pull in the next frame, copy it, and release the lock so the next frame can be loaded
    f = frame_queue.get(block=True, timeout=None)
    image_queue.put(f, block=True, timeout=None)

    # Cast the frame to grayscale
    g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)

    # Gaussian blur the frame
    blur = cv2.GaussianBlur(g, (7, 7), 0)
    blur_queue.put(blur, block=True, timeout=None)

def edgeDetect(): 

    b = blur_queue.get(block=True, timeout=None)

    edge = cv2.Canny(b, 50, 150)
    edge_queue.put(edge, block=True, timeout=None)

def identifyTargets():

    edge = edge_queue.get(block=True, timeout=None)
    
    # find contours in the edge map
    (_, cnts, _) = cv2.findContours(edge.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    image = image_queue.get(block=True, timeout=None)

    # loop over the contours
    for c in cnts:
        # approximate the contour
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.01 * peri, True)

        # ensure that the approximated contour is "roughly" rectangular
        if len(approx) >= 4 and len(approx) <= 7:
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
            keepSolidity = solidity > 0.9
            # keepSolidity = True
            keepAspectRatio = aspectRatio >= 0.8 and aspectRatio <= 1.2

            # ensure that the contour passes all our tests
            if keepDims and keepSolidity and keepAspectRatio:
                # draw an outline around the target and update the status
                # text
                cv2.drawContours(image, [approx], -1, (255, 0, 0), 4)
                status = "Target(s) Acquired"

                try:
                    # compute the center of the contour region and draw the
                    # crosshairs
                    M = cv2.moments(approx)
                    (cX, cY) = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))
                    (startX, endX) = (int(cX - (w * 0.15)), int(cX + (w * 0.15)))
                    (startY, endY) = (int(cY - (h * 0.15)), int(cY + (h * 0.15)))
                    cv2.line(image, (startX, cY), (endX, cY), (0, 0, 255), 3)
                    cv2.line(image, (cX, startY), (cX, endY), (0, 0, 255), 3)
                    final_image_queue.put(image, block=True, timeout=None)
                except Exception:
                    print "Divide by zero"

def main():

    # Set up the PiCamera
    camera = PiCamera()
    camera.resolution = (1280, 720)
    camera.framerate = 30
    rawCapture = PiRGBArray(camera, size=camera.resolution)

    # allow the camera to warmup
    sleep(0.1)

    # Start the image processing processes
    Process(target=grayAndBlur).start()
    Process(target=edgeDetect).start()
    Process(target=identifyTargets).start()

    # capture frames from the camera
    for frame in camera.capture_continuous(rawCapture, format="bgr", use_video_port=True):
        # grab the raw NumPy array representing the image, then initialize the timestamp
        # and occupied/unoccupied text

        # Add the next image to process. If it blocks and times out, try to put the next frame
        try:
            frame_queue.put(frame.array, block=True, timeout=1)
        except Exception:
            continue
        
        # Get the final image to be displayed
        final_image = final_image_queue.get(block=True, timeout=None)

        # draw the status text on the frame
        cv2.putText(final_image, status, (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        # show the frame and record if a key is pressed
        cv2.imshow("Frame", final_image)
        key = cv2.waitKey(1) & 0xFF

        # Print the time between frames
        current_time = int(round(time.time()*1000))
        print current_time - last_time
        last_time = current_time

        # if the 'q' key is pressed, stop the loop
        if key == ord("q"):
            break

        # clear the stream in preparation for the next frame
        rawCapture.truncate(0)

    # cleanup the camera and close any open windows
    camera.release()
    cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
