# ChitChat
A simple group chat Application using Socket Programming. Implementations are provided in both **Java** and **Python**. A simple GUI demonstration on localhost is shown below... This can be implemented over LAN connected machines by using their IP Address. #socket #socketProgramming #chat #groupchat

To watch how it is implemented click the link below:

https://www.linkedin.com/posts/deysarkarswarup_socket-socketprogramming-chat-activity-6581552689602236416-vMxm

## Java

Run the server first, then one or more clients.

```bash
javac SocketServer.java SocketClient.java
java SocketServer   # starts the server (and opens a local client)
java SocketClient   # open additional clients
```

## Python

Requires Python 3 and the standard library only. No extra packages are needed.

```bash
python socket_server.py   # start the server in one terminal
python socket_client.py   # start a client in another terminal
```

The Python client (`socket_client.py`) opens a tkinter GUI, prompts for the server IP and nickname, and now supports a current user list, image sharing, and simple chat commands.

### Features

- Server logging is written to `chitchat_server.log`.
- The client shows the current user list in a sidebar.
- `/users` requests a fresh user list from the server.
- `/msg USERNAME MESSAGE` sends a private one-to-one message.
- A Weather Unit dropdown in the sidebar switches between Celsius and Fahrenheit.
- `/unit C` or `/unit F` also switches weather output units from chat commands.
- `/weather CITY` asks the built-in WeatherBot for a live forecast from wttr.in using your selected unit.
- `/image PATH` sends a local image to everyone in the room. PNG and GIF work best with tkinter.
- `/me ACTION` sends an action message such as `/me is testing the bot`.
- `/help` prints the available commands.

### Notes

- Start the server first, then open one or more clients.
- If you want to share an image, use a local file path on the machine running the client.
- The weather command needs internet access because it fetches live data.
