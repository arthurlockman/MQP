#!/usr/local/bin/python

from dronekit import connect, VehicleMode, LocationGlobalRelative
import time
import argparse
import sys
import pickle
from multiprocessing import Queue, Process, Value
import socket
import os
import math

identified = None
vehicle = None 
server_socket = None

# Queue of data containing the center location of a target
image_data = Queue(maxsize=1)


def initialize():
    global vehicle

    print "Basic pre-arm checks"

    # Don't let the user try to arm until autopilot is ready
    while not vehicle.is_armable:
        print "Waiting for vehicle to initialize..."
        time.sleep(1)


def arm(): 
    global vehicle

    print "Arming motors"
    # Copter should arm in GUIDED mode
    vehicle.mode = VehicleMode("GUIDED")
    vehicle.armed = True    

    while not vehicle.armed:      
        print " Waiting for arming..."
        time.sleep(1)


def takeoff(atargetaltitude=10):
    global vehicle

    vehicle.mode = VehicleMode("GUIDED")

    print "Taking off!"
    vehicle.simple_takeoff(atargetaltitude)  # Take off to target altitude

    # Wait until the vehicle reaches a safe height before processing the goto (otherwise the command 
    #  after Vehicle.simple_takeoff will execute immediately).
    while True:
        print " Altitude: ", vehicle.location.global_relative_frame.alt
        # Break and return from function just below target altitude.
        if vehicle.location.global_relative_frame.alt >= atargetaltitude * 0.95:
            print "Reached target altitude"
            break
        time.sleep(1)


def setup():
    global vehicle

    # Connect to the Vehicle
    print "Connecting to the vehicle..."
    vehicle = connect('/dev/ttyAMA0', baud=57600, wait_ready=True)
    # vehicle = connect('tcp:localhost:5760', baud=57600, wait_ready=True)

    # Initialize the vehicle
    initialize()

    # Arm the vehicle
    arm()

    print "Set default/target airspeed to 3"
    vehicle.airspeed = 3


def return_to_launch():
    global vehicle

    print "Returning to Launch"
    vehicle.mode = VehicleMode("RTL")
    while vehicle.location.global_relative_frame.alt >= 0:
        time.sleep(1)


def end_flight():
    global vehicle

    # Close vehicle object before exiting script
    print "Close vehicle object"
    vehicle.close()


def go_to_coordinate(latitude, longitude, altitude=10, speed=5):
    global vehicle

    vehicle.mode = VehicleMode("GUIDED")
    print "Navigating to point"
    point = LocationGlobalRelative(latitude, longitude, altitude)
    vehicle.simple_goto(point, groundspeed=speed)

    # sleep so we can see the change in map
    time.sleep(30)


def getImageData():
    global image_data, identified

    while True:
        client_socket, address = server_socket.accept()
        print "Connection from ", address
        while True:
            data_string = client_socket.recv(512)
            try:
                image_data.get(block=False)
            except:
                pass
            data = pickle.loads(data_string)
            image_data.put(data)

            with identified.value.get_lock():
                if data != None:
                    identified.value = 1
                else:
                    identified.value = 0
            # print "RECIEVED:" , pickle.loads(data_string)

def printImageData():

    while True:
        try:
            data = image_data.get()
            print data
        except:
            pass


def circle_POI():
    global vehicle
    
    # The circle radius in cm. Must be incremented by 100 cm.
    # The tangential speed is 50 cm/s
    speed = 50

    radius = (int)200
    rate = (int)math.degrees(2*math.pi*rad / speed)

    vehicle.parameters["CIRCLE_RADIUS"] = radius
    vehicle.parameters["CIRCLE_RATE"] = rate

    vehicle.mode = VehicleMode("CIRCLE")


def main():
    global server_socket, vehicle, identified

    identified = Value('i', 0)

    setup()

    # server_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    # server_socket.bind(("",5001))
    # server_socket.listen(5)

    # ImageProcess = Process(target=getImageData)
    # ImageProcess.start()

    # Uncomment these to print the recieved data
    # CAUTION: the data is consumed and will not be usable by another function
    # ImagePrint = Process(target=printImageData)
    # ImagePrint.start()

    # os.system('python ../PiCamera/target_identification.py')
    # os.system('python ../PiCamera/client_test.py')

    ignore_target = False

    while True:

        # If the target has been seen, stop all motion and hold position
        # Possible to ignore the target if flag set
        # if ignore_target == False:
        #     with identified.value.get_lock():
        #         if identified.value == 1:
        #             vehicle.mode = VehicleMode("LOITER")

        print "\n---------------------------------------------------------------------------\n"
        print "Options: takeoff, pilot, land, end, stop, goto, circle, ignore, obey"

        command = raw_input("What shall I do next?\n")

        if command == "takeoff":
            takeoff(5)

        elif command == "pilot":
            vehicle.mode = VehicleMode("SIMPLE")

        elif command == "land":
            ignore_target = True
            return_to_launch()

        elif command == "end":
            end_flight()
            ImageProcess.terminate()
            exit()

        elif command == "stop":
            vehicle.mode = VehicleMode("LOITER")

        elif command == "goto":
            latitude = float(raw_input("Latitude: "))
            longitude = float(raw_input("Longitude: "))
            altitude = float(raw_input("Altitude: "))
            go_to_coordinate(latitude, longitude, int(altitude))

        elif command == "circle":
            circle_POI()

        elif command == "ignore":
            ignore_target = True

        elif command == "obey":
            ignore_target = False

        else:
            print "Not a vaild command."

if __name__ == '__main__':
    main()
