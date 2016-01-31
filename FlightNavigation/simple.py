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

# Global Variables

identified = None
user_override = None
vehicle = None 
image_socket = None
shutdown = None

# Shared queues
image_data = Queue(maxsize=1)
gps_coordinates = Queue()

def setup():
    global vehicle

    # Connect to the Vehicle
    print "Connecting to the vehicle..."
    vehicle = connect('/dev/ttyAMA0', baud=57600, wait_ready=True)

    # Uncomment this for the simulator
    # vehicle = connect('tcp:localhost:5760', baud=57600, wait_ready=True)

    # Initialize the vehicle
    while not vehicle.is_armable:
        print "Waiting for vehicle to initialize..."
        time.sleep(1)

    # Arm the vehicle
    arm()

    print "Set default/target airspeed to 3"
    vehicle.airspeed = 3


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

    # Wait until the vehicle reaches a safe height
    while True:
        print " Altitude: ", vehicle.location.global_relative_frame.alt
        # Break and return from function just below target altitude.
        if vehicle.location.global_relative_frame.alt >= atargetaltitude * 0.95:
            print "Reached target altitude"
            break
        time.sleep(1)


def return_to_launch():
    global vehicle

    print "Returning to Launch"
    vehicle.mode = VehicleMode("RTL")

    # Wait until the vehicle lands to process the next command
    while vehicle.location.global_relative_frame.alt >= 0:
        time.sleep(1)


def end_flight():
    global vehicle, shutdown

    # Disarm the vehicle
    vehicle.armed = False
    while vehicle.armed == True:      
        print " Waiting for disarming..."
        time.sleep(1)

    # Close vehicle object before exiting script
    print "Close vehicle object"
    vehicle.close()

    # Shutdown the other processes
    with shutdown.value.get_lock():
        shutdown.value = 1


def go_to_coordinate(latitude, longitude, altitude=10, speed=5):
    global vehicle

    vehicle.mode = VehicleMode("GUIDED")
    print "Navigating to point"
    point = LocationGlobalRelative(latitude, longitude, altitude)
    vehicle.simple_goto(point, groundspeed=speed)

    # sleep so we can see the change in map
    # time.sleep(30)


def circle_POI():
    global vehicle
    
    # The circle radius in cm. Must be incremented by 100 cm.
    # The tangential speed is 50 cm/s
    speed = 50

    radius = int(200)
    rate = int(math.degrees(2*math.pi*rad / speed))

    vehicle.parameters["CIRCLE_RADIUS"] = radius
    vehicle.parameters["CIRCLE_RATE"] = rate

    vehicle.mode = VehicleMode("CIRCLE")

def stop():
    global vehicle

    vehicle.mode = VehicleMode("LOITER")

def check_user_control():
    global vehicle, user_override

    value = vehicle.channels['8']

    # print value

    if value == SOMETHING:
        return True
    else:
        return False


def shell_handler(command):

    if command == "takeoff":
        # Blocking
        takeoff(5)

    elif command == "land":
        # Blocking
        return_to_launch()

    elif command == "end":
        # Kills everything
        end_flight()

    elif command == "stop":
        # Non-blocking
        stop()

    elif command == "circle":
        # Non-blocking
        circle_POI()

    elif command == "goto":
        # Non-blocking? 
        global gps_coordinates

        # Make sure there is a location to go to
        try:
            location = gps_coordinates.get(block=False)
            go_to_coordinate(location(0), location(1), altitude=10, speed=5)
        except:
            print "GPS queue empty"

    else:
        print "Not a vaild command."


def process_image_data():
    global image_data, identified, shutdown

    client_socket, address = image_socket.accept()
    print "Image socket connected from ", address

    while True:

        # image_socket is non-blocking, so an exception might be raised if there is no data in the socket
        try:
            data_string = client_socket.recv(512)

            # Clear the current data
            try:
                image_data.get(block=False)
            except:
                pass

            # Add the new data
            data = pickle.loads(data_string)
            image_data.put(data)

            # If the target has been seen, set the flag
            with identified.value.get_lock():
                if data != -1:
                    identified.value = 1
                else:
                    identified.value = 0
        except:
            pass

        # If it is time to shutdown
        with shutdown.value.get_lock():
            if shutdown.value == 1:
                break

def process_gps_data():
    global gps_coordinates, shutdown

    client_socket, address = image_socket.accept()
    print "GPS socket connected from ", address

    while True:
        # gps_socket is non-blocking, so an exception might be raised if there is no data in the socket
        try:
            data_string = client_socket.recv(512)
            data = pickle.loads(data_string)
            # Print data
            gps_coordinates.put(data)
        except:
            pass

        # If it is time to shut down
        with shutdown.value.get_lock():
            if shutdown.value == 1:
                break


def main():
    global image_socket, vehicle, identified, shutdown

    # Multi-core shared variables
    identified = Value('i', 0)
    shutdown = Value('i', 0)

    # Initialize and arm the vehicle
    setup()

    # Start the other scripts
    os.system("gnome-terminal -e 'python ../PiCamera/target_identification.py'")
    os.system("gnome-terminal -e 'python ./shell.py'")
    os.system("gnome-terminal -e 'python ../GoToHere/gotohere.py'")

    # os.system('python ../PiCamera/target_identification.py')
    # os.system('python ./shell.py')
    # os.system('python ../GoToHere/gotohere.py')

    # To open a terminal and run a command: 
    # os.system("gnome-terminal -e 'bash -c \"sudo apt-get update; exec bash\"'")

    # Socket for listening to the target_identification script
    image_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    image_socket.setblocking(0)
    image_socket.bind(("",5001))
    image_socket.listen(5)

    # Socket for listening to the GPS coordinate script
    gps_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    gps_socket.setblocking(0)
    gps_socket.bind(("",5002))
    gps_socket.listen(5)

    # Socket for listening to the user shell
    shell_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    shell_socket.setblocking(0)
    shell_socket.bind(("",5003))
    shell_socket.listen(5)

    # Image information handler
    ImageProcess = Process(target=process_image_data)
    ImageProcess.start()

    # GPS information handler
    GPSProcess = Process(target=process_gps_data)
    GPSProcess.start()

    # Connect the shell socket
    client_socket, address = shell_socket.accept()
    print "Shell socket connected from ", address

    while True:

        # Check user override switch
        if check_user_control() == True:
            vehicle.mode = VehicleMode("LOITER")

        # shell_socket is non-blocking, so an exception might be raised if there is no data in the socket
        try:
            # Recieve data from shell socket
            data_string = client_socket.recv(512)
            data = pickle.loads(data_string)

            # Act accordingly
            shell_handler(data)
        except:
            pass

        # If it is time to shut down
        with shutdown.value.get_lock():
            if shutdown.value == 1:
                break

    # Wait for the child processes to terminate
    ShellProcess.join()
    print "Shell process shut down"
    GPSProcess.join()
    print "GPS process shut down"
    ImageProcess.join()
    print "Image process shut down"
    OverrideChecker.join()
    print "Override checker shut down"

    

    

if __name__ == '__main__':
    main()
