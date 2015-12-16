#!/usr/bin/python

from dronekit import connect, VehicleMode, LocationGlobalRelative
import time
import argparse
import globals as glb  


def initialize():
	print "Basic pre-arm checks"

    # Don't let the user try to arm until autopilot is ready
    while not glb.vehicle.is_armable:
        print "Waiting for vehicle to initialize..."
        time.sleep(1)


def arm():        
    print "Arming motors"
    # Copter should arm in GUIDED mode
    glb.vehicle.mode = glb.VehicleMode("GUIDED")
    glb.vehicle.armed = True    

    while not glb.vehicle.armed:      
        print " Waiting for arming..."
        time.sleep(1)


def takeoff(aTargetAltitude = 10):
    glb.vehicle.mode = glb.VehicleMode("GUIDED")

    print "Taking off!"
    glb.vehicle.simple_takeoff(aTargetAltitude) # Take off to target altitude

    # Wait until the vehicle reaches a safe height before processing the goto (otherwise the command 
    #  after Vehicle.simple_takeoff will execute immediately).
    while True:
        print " Altitude: ", glb.vehicle.location.global_relative_frame.alt 
        #Break and return from function just below target altitude.        
        if glb.vehicle.location.global_relative_frame.alt>=aTargetAltitude*0.95: 
            print "Reached target altitude"
            break
        time.sleep(1)


def setup():
	#Set up option parsing to get connection string
	parser = argparse.ArgumentParser(description='Print out vehicle state information. Connects to SITL on local PC by default.')
	parser.add_argument('--connect', default='localhost:14550', help="vehicle connection target. Default 'localhost:14550'")
	args = parser.parse_args()

	# Connect to the Vehicle
	print 'Connecting to vehicle on: %s' % args.connect
	glb.vehicle = connect(args.connect, wait_ready=True)

	# Initialize the vehicle
	initialize()

	# Arm the vehicle
	arm()

	print "Set default/target airspeed to 3"
	glb.vehicle.airspeed=3


def return_to_launch():
	print "Returning to Launch"
	glb.vehicle.mode = glb.VehicleMode("RTL")


def end_flight():
	#Close vehicle object before exiting script
	print "Close vehicle object"
	glb.vehicle.close()

	exit()


def go_to_coordinate(latitude, longitude, altitude = 10, speed = 5):
	glb.vehicle.mode = glb.VehicleMode("GUIDED")
	print "Navigating to point"
	point = LocationGlobalRelative(latitude, longitude, altitude)
	glb.vehicle.simple_goto(point, groundspeed = speed)

	# sleep so we can see the change in map
	time.sleep(30)


def main():

	setup()

	while True:
		print "\n---------------------------------------------------------------------------\n"
		print "What shall I do next?"
		print "Options: takeoff, land, goto, end"
		command = raw_input("What shall I do next?")

		if command.lower == "takeoff":
			takeoff(10)
		elif command.lower == "land":
			return_to_launch()
		elif command.lower == "end":
			end_flight()
		elif command.lower == "goto":
			latitude = float(raw_input("Latitude: "))
			longitude = float(raw_input("Longitude: "))
			altitude = float(raw_input("Altitude: "))
			go_to_coordinate(latitude, longitude, altitude) 
		else
			print "Not a vaild command."


if __name__ == '__main__':
	main()