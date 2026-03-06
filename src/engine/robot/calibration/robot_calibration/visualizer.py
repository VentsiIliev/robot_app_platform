import cv2


def draw_progress_bar(frame,progress):
    # Draw progress bar
    cv2.rectangle(frame, (10, frame.shape[0] - 50), (int(10 + progress * 3), frame.shape[0] - 30), (0, 255, 0), -1)
    cv2.rectangle(frame, (10, frame.shape[0] - 50), (310, frame.shape[0] - 30), (255, 255, 255), 2)

def draw_status_text(frame,status_text):
    y_offset = 30
    line_height = 25
    # Current state
    cv2.putText(frame, f"State: {status_text}", (10, y_offset),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    y_offset += line_height

def draw_current_marker_info(frame,current_marker, current_marker_id, required_ids_list):
    y_offset = 30
    line_height = 25
    cv2.putText(frame, f"Marker: {current_marker} ({current_marker_id + 1}/{len(required_ids_list)})",
                (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    y_offset += line_height

def draw_iteration_info(frame,iteration_count, max_iterations):
    y_offset = 30
    line_height = 25
    cv2.putText(frame, f"Iteration: {iteration_count}/{max_iterations}",
                (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
    y_offset += line_height

def draw_current_error_mm(frame,current_error_mm, alignment_threshold_mm):
    y_offset = 30
    line_height = 25
    error_color = (0, 255, 0) if current_error_mm <= alignment_threshold_mm else (0, 0, 255)
    cv2.putText(frame, f"Error: {current_error_mm:.3f}mm",
                (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, error_color, 2)
    y_offset += line_height

def draw_progress_text(frame,progress):
    cv2.putText(frame, f"Progress: {progress:.0f}%",
                (10, frame.shape[0] - 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
