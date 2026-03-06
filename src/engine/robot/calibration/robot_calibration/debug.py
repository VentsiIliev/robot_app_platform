import cv2


class DebugDraw:
    def __init__(self):
        # drawing settings
        self.marker_color = (0, 255, 0)  # Green
        self.marker_radius = 6
        self.text_color = (0, 255, 0)  # Green
        self.text_scale = 0.7
        self.text_thickness = 2
        self.text_font = cv2.FONT_HERSHEY_SIMPLEX
        self.text_offset = 10  # Offset for text position relative to marker top-left corner
        self.text_position = (self.marker_radius + self.text_offset, self.marker_radius + self.text_offset)
        self.image_center_color = (255, 0, 0)  # Blue
        self.image_center_radius = 4
        self.circle_thickness = -1

    def draw_marker_top_left_corner(self, frame, marker_id, marker_corners):
        """Draw marker top-left corner on frame"""
        if marker_id in marker_corners:
            top_left_px = marker_corners[marker_id]
            cv2.circle(frame, top_left_px, self.marker_radius, self.marker_color, self.circle_thickness)
            cv2.putText(frame, f"ID {marker_id}", (top_left_px[0] + self.text_offset, top_left_px[1]),
                        self.text_font, self.text_scale, self.text_color, self.text_thickness)
            return True
        return False

    def draw_image_center(self, frame):
        """Draw crosshair at image center"""
        frame_height, frame_width = frame.shape[:2]
        center_x, center_y = frame_width // 2, frame_height // 2

        # Color and thickness
        color = getattr(self, "image_center_color", (0, 255, 0))  # default green
        thickness = 1  # thinner than 12 so it looks clean

        # Draw horizontal line across the frame
        cv2.line(frame, (0, center_y), (frame_width, center_y), color, thickness)

        # Draw vertical line across the frame
        cv2.line(frame, (center_x, 0), (center_x, frame_height), color, thickness)

        # Optional: draw small circle at center (for reference)
        cv2.circle(frame, (center_x, center_y), 2, color, -1)