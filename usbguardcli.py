#!/usr/bin/env python3
import re
import subprocess
from curses import wrapper
from shutil import get_terminal_size

import urwid

NAME = "usgguardcli"
VERSION = 0.1
HELP_TEXT = f"""
{NAME} {VERSION}
"""

TERM_SIZE = get_terminal_size().columns
NAME_COL_SIZE = TERM_SIZE // 3


def get_device_list():
    subp = subprocess.run(
        ["usbguard", "list-devices"],
        capture_output=True,
        bufsize=1,
        universal_newlines=True,
    )
    output = str(subp.stdout)
    return output.split("\n")


def allow_device(device_id):
    subp = subprocess.run(["usbguard", "allow-device", device_id],)
    if subp.returncode != 0:
        raise PermissionError("Cannot allow device: " + subp.stderr)


def block_device(device_id):
    subp = subprocess.run(["usbguard", "block-device", device_id],)
    if subp.returncode != 0:
        raise PermissionError("Cannot block device: " + subp.stderr)


class DeviceButton(urwid.Button):
    def __init__(self, device):
        self.device_nr = device.split(":")[0]
        self.device_status = device.split()[1]
        self.id = device.split()[3]
        self.name = re.search(r'name "([^"]*)"', device).group(1)
        self.connect_type = re.search(r'with-connect-type "([^"]*)"', device).group(1)
        label = (
            f"[{self.device_nr}] {self.id}  "
            + f"{self.name.ljust(NAME_COL_SIZE)} <{self.connect_type}>"
        )
        super().__init__(label)
        self.set_state(self.device_status)

    def connect_signal(self, call):
        urwid.connect_signal(self, "click", call, self.device_nr)

    def set_state(self, state=None):
        # label = self.label.replace(self.device_status, state)
        self.set_label((state, self.label))
        self.device_status = state


class States:
    ALLOW = "allow"
    BLOCK = "block"


class Tui:
    palette = [
        ("reversed", "standout", "default"),
        (States.ALLOW, "black", "light green"),
        (States.BLOCK, "black", "light red"),
    ]

    def __init__(self,):
        body = [urwid.Text("Devices"), urwid.Divider()]
        self.devices = get_device_list()
        for dev in self.devices:
            if dev.strip() == "":
                continue
            button = DeviceButton(dev)
            button.connect_signal(self.toggle)
            body.append(urwid.AttrMap(button, None, focus_map="reversed"))
        focuswalker = urwid.SimpleFocusListWalker(body)
        self.list = urwid.ListBox(focuswalker)
        self.left = urwid.Padding(self.list, left=2, right=2)

        self.cols = urwid.Columns([self.left])
        urwid.connect_signal(focuswalker, "modified", self.handle_input)

        # Start the MainLoop
        self.loop = urwid.MainLoop(
            self.cols, palette=self.palette, unhandled_input=self.handle_input
        )

    def __run__(self, stdscr):
        self.loop.run()

    def run(self):
        wrapper(self.__run__)

    def get_selected(self):
        return self.left.base_widget.get_focus_widgets()[0]

    def up(self):
        focus = self.left.base_widget.focus_position
        if focus <= 2:
            return
        self.left.base_widget.set_focus(focus - 1)

    def down(self):
        focus = self.left.base_widget.focus_position
        try:
            self.left.base_widget.set_focus(focus + 1)
        except IndexError:
            # We are already at the lowest entry
            pass

    def exit(self):
        raise urwid.ExitMainLoop()

    def handle_input(self, key=None):
        if key in ("q", "Q"):
            self.exit()

        # This will most likely fail due to a race condition in __init__
        # Doesn't matter, just ignore it
        try:
            button = self.get_selected()
            name = self.get_selected_pkg().pkgName
        except AttributeError:
            return

        if key is None:
            self.toggle(button, name)
        # Vim-movements
        elif key == "j":
            self.down()
        elif key == "k":
            self.up()
        elif key == "r":
            self.__init__()

    def toggle(self, button, _):
        if button.device_status == States.BLOCK:
            allow_device(button.device_nr)
            button.set_state(States.ALLOW)
        else:
            if button.connect_type != "hotplug":
                # TODO show error message or warning
                return
            block_device(button.device_nr)
            button.set_state(States.BLOCK)
        # self.__init__()


if __name__ == "__main__":
    tui = Tui()
    tui.run()
