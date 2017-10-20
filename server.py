import socket
import re
import threading
import ssl
import zlib

class Server(object):
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.cert =  'cert.pem'
        self.key = 'key.pem'
        self.server_addr = (host,port)
        self.listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listen_socket.bind(self.server_addr)

        self.pathz = ['home.html','drugs.html','escort.html'] # available locations on the server
        self.content = {} # dictonary to store the servable content
        for self.values in self.pathz:
            with open(self.values) as self.f:
                self.content[self.values] = self.f.read()

    def server_listen(self):
        self.listen_socket.listen(5)
        self.ssl_wrap = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH) # create new ssl context obj
        self.ssl_wrap.load_cert_chain(certfile=self.cert,keyfile=self.key) # load cert
        self.ssl_wrap.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1  # specify which SSL protocol to use
        self.ssl_wrap.set_ciphers('EECDH+AESGCM:EDH+AESGCM:AES256+EECDH:AES256+EDH') # specify which cipher suite to use

        print('Serving HTTP on port {port} ...'.format(port=self.port))
        while True:
            self.client, self.address = self.listen_socket.accept()
            try:
                self.conn = self.ssl_wrap.wrap_socket(self.client, server_side=True)
                 # client_connection.settimeout(60)  is this needed???
                threading.Thread(target = self.handle_client,args = (self.conn,self.address)).start()
            except ssl.SSLError as e: # catch SSL errors
                print(e)

    def handle_client(self, conn, address):
        while True:
            try:
                request = conn.recv(1024)
                if request: # if client is there
                    request_dec = request.decode() # decode request
                    print (request_dec)
                    headz,content = self.routes(request_dec) # deal with the request
                    z = zlib.compressobj(-1,zlib.DEFLATED,31)
                    compress = z.compress(content) + z.flush()
                    print (content)
                    conn.send(headz.encode()) # send the header
                    conn.send(compress) # send the compressed contet
                    conn.close() # don't keep the connection open
                else:
                    raise error('Client disconnected')
            except:
                conn.close()
                return False

    def routes(self, request):
        resp = ''
        regex = re.compile(r"\bGET.*$",re.MULTILINE) # regex to match a line starting with GET
        request = regex.findall(request) # find it in the request
        request = ''.join(request) # convert from list to string

        # see if the request path matches any locations on the server
        for linez in self.pathz:
            if linez in request:
                resp = self.content[linez] # if it does pull the coresponding content

        if resp == '': # if location does not exists - 404, baby!
            headz = 'HTTP/1.1 404 Not Found\nContent-Type: text/html; charset=utf-8\n\n'
            resp = '<body><h1>Sowwwiiii, ces&#x27;t no possible </h1></body>'

        else: # and if the location DOES exist
            headz = 'HTTP/1.1 200 OK\nContent-Type: text/html; charset=utf-8\nContent-Encoding: gzip\n\n'

        return headz,resp

if __name__ == "__main__":
    while True:
        port_num = input("Which port should I listen to? ")
        try:
            port_num = int(port_num)
            break
        except ValueError:
            pass

    Server('',port_num).server_listen()
