import json
import os
import socket
import sys
import time


HOST = "192.168.1.254"
USER = "hass_robot"
PASSWORD = os.environ.get("H3C_SWITCH_PASSWORD")
ACL_ID = 3000
ACL_DESCRIPTION = "Block_TV_Internet_Permit_Internal"


TVS = {
    "master_bedroom": {
        "name": "主卧室 Sony 电视",
        "ip": "192.168.1.24",
        "mac": "cc98-8b23-abaa",
        "permit_rule": 10,
        "deny_rule": 15,
    },
    "living_room": {
        "name": "客厅 Sony 电视",
        "ip": "192.168.1.25",
        "mac": "88c9-e8d1-bcb0",
        "permit_rule": 20,
        "deny_rule": 25,
    },
    "elder_room": {
        "name": "老人房 Sony 电视",
        "ip": "192.168.1.26",
        "mac": "cc98-8b36-afc7",
        "permit_rule": 30,
        "deny_rule": 35,
    },
    "study_room": {
        "name": "书房 Sony 电视",
        "ip": "192.168.1.27",
        "mac": "7026-05e6-0afd",
        "permit_rule": 40,
        "deny_rule": 45,
    },
}


IAC = 255
DONT = 254
DO = 253
WONT = 252
WILL = 251


class H3CTelnetClient:
    def __init__(self, host, username, password, port=23, timeout=5):
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.timeout = timeout
        self.sock = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()

    def connect(self):
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self.sock.settimeout(1)

        self.read_until_any(["login:", "username:", "user name:"], timeout=8)
        self.send_line(self.username)
        self.read_until_any(["password:"], timeout=8)
        self.send_line(self.password)
        time.sleep(0.5)
        return self.read_available(timeout=1)

    def close(self):
        if self.sock:
            try:
                self.send_line("quit")
            except OSError:
                pass
            self.sock.close()
            self.sock = None

    def run_commands(self, commands, wait=0.8):
        output = []
        for command in commands:
            self.send_line(command)
            time.sleep(wait)
            output.append(self.read_available(timeout=2))
        return "\n".join(output)

    def send_line(self, text):
        self.sock.sendall(text.encode("ascii") + b"\r\n")

    def read_until_any(self, keywords, timeout=5):
        end_time = time.time() + timeout
        output = ""

        while time.time() < end_time:
            output += self.read_available(timeout=0.8)
            lower_output = output.lower()
            if any(keyword.lower() in lower_output for keyword in keywords):
                return output

        return output

    def read_available(self, timeout=1):
        end_time = time.time() + timeout
        chunks = []

        while time.time() < end_time:
            try:
                data = self.sock.recv(4096)
            except socket.timeout:
                break

            if not data:
                break

            chunks.append(self._negotiate_telnet(data))
            self.sock.settimeout(0.2)

        self.sock.settimeout(1)
        return b"".join(chunks).decode("utf-8", errors="ignore").replace("\x00", "")

    def _negotiate_telnet(self, data):
        clean = bytearray()
        i = 0

        while i < len(data):
            byte = data[i]
            if byte != IAC:
                clean.append(byte)
                i += 1
                continue

            if i + 2 >= len(data):
                break

            command = data[i + 1]
            option = data[i + 2]

            if command == WILL:
                self.sock.sendall(bytes([IAC, DONT, option]))
                i += 3
            elif command == DO:
                self.sock.sendall(bytes([IAC, WONT, option]))
                i += 3
            elif command in (WONT, DONT):
                i += 3
            else:
                i += 2

        return bytes(clean)


class TVInternetController:
    def __init__(self, host=HOST, username=USER, password=PASSWORD, acl_id=ACL_ID):
        if not password:
            raise RuntimeError("请先设置 H3C_SWITCH_PASSWORD 环境变量")

        self.host = host
        self.username = username
        self.password = password
        self.acl_id = acl_id
        self.tvs = TVS

    def enable_internet(self, tv_key, save=False):
        """允许指定电视上网：删除该电视的 deny 规则，保留内网 permit 规则。"""
        tv = self._get_tv(tv_key)
        commands = [
            "system-view",
            f"acl advanced {self.acl_id}",
            f"undo rule {tv['deny_rule']}",
            "quit",
            "quit",
        ]
        if save:
            commands.append("save force")
        output = self._run(commands)
        self._ensure_no_command_error(output)
        return output

    def disable_internet(self, tv_key, save=False):
        """禁止指定电视上网：恢复该电视的 deny 规则。"""
        tv = self._get_tv(tv_key)
        commands = [
            "system-view",
            f"acl advanced {self.acl_id}",
            f"undo rule {tv['deny_rule']}",
            f"rule {tv['deny_rule']} deny ip source {tv['ip']} 0",
            "quit",
            "quit",
        ]
        if save:
            commands.append("save force")
        output = self._run(commands)
        self._ensure_no_command_error(output)
        return output

    def get_acl(self):
        return self._run(["screen-length disable", "display acl all"])

    def get_statuses(self):
        acl_output = self.get_acl()
        statuses = {}
        for key, tv in self.tvs.items():
            deny_rule = f"rule {tv['deny_rule']} deny ip source {tv['ip']} 0"
            statuses[key] = {
                **tv,
                "internet_enabled": deny_rule not in acl_output,
            }
        return statuses

    def list_tvs(self):
        return self.tvs

    def _run(self, commands):
        with H3CTelnetClient(self.host, self.username, self.password) as client:
            return client.run_commands(commands)

    def _ensure_no_command_error(self, output):
        error_markers = [
            " % ",
            "Unrecognized command",
            "Too many parameters",
            "No such ACL",
            "Invalid input",
        ]
        if any(marker in output for marker in error_markers):
            raise RuntimeError(f"交换机返回命令错误：\n{output}")

    def _get_tv(self, tv_key):
        if tv_key not in self.tvs:
            valid_keys = ", ".join(self.tvs)
            raise ValueError(f"未知电视: {tv_key}. 可用值: {valid_keys}")
        return self.tvs[tv_key]


if __name__ == "__main__":
    controller = TVInternetController()
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    tv_key = sys.argv[2] if len(sys.argv) > 2 else None

    if action == "status":
        print("电视上网状态：")
        for key, tv in controller.get_statuses().items():
            state = "允许上网" if tv["internet_enabled"] else "禁止上网"
            print(f"- {key}: {tv['name']} {tv['ip']} {tv['mac']} -> {state}")
    elif action == "status-json":
        statuses = controller.get_statuses()
        print(json.dumps({
            key: tv["internet_enabled"]
            for key, tv in statuses.items()
        }))
    elif action == "enable" and tv_key:
        print(controller.enable_internet(tv_key))
        print(f"{controller.list_tvs()[tv_key]['name']} 已允许上网")
    elif action == "disable" and tv_key:
        print(controller.disable_internet(tv_key))
        print(f"{controller.list_tvs()[tv_key]['name']} 已禁止上网")
    else:
        print("用法：")
        print("  python tv_internet_control.py status")
        print("  python tv_internet_control.py status-json")
        print("  python tv_internet_control.py enable master_bedroom")
        print("  python tv_internet_control.py disable master_bedroom")

        print("\n可用电视：")
        for key, tv in controller.list_tvs().items():
            print(f"  {key}: {tv['name']}")
