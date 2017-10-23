import socket
import re
import threading
import ssl
import zlib
import os
from time import sleep

class Server(object):
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.cert =  'cert.pem' #  generated server cert
        self.key = 'keyNOA.pem' # generated server key
        self.server_addr = (host,port)
        self.listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listen_socket.bind(self.server_addr)

        self.content, self.external_content = {}, {} # dictonaries to store the servable content
        for filez in os.listdir(os.getcwd()): # scan the root dir for files, read them and save their content
            if os.path.isdir(filez): # skip dirs
                continue
            else: # if not dir read the content of the file and store it in content{}
                with open(filez) as self.f:
                    self.content[filez] = self.f.read()
        for filez in os.listdir('files'): # the same but for files/ dir (this is where external files are kept)
            with open('files/'+filez) as self.f:
                self.external_content[filez] = self.f.read()

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
                threading.Thread(target = self.handle_client,args = (self.conn,self.address)).start() # start a thread

            except ssl.SSLError as e: # catch SSL errors
                print(e)

    def handle_client(self, conn, address):
        while True:
            try:
                request = conn.recv(1024)
                print(request)
                if request: # if client is there
                    request_dec = request.decode() # decode request
                    headz,content,compress = self.routes(request_dec) # deal with the request
                    if compress == True: # if client supports compression
                        z = zlib.compressobj(-1,zlib.DEFLATED,31)
                        compressed = z.compress(content) +  z.flush()
                        content = compressed
                    else: # if it doesn't, encode the content before sending it back
                        content = content.encode()

                    conn.send(headz.encode()) # send the header
                    conn.send(content) # send the compressed contet
                    conn.close() # don't keep the connection open
                else:
                    raise error('Client disconnected')
            except:
                conn.close()
                return False

    def routes(self, request):
        resp = ''
        compress = False # this will be used to check if compression should be used
        regex_get = re.compile(r"\bHEAD.*$|GET.*$",re.MULTILINE) # regex to match a line starting with GET or HEAD
        regex_http = re.compile(r"(?<=HTTP/).*?(?=\s)",re.MULTILINE) # regex to match the HTTP version line
        http_synt = re.compile(r"^[0-9.]*$",re.MULTILINE) # check if correct syntax is used for HTTP ver
        get_synt = re.compile(r"""[-!$%^&*()_+|~=`{}\[\];'"<>?,]""",re.MULTILINE)
        regex_encoding = re.compile(r"\bAccept-Encoding:.*$",re.MULTILINE) # check if 'Accept-Encoding' is present in the header
        request_get = regex_get.findall(request) # find it in the request
        request_get = ''.join(request_get) # convert from list to string

        request_http = regex_http.findall(request) # check if is the right syntax
        request_http = ''.join(request_http) # convert from list to string

        request_http_synt = http_synt.findall(request_http)
        request_http_synt = ''.join(request_http_synt)

        request_get_synt = get_synt.findall(request_get)
        request_get_synt = ''.join(request_get_synt)

        request_encoding = regex_encoding.findall(request)
        request_encoding = ''.join(request_encoding)

        http_ver = '1.1'

        # verify HTTP version requested
        if request_http_synt == '': # if requested HTTP version syntax is malformed
            #print('syntax')
            headz = 'HTTP/1.1 400 Bad Request\nContent-Type: text/html; charset=utf-8\n'
            resp = '<body><h1>Malformed HTTP version syntax</h1></body>'
        elif request_http_synt.find(http_ver) == '': # if syntax is fine, but requested version is other than 1.1
            headz = 'HTTP/1.1 505 HTTP Version Not Supported\nContent-Type: text/html; charset=utf-8\n'
            resp = '<body><h1>Invaldi HTTP version. Currently the server only supports HTTP 1.1</h1></body>'
        else: # HTTP version 1.1
            # verifty if GET is used
            if request_get == '': # GET was not used
                headz = 'HTTP/1.1 501 Not Implemented\nContent-Type: text/html; charset=utf-8\n'
                resp = '<html><h5>Invalid method was used. Currently the server only supports GET and HEAD method</html>'
            else: # GET was used
                if request_get_synt != '': # malformed GET path syntax
                    headz = 'HTTP/1.1 400 Bad Request\nContent-Type: text/html; charset=utf-8\n'
                    resp = '<html><h5>Invalid characters in the requested path </h5></html>'
                else: # syntax is fine
                    for linez in self.content: # see if the requested path matches any locations on the server
                        if linez in request_get:
                            resp = self.content[linez] # if it does pull the coresponding content
                    if resp == '': # if blank location || does not exists || an external file is requested
                        if request_get.find('GET / HTTP/1.1') == 0: # if blank location
                            headz = 'HTTP/1.1 200 OK\nContent-Type: text/html; charset=utf-8\n'
                            resp = self.content['home.html']

                        for xo in self.external_content: # check if the request is for external files
                            if xo in request_get:
                                headz = 'HTTP/1.1 200 OK\nContent-Type: image/jpeg; charset=utf-8\nConnection: keep-alive\n'
                                resp = self.external_content[xo]

                        if resp == '': # re-check if resp is empty, if so - 404
                            headz = 'HTTP/1.1 404 Not Found\nContent-Type: text/html; charset=utf-8\n'
                            resp = '<html><h5>The requested file can&#x27;t be found </h5></html>'
                    else: # and if the location DOES exist
                        headz = 'HTTP/1.1 200 OK\nContent-Type: text/html; charset=utf-8\n'

        if request_encoding != '': # if client supports compression
            headz += 'Content-Encoding: gzip\n'
            compress = True

        response_size = (len(resp)) # calculate size of response
        headz += 'Content-Length: '+str(response_size)+'\n\n' # add it to header
        return headz,resp,compress

if __name__ == "__main__":
    while True:
        port_num = input("Which port should I listen to? ")
        try:
            port_num = int(port_num)
            break
        except ValueError:
            pass

    Server('',port_num).server_listen()
