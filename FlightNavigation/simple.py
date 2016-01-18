#!/usr/local/bin/python

from dronekit import connect, VehicleMode, LocationGlobalRelative
import time
import argparse

vehicle = None 


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

    # Set up option parsing to get connection string
    parser = argparse.ArgumentParser(description='Print out vehicle state information. '
                                                 'Connects to SITL on local PC by default.')
    parser.add_argument('--connect', default='tcp:localhost:14550',
			help="vehicle connection target. Default 'localhost:14550'")
    # parser.add_argument('--connect', default='tcp:127.0.0.1:5760',
    # help="vehicle connection target. Default 'localhost:14550'")

    args = parser.parse_args()

    # Connect to the Vehicle
    print 'Connecting to vehicle on: %s' % args.connect
    vehicle = connect('/dev/ttyAMA0', baud=57600, wait_ready=True)

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

    exit()


def go_to_coordinate(latitude, longitude, altitude=10, speed=5):
    global vehicle

    vehicle.mode = VehicleMode("GUIDED")
    print "Navigating to point"
    point = LocationGlobalRelative(latitude, longitude, altitude)
    vehicle.simple_goto(point, groundspeed=speed)

    # sleep so we can see the change in map
    time.sleep(30)


def print_altitude():
    while True:
        print vehicle.location.global_relative_frame.alt
        time.sleep(1)


def main():

    setup()
    # p = Thread(target = printAltitude)
    # p.start()

    while True:
        print "\n---------------------------------------------------------------------------\n"
        print "What shall I do next?"
        print "Options: takeoff, land, goto, end"
        command = raw_input("What shall I do next?\n")

        if command == "takeoff":
            takeoff(10)
        elif command == "land":
            return_to_launch()
        elif command == "end":
            end_flight()
        elif command == "goto":
            latitude = float(raw_input("Latitude: "))
            longitude = float(raw_input("Longitude: "))
            altitude = float(raw_input("Altitude: "))
            go_to_coordinate(latitude, longitude, int(altitude))
        else:
            print "Not a vaild command."


if __name__ == '__main__':
    main()
