import json
import os
import sys
import time
import traceback
import urllib.error
import urllib.request
from datetime import datetime

import win32con
import win32print
import win32ui


APP_DIR = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
LOG_PATH = os.path.join(APP_DIR, "print-client.log")


def log(message):
    line = "%s %s\n" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), message)
    with open(LOG_PATH, "a") as fh:
        fh.write(line)


def load_config():
    with open(CONFIG_PATH, "r") as fh:
        config = json.load(fh)
    config["server_url"] = config["server_url"].rstrip("/")
    config.setdefault("client_id", "win7-usb-printer")
    config.setdefault("poll_seconds", 5)
    config.setdefault("font_name", "SimSun")
    config.setdefault("font_size", 9)
    config.setdefault("margin_mm", 3)
    config.setdefault("line_spacing", 1.28)
    config.setdefault("orientation", "feed")
    config.setdefault("rotation_degrees", 270)
    return config


def api_post(config, path, payload):
    url = config["server_url"] + path
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-Print-Client-Token": config["token"],
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def mm_to_px(mm_value, dpi):
    return int(mm_value * dpi / 25.4)


def create_font(config, dpi_y, rotation_degrees=0):
    return win32ui.CreateFont({
        "name": config["font_name"],
        "height": -int(config["font_size"] * dpi_y / 72),
        "weight": 400,
        "escapement": int(rotation_degrees * 10),
        "orientation": int(rotation_degrees * 10),
    })


def print_text_normal(dc, text, config, dpi_x, dpi_y, page_width, page_height):
    margin = mm_to_px(config["margin_mm"], dpi_x)
    y = margin
    line_height = int(config["font_size"] * dpi_y / 72 * float(config["line_spacing"]))
    font = create_font(config, dpi_y)

    dc.StartPage()
    dc.SelectObject(font)

    for line in text.splitlines():
        if y + line_height > page_height - margin:
            dc.EndPage()
            dc.StartPage()
            dc.SelectObject(font)
            y = margin
        dc.DrawText(
            line,
            (margin, y, page_width - margin, y + line_height),
            win32con.DT_LEFT | win32con.DT_TOP | win32con.DT_SINGLELINE,
        )
        y += line_height

    dc.EndPage()


def print_text_along_feed(dc, text, config, dpi_x, dpi_y, page_width):
    margin_x = mm_to_px(config["margin_mm"], dpi_x)
    margin_y = mm_to_px(config["margin_mm"], dpi_y)
    line_height = int(config["font_size"] * dpi_x / 72 * float(config["line_spacing"]))
    rotation = int(config.get("rotation_degrees", 270))
    font = create_font(config, dpi_y, rotation)

    def initial_x():
        return page_width - margin_x if rotation == 270 else margin_x

    def next_x(current_x):
        return current_x - line_height if rotation == 270 else current_x + line_height

    def reached_edge(current_x):
        if rotation == 270:
            return current_x < margin_x
        return current_x > page_width - margin_x

    x = initial_x()
    y = margin_y

    dc.StartPage()
    dc.SelectObject(font)

    for line in text.splitlines():
        if reached_edge(x):
            dc.EndPage()
            dc.StartPage()
            dc.SelectObject(font)
            x = initial_x()
        dc.TextOut(x, y, line)
        x = next_x(x)

    dc.EndPage()


def print_text_to_default_printer(text, title, config):
    printer_name = win32print.GetDefaultPrinter()
    dc = win32ui.CreateDC()
    dc.CreatePrinterDC(printer_name)

    dpi_x = dc.GetDeviceCaps(win32con.LOGPIXELSX)
    dpi_y = dc.GetDeviceCaps(win32con.LOGPIXELSY)
    page_width = dc.GetDeviceCaps(win32con.HORZRES)
    page_height = dc.GetDeviceCaps(win32con.VERTRES)

    dc.StartDoc(title)
    try:
        if str(config.get("orientation", "")).lower() in ("feed", "rotated", "landscape"):
            print_text_along_feed(dc, text, config, dpi_x, dpi_y, page_width)
        else:
            print_text_normal(dc, text, config, dpi_x, dpi_y, page_width, page_height)
    finally:
        dc.EndDoc()
        dc.DeleteDC()


def main():
    config = load_config()
    client_id = config["client_id"]
    log("client started: %s" % client_id)

    while True:
        try:
            response = api_post(config, "/api/print-client/next", {"client_id": client_id})
            if response.get("ok") and response.get("has_job"):
                job = response["job"]
                payload = response["payload"]
                title = "Order %s" % job.get("order_no", job["id"])

                try:
                    print_text_to_default_printer(payload["text"], title, config)
                except Exception as exc:
                    error = "%s\n%s" % (exc, traceback.format_exc())
                    api_post(
                        config,
                        "/api/print-client/report",
                        {
                            "client_id": client_id,
                            "job_id": job["id"],
                            "success": False,
                            "error": error,
                        },
                    )
                    log("print failed job=%s error=%s" % (job["id"], exc))
                else:
                    api_post(
                        config,
                        "/api/print-client/report",
                        {
                            "client_id": client_id,
                            "job_id": job["id"],
                            "success": True,
                        },
                    )
                    log("print ok job=%s order=%s" % (job["id"], job.get("order_no", "")))
            time.sleep(float(config["poll_seconds"]))
        except (urllib.error.URLError, urllib.error.HTTPError) as exc:
            log("server request failed: %s" % exc)
            time.sleep(float(config["poll_seconds"]))
        except Exception as exc:
            log("unexpected error: %s\n%s" % (exc, traceback.format_exc()))
            time.sleep(float(config["poll_seconds"]))


if __name__ == "__main__":
    main()
