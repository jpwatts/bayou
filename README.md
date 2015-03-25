Bayou is an event stream server.

Run the server:

    $ bayou

Append an event:

    $ curl -d '"Hello, World"' "http://127.0.0.1:8000/example"
    {"data":"Hello, World",offset=0,time="..."}

Read events:

    $ curl "http://127.0.0.1:8000/example"
    {"data":"Hello, World",offset=0,time="..."}
    ...
