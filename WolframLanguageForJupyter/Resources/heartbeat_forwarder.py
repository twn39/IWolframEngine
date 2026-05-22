import sys
import threading
import os

try:
    import zmq
except ImportError:
    # Exit with code 2 if pyzmq is missing
    sys.exit(2)

def monitor_stdin():
    try:
        sys.stdin.read()  # Blocks until EOF when parent process terminates
    except Exception:
        pass
    os._exit(0)

def main():
    if len(sys.argv) < 3:
        sys.exit(1)
        
    ip = sys.argv[1]
    port = int(sys.argv[2])
    
    # Start stdin monitor thread to prevent zombie processes
    t = threading.Thread(target=monitor_stdin)
    t.daemon = True
    t.start()
    
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    try:
        socket.bind(f"tcp://{ip}:{port}")
    except Exception as e:
        sys.exit(3)
        
    while True:
        try:
            msg = socket.recv()
            socket.send(msg)
        except Exception:
            break

if __name__ == '__main__':
    main()
