import SimpleHTTPServer
import SocketServer
import cgi
import socket
import pickle

# gps_sock = None

class ServerHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):

    def do_GET(self):
        print("======= GET STARTED =======")
        print(self.headers)
        SimpleHTTPServer.SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        print("======= POST STARTED =======")
        print(self.headers)
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={'REQUEST_METHOD':'POST',
                     'CONTENT_TYPE':self.headers['Content-Type'],
                     })
        print("======= POST VALUES =======")
        for item in form.list:
            print(item)
        latlong = form.getvalue('latitude'), form.getvalue('longitude')
        data_string = pickle.dumps(latlong)
        print(data_string)
        gps_sock.send(data_string)


if __name__ == '__main__':
    global gps_sock
    PORT = 8000

    Handler = ServerHandler

    httpd = SocketServer.TCPServer(("", PORT), Handler)

    print "serving at port", PORT
    httpd.serve_forever()
    gps_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    gps_sock.connect(('localhost', 5002))
