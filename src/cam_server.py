from flask import Flask, Response, request
import atexit
import cv2
import threading
import time

from src.engine.vision.implementation.plvision.PLVision.Camera import Camera

cam_lock = threading.Lock()
frame_lock = threading.Lock()
frame_ready = threading.Condition(frame_lock)


cam = Camera(cameraIndex=0, width=1280, height=720, fps=30)
cam.set_auto_exposure(True)


if not cam.isOpened():
 raise RuntimeError("Failed to open camera")




latest_jpeg = None
latest_frame_id = 0
capture_running = True




def _camera_loop():
 global latest_jpeg, latest_frame_id


 consecutive_failures = 0


 while capture_running:
     with cam_lock:
         frame = cam.capture(timeout=0.25)


     if frame is None:
         consecutive_failures += 1


         if consecutive_failures >= 4:
             with cam_lock:
                 try:
                     cam.stop_stream()
                 except Exception:
                     pass
             time.sleep(0.2)
             with cam_lock:
                 try:
                     cam.start_stream()
                 except Exception:
                     pass
             consecutive_failures = 0


         time.sleep(0.01)
         continue


     consecutive_failures = 0


     ok, buffer = cv2.imencode(".jpg", frame)
     if not ok:
         time.sleep(0.005)
         continue


     jpeg = buffer.tobytes()


     with frame_ready:
         latest_jpeg = jpeg
         latest_frame_id += 1
         frame_ready.notify_all()




capture_thread = threading.Thread(target=_camera_loop, daemon=True)
capture_thread.start()




app = Flask(__name__)




def generate_frames():
 last_sent_id = -1


 while True:
     with frame_ready:
         while latest_frame_id == last_sent_id:
             frame_ready.wait(timeout=1.0)


         jpeg = latest_jpeg
         frame_id = latest_frame_id


     if jpeg is None:
         continue


     last_sent_id = frame_id


     yield (
         b"--frame\r\n"
         b"Content-Type: image/jpeg\r\n"
         + f"Content-Length: {len(jpeg)}\r\n\r\n".encode("ascii")
         + jpeg
         + b"\r\n"
     )




@app.route("/video_feed")
def video_feed():
 return Response(
     generate_frames(),
     mimetype="multipart/x-mixed-replace; boundary=frame",
     headers={
         "Cache-Control": "no-cache, no-store, must-revalidate",
         "Pragma": "no-cache",
         "Expires": "0",
         "Connection": "close",
     },
 )




@app.route("/")
def index():
 return '<h1>Camera Live Stream</h1><img src="/video_feed" width="640" height="480">'




@app.route("/set_auto_exposure")
def set_auto_exposure():
 value = request.args.get("value", "").lower()


 with cam_lock:
     if value in ["true", "1", "on"]:
         cam.set_auto_exposure(True)
         return {"auto_exposure": True}


     if value in ["false", "0", "off"]:
         cam.set_auto_exposure(False)
         return {"auto_exposure": False}


 return {"error": "invalid value"}, 400




@atexit.register
def cleanup():
 global capture_running
 capture_running = False
 try:
     capture_thread.join(timeout=1.0)
 except Exception:
     pass
 with cam_lock:
     try:
         cam.close()
     except Exception:
         pass




if __name__ == "__main__":
 app.run(host="0.0.0.0", port=5000, threaded=True, use_reloader=False)


# RUN WITH cd src && ../.venv/bin/gunicorn -w 1 -k gevent --threads 1 -b 0.0.0.0:5000 cam_server:app




# • From the server project directory, run:
#
#   gunicorn -w 1 -k gevent --threads 1 -b 0.0.0.0:5000 cam_server:app
#
#   I
#   - run with -w 1 because the camera object should not be duplicated across multiple worker processes
#   - gevent is better than Flask dev server for long-lived MJPEG streaming
#
#   If you want, I can also give you a small systemd service file for it.



