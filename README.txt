Required external programs:

* Node.js (https://nodejs.org/)
* Python 3.7+ (https://www.python.org/)

Installing npm dependencies (inside the client/ directory):

    npm install

Installing Python dependencies (in the root directory):

    pip install -r requirements.txt

Building the frontend (inside the client/ directory):

    npm run build

Before starting the server, the file server-config.ini must exist (copy and
rename it from example-server-config.ini) with the desired configuration.

Starting the server (in the root directory):

    python -m server
