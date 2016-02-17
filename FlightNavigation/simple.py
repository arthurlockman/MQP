#!/usr/local/bin/python

from dronekit import connect, VehicleMode, LocationGlobalRelative
from pymavlink import mavutil
import time
import argparse
import sys
import pickle
from multiprocessing import Queue, Process, Value
import socket
import os
import math
import copy

# Global Variables and Flags
vehicle = None
ignore_target = True
tangential_speed = 100 # cm/s
circle_period = sys.maxint
homing = False
last_image_location = (0, 0)

# Process shared flags
identified = None
shutdown = None

# Sockets
image_socket = None
gps_socket = None
shell_socket = None

# Shared queues
image_data = Queue(maxsize=1)
gps_coordinates = Queue()
shell_commands = Queue()

# Simulator flag
SIM = True

def setup():
    global vehicle

    # Connect to the Vehicle
    print "Connecting to the vehicle..."
    if SIM == False:
        vehicle = connect('/dev/ttyAMA0', baud=57600, wait_ready=True)
    else: 
        vehicle = connect('tcp:localhost:5760', baud=57600, wait_ready=True)

    # Initialize the vehicle
    while not vehicle.is_armable:
        print "Waiting for vehicle to initialize..."
        time.sleep(1)

    # Arm the vehicle
    # arm()

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

    print "arming"
    # Arm the UAV
    arm()

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
    # while vehicle.location.global_relative_frame.alt >= 0:
    #   time.sleep(1)


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
    with shutdown.get_lock():
        shutdown.value = 1


def go_to_coordinate(latitude, longitude, altitude=10, speed=5):
    global vehicle

    print "Navigating to point"
    vehicle.mode = VehicleMode("GUIDED")
    print latitude
    print longitude
    print type(latitude)
    print type(longitude)
    point = LocationGlobalRelative(latitude, longitude, altitude)
    vehicle.simple_goto(point, groundspeed=speed)

    # sleep so we can see the change in map
    # time.sleep(30)


def circle_POI():
    global vehicle, ignore_target, tangential_speed, circle_period
    
    # Serach for the target
    ignore_target = False

    # The circle radius in cm. Max 10000
    # The tangential speed is 100 cm/s
    speed = tangential_speed

    # Radius has to be increments of 100 cm and rate has to be in increments of 1 degree
    radius = int(100)
    period = 2*math.pi*radius / speed
    rate = int(360.0/period)

    vehicle.parameters["CIRCLE_RADIUS"] = radius
    vehicle.parameters["CIRCLE_RATE"] = rate

    vehicle.mode = VehicleMode("CIRCLE")

    # Update the global variable for the next circle
    circle_period = period


def update_circle_params():
    global vehicle, tangential_speed, circle_period

    current_radius = vehicle.parameters["CIRCLE_RADIUS"]
    current_rate = vehicle.parameters["CIRCLE_RATE"]

    new_radius = current_radius + 100
    new_period = 2*math.pi*new_radius / tangential_speed
    new_rate = int(360.0/new_period)

    vehicle.parameters["CIRCLE_RADIUS"] = new_radius
    vehicle.parameters["CIRCLE_RATE"] = new_rate

    # Update the global variable for the next circle
    circle_period = new_period


def stop():
    global vehicle

    vehicle.mode = VehicleMode("GUIDED")
    print "stopped"

def clearGPSQueue():
    global gps_coordinates

    # Deletes and reinstatiates the GPS queue
    del gps_coordinates
    gps_coordinates = Queue()

def check_user_control():
    global vehicle, SIM

    if SIM == True:
        return False

    value = vehicle.channels['8']

    # print value

    if value < 1450:
        return True
    else:
        return False

def printData():
    global vehicle, gps_coordinates, homing

    print "Alt: ", vehicle.location.global_relative_frame.alt
    print "Lat: ", vehicle.location.global_relative_frame.lat
    print "Lon: ", vehicle.location.global_relative_frame.lon
    print "Mode: ", vehicle.mode
    print "Homing: ", homing
    print "Ignore: ", ignore_target
    # print "GPS: "

'''
    # Print the GPS points
    while True:
        try:
            coordinate = gps_coordinates.get_nowait()
            print coordinate
            gps_coordinates.put(coordinate)
        except:
            break
'''

def drop():
    os.system('python ../experiments/drop_gpio.py')

def shell_handler(command):
    global gps_coordinates, ignore_target, vehicle, homing

    print command

    if command == "takeoff":
        # Blocking
        takeoff(6)

    elif command == "land":
        # Blocking
        return_to_launch()

    elif command == "end":
        # Kills everything
        end_flight()

    elif command == "stop":
        # Non-blocking
        stop()
        homing = False

    elif command == "circle":
        # Non-blocking
        circle_POI()

    elif command == "goto":
        # Non-blocking? 

        # Make sure there is a location to go to
        location = []
        try:
            location = gps_coordinates.get_nowait()
        except:
            print "No available GPS coordinate"
            return

        print location
        go_to_coordinate(location[0], location[1], altitude=10, speed=5)

    elif command == "ignore":
        ignore_target = True
        homing = False

    elif command == "search":
        ignore_target = False
        homing = False

    elif command == "clearq":
        clearGPSQueue()

    elif command == "print":
        printData()

    elif command == "override":
        homing = False
        vehicle.mode = VehicleMode("LOITER") 

    elif command == "drop":
        drop()

    else:
        print "Not a vaild command."


def process_image_data():
    global image_data, identified, shutdown, image_socket, last_image_location

    while True:
        try:
            client_socket, address = image_socket.accept()
            print "Image socket connected from ", address
            break
        except:
            pass

    while True:

        # If it is time to shutdown
        with shutdown.get_lock():
            if shutdown.value == 1:
                print "Shutting down."
                break

        # image_socket is non-blocking, so an exception might be raised if there is no data in the socket
        try:
            # Get the data
            data_string = client_socket.recv(512)

            # Clear the current data in the shared queue
            try:
                image_data.get(block=False)
            except:
                pass

            # Add the new data
            data = pickle.loads(data_string)
            image_data.put(data)

            # If the target has been seen, set the flag
            with identified.get_lock():
                if data != -1:
                    print "Saw something!"
                    print data
                    last_image_location = data
                    identified.value = 1
                else:
                    identified.value = 0
        except:
            pass

        

def process_gps_data():
    global gps_coordinates, shutdown, gps_socket

    while True:
        try:
            client_socket, address = gps_socket.accept()
            print "GPS socket connected from ", address
            break
        except:
            pass

    while True:
        # gps_socket is non-blocking, so an exception might be raised if there is no data in the socket
        
        # If it is time to shut down
        with shutdown.get_lock():
            if shutdown.value == 1:
                print "Shutting down"
                break

        try:
            data_string = client_socket.recv(512)
            data = pickle.loads(data_string)
            print data
            gps_coordinates.put(data)
        except:
            continue

def process_shell_data():
    global shell_commands, shutdown, shell_socket

    # Connect the shell socket
    # Must connect to shell before the UAV will arm
    while True:
        try:
            client_socket, address = shell_socket.accept()
            print "Shell socket connected from ", address
            break
        except:
            pass

    while True:
    
        # If it is time to shut down
        with shutdown.get_lock():
            if shutdown.value == 1:
                print "Shutting down"
                break

        # shell_socket is non-blocking, so an exception might be raised if there is no data in the socket
        try:
            # Recieve data from shell socket
            data_string = client_socket.recv(512)
            data = pickle.loads(data_string)

            # Put it in the commands queue to be processed
            shell_commands.put(data)
            
        except:
            pass

def main():
    global image_socket, gps_socket, shell_socket, vehicle, identified, shutdown, homing, last_image_location, ignore_target

    # Multi-core shared variables
    identified = Value('i', 0)
    shutdown = Value('i', 0)

    # Start the other scripts
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

    # Shell information handler
    ShellProcess = Process(target=process_shell_data)
    ShellProcess.start()

    # Initialize and arm the vehicle
    setup()

    # Time variable
    last_time = time.time()

    # Main control loop
    while True:

        # Check user override switch
        if check_user_control() == True:
            homing = False
            vehicle.mode = VehicleMode("LOITER")

        # See if there are any new commands queued up and act accordingly
        try:
            data = shell_commands.get_nowait()
            shell_handler(data)
        except:
            pass

        # Check if the circle needs to be expanded
        if SIM == False and vehicle.mode == "CIRCLE" and (time.time() - last_time > circle_period):
            update_circle_params()
            last_time = time.time()
            print "Expanding circle."

        # Check and see if the target has been found
        # Stop only if it has and you want to stop
        with identified.get_lock():
            if identified.value == 1 and ignore_target == False and not homing:
                print "Target Found!!"
                stop()
                homing = True
                ignore_target = True

        # Home in on the taret
        if homing == True:

            alt = vehicle.location.global_relative_frame.alt
            FOV = 48.1 # Degrees
            angle_345 = 36.87 # degrees

            # Calculate the actual viewing X,Y distances
            X = 2 * alt * math.tan(math.radians(FOV/2)) * math.cos(math.radians(angle_345))
            Y = 2 * alt * math.tan(math.radians(FOV/2)) * math.sin(math.radians(angle_345))

            (cx, cy) = last_image_location

            # Calculate the actual distance between the drone the the target
            # Scale the pixel location to the real location
            dX = (cx - 320) * X / 640
            dY = (cy - 240) * Y / 480

            # print "dX: ", dX
            # print "dY: ", dY

            # Relative to the current location
            msg = vehicle.message_factory.set_position_target_local_ned_encode(
            0,       # time_boot_ms (not used)
            0, 0,    # target_system, target_component
            mavutil.mavlink.MAV_FRAME_BODY_NED, # frame
            0b0000111111000000, # type_mask (enable speeds and velocities only)
            dX, dY, 0, # x, y, z positions
            0, 0, 0, # x, y, z velocity in m/s
            0, 0, 0, # x, y, z acceleration (not supported yet, ignored in GCS_Mavlink)
            0, 0)    # yaw, yaw_rate (not supported yet, ignored in GCS_Mavlink)
            # send command to vehicle
            vehicle.send_mavlink(msg)

            if abs(dX) <= .15 and abs(dY) <= 0.15:
                print "Centered!"
                homing = False
                vehicle.mode = VehicleMode("GUIDED")

        # If it is time to shut down
        with shutdown.get_lock():
            if shutdown.value == 1:
                break

    # Wait for the child processes to terminate
    GPSProcess.join()
    print "GPS process shut down"
    ImageProcess.join()
    print "Image process shut down"
    ShellProcess.join()
    print "Shell process shut down"

    # Shutdown the sockets
    image_socket.shutdown(socket.SHUT_RDWR)
    gps_socket.shutdown(socket.SHUT_RDWR)
    shell_socket.shutdown(socket.SHUT_RDWR)

    # Close the sockets
    image_socket.close()
    gps_socket.close()
    shell_socket.close()

    exit()
    

if __name__ == '__main__':
    main()
