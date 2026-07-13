import sys
import socket


# H3C Comware Python 2.7 compatible webhook sender.
# Keep this file dependency-free: no requests, no json, no f-strings.

HA_HOST = "192.168.1.249"
HA_PORT = 8123
WEBHOOK_PATH = "/api/webhook/h3c_tv_sync_xyz123"
TIMEOUT = 2

VALID_TVS = (
    "master_bedroom",
    "living_room",
    "elder_room",
    "study_room",
    "test_tv",
)

VALID_STATES = (
    "on",
    "off",
    "enable",
    "disable",
    "blocked",
    "allowed",
)


def is_safe_value(value):
    allowed_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
    if not value:
        return False
    for char in value:
        if char not in allowed_chars:
            return False
    return True


def get_args():
    if len(sys.argv) >= 3:
        tv_name = sys.argv[1]
        action_state = sys.argv[2]
    else:
        # Safe defaults for manual connectivity tests on the switch.
        tv_name = "test_tv"
        action_state = "on"

    if not is_safe_value(tv_name) or not is_safe_value(action_state):
        raise ValueError("Arguments only allow letters, numbers, underscore and hyphen")

    if tv_name not in VALID_TVS:
        raise ValueError("Invalid tv: " + tv_name)

    if action_state not in VALID_STATES:
        raise ValueError("Invalid state: " + action_state)

    return tv_name, action_state


def build_request(tv_name, action_state):
    body = '{"tv":"%s","state":"%s"}' % (tv_name, action_state)

    headers = ""
    headers += "POST " + WEBHOOK_PATH + " HTTP/1.1\r\n"
    headers += "Host: " + HA_HOST + ":" + str(HA_PORT) + "\r\n"
    headers += "Content-Type: application/json\r\n"
    headers += "Content-Length: " + str(len(body)) + "\r\n"
    headers += "Connection: close\r\n"
    headers += "\r\n"

    return headers + body


def send_webhook(request):
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(TIMEOUT)
        sock.connect((HA_HOST, HA_PORT))
        sock.sendall(request)

        try:
            response = sock.recv(128)
        except socket.timeout:
            response = ""

        return response
    finally:
        if sock:
            sock.close()


def main():
    try:
        tv_name, action_state = get_args()
        request = build_request(tv_name, action_state)
        response = send_webhook(request)

        if response.startswith("HTTP/1.1 200") or response.startswith("HTTP/1.0 200"):
            print("Success: webhook sent, tv=" + tv_name + ", state=" + action_state)
            return 0

        if response:
            print("Warning: webhook sent but response was: " + response.split("\r\n")[0])
            return 0

        print("Warning: webhook sent but no HTTP response received")
        return 0
    except Exception as error:
        print("Error: " + str(error))
        return 1


if __name__ == "__main__":
    sys.exit(main())