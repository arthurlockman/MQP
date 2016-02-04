import socket, pickle


def main():
	image_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	gps_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    while True:
        try:
            image_socket.connect(('localhost', 5001))
            gps_socket.connect(('localhost', 5002))
            break
        except:
            pass

    while True:

        print "\n---------------------------------------------------------------------------\n"
        print "Options: takeoff, land, end, stop, circle, goto, ignore, search, clearq"

        command = raw_input("What shall I do next?\n")
        data = pickle.dumps(command)
        image_socket.send(data)


if __name__ == '__main__':
	main()