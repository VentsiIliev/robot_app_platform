import cv2
import numpy as np


class Contour:
    def __init__(self, contour_points):        # np.array (not np.asarray) — forces a copy even when dtype already matches float32.
        # This ensures that in-place mutations (translate, scale, rotate) on this Contour
        # never propagate back to the source array (e.g. _latest_contours in VisionSystem).
        contour_points = np.array(contour_points, dtype=np.float32)
        if contour_points.ndim == 3 and contour_points.shape[1] == 1:
            contour_points = contour_points[:, 0, :]
        self.contour_points = contour_points.reshape(-1, 2)

    # --- Accessors ---
    def get(self):
        # Returns a copy — callers (update_workpiece_data, VisionService.run_matching,
        # MatchInfo, etc.) may freely mutate or store the result without corrupting
        # this Contour's internal float32 state.
        return self.contour_points.copy()

    def as_cv(self):
        # Returns a view — read-only use only (geometry queries, cv2 calls).
        # Cast to int32 at the call site if drawing is needed.
        return self.contour_points.reshape(-1, 1, 2)

    # --- Geometry and properties ---
    def getArea(self):
        return cv2.contourArea(self.as_cv())

    def getBbox(self):
        return cv2.boundingRect(self.as_cv())

    def getMinAreaRect(self):
        return cv2.minAreaRect(self.as_cv())

    def getMoments(self):
        return cv2.moments(self.as_cv())

    def getPerimeter(self):
        return cv2.arcLength(self.as_cv(), True)

    def getCentroid(self):
        M = self.getMoments()
        if M["m00"] == 0:
            x, y, w, h = self.getBbox()
            if w > 0 and h > 0:
                return (x + w / 2.0, y + h / 2.0)
            elif len(self.contour_points):
                return tuple(self.contour_points[0].tolist())
            else:
                return (0.0, 0.0)
        return (M["m10"] / M["m00"], M["m01"] / M["m00"])

    def getConvexHull(self):
        return cv2.convexHull(self.as_cv())

    def getOrientation(self):
        M = self.getMoments()
        if abs(M["mu20"]) < 1e-10:
            return 0
        angle = 0.5 * np.arctan2(2 * M["mu11"], M["mu20"] - M["mu02"])
        return np.degrees(angle)

    def getOrientationMinAreaRect(self) -> float:
        """Calculate orientation using minimum area bounding rectangle.
        
        This method is more stable than moments-based orientation, especially for:
        - Elongated shapes
        - Complex contours with smooth edges
        - Contours rotated 90 degrees or at arbitrary angles
        
        Returns orientation in degrees [0, 180).
        """
        rect = cv2.minAreaRect(self.as_cv())
        if rect == (0, 0, 0):
            return 0.0
        
        center, size, angle = rect
        if size[0] < 1 or size[1] < 1:
            return 0.0
        
        # minAreaRect returns angle in [-90, 0)
        # Convert to [0, 180) range
        # The angle is the rotation of the shorter side relative to horizontal
        angle = float(angle)
        if angle < 0:
            angle += 90.0
        else:
            angle = 90.0 + angle
        
        return angle % 180.0

    def getOrientationPCA(self) -> float:
        """Calculate orientation using Principal Component Analysis.
        
        This is the most robust method for complex shapes, using the
        eigenvector corresponding to the largest eigenvalue of the
        covariance matrix.
        
        Returns orientation in degrees [0, 180).
        """
        if len(self.contour_points) < 3:
            return 0.0
        
        # Compute centroid
        centroid = np.mean(self.contour_points, axis=0)
        
        # Center the points
        centered = self.contour_points - centroid
        
        # Compute covariance matrix
        cov = np.cov(centered.T)
        
        if cov.shape != (2, 2):
            return 0.0
        
        # Compute eigenvalues and eigenvectors
        eigenvalues, eigenvectors = np.linalg.eigh(cov)
        
        # Get the eigenvector corresponding to the largest eigenvalue
        largest_idx = np.argmax(eigenvalues)
        principal_axis = eigenvectors[:, largest_idx]
        
        # Compute angle from x-axis
        angle = np.degrees(np.arctan2(principal_axis[1], principal_axis[0]))
        
        # Normalize to [0, 180)
        return angle % 180.0

    def getOrientationRobust(self) -> float:
        """Get orientation using the most robust method available.
        
        Uses PCA as primary method, falls back to minAreaRect if PCA fails,
        and finally falls back to moments-based if both fail.
        
        Returns orientation in degrees [0, 180).
        """
        # Try PCA first - most robust for complex shapes
        pca_angle = self.getOrientationPCA()
        if pca_angle != 0.0:
            return pca_angle
        
        # Fall back to minAreaRect
        min_area_angle = self.getOrientationMinAreaRect()
        if min_area_angle != 0.0:
            return min_area_angle
        
        # Final fallback to moments
        return self.getOrientation()

    def getCentroidRobust(self) -> tuple[float, float]:
        """Calculate centroid using the most reliable method.
        
        Uses moments-based calculation with improved fallback handling
        for edge cases (degenerate contours, single points, etc.)
        """
        M = self.getMoments()
        m00 = float(M.get("m00", 0.0))
        
        if abs(m00) > 1e-10:
            # Standard moments calculation
            cx = float(M.get("m10", 0.0)) / m00
            cy = float(M.get("m01", 0.0)) / m00
            return (cx, cy)
        
        # Fallback 1: Use bounding box center
        x, y, w, h = self.getBbox()
        if w > 0 and h > 0:
            return (float(x + w / 2.0), float(y + h / 2.0))
        
        # Fallback 2: Use mean of all points
        if len(self.contour_points) > 0:
            return tuple(np.mean(self.contour_points, axis=0).tolist())
        
        # Fallback 3: Use first point
        if len(self.contour_points) > 0:
            return tuple(self.contour_points[0].tolist())
        
        return (0.0, 0.0)

    # --- Comparison ---
    def match(self, other):
        if isinstance(other, Contour):
            other = other.as_cv()
        return cv2.matchShapes(self.as_cv(), other, 1, 0.0)

    # --- Transformations ---
    def translate(self, dx, dy):
        self.contour_points += np.array([dx, dy], dtype=np.float32)

    def scale(self, factor):
        self.contour_points *= factor

    def rotate(self, angle_deg, pivot):
        angle_rad = np.radians(angle_deg)
        cos_a, sin_a = np.cos(angle_rad), np.sin(angle_rad)
        p = np.asarray(pivot, dtype=np.float32)
        pts = self.contour_points - p
        R = np.array([[cos_a, -sin_a], [sin_a, cos_a]], dtype=np.float32)
        self.contour_points = pts @ R.T + p

    def simplify(self, epsilon_factor=0.01):
        peri = self.getPerimeter()
        epsilon = epsilon_factor * peri
        simplified = cv2.approxPolyDP(self.as_cv(), epsilon, True)
        self.contour_points = simplified.reshape(-1, 2).astype(np.float32)
        return self.contour_points

    # --- Convexity ---
    def getConvexityDefects(self):
        contour = self.as_cv().astype(np.int32)
        hull = cv2.convexHull(contour, returnPoints=False)
        if hull is None or len(hull) < 3:
            return False, None
        defects = cv2.convexityDefects(contour, hull)
        return (defects is not None), defects

    # --- Morphological shrinking ---
    def shrink(self, offset_x, offset_y):
        x, y, w, h = self.getBbox()
        mask = np.zeros((h + 2 * offset_y, w + 2 * offset_x), dtype=np.uint8)
        shifted = self.contour_points - [x - offset_x, y - offset_y]
        cv2.fillPoly(mask, [shifted.astype(np.int32)], 255)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2 * offset_x, 2 * offset_y))
        eroded = cv2.erode(mask, kernel, iterations=1)
        contours, _ = cv2.findContours(eroded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            new_c = contours[0].reshape(-1, 2) + [x - offset_x, y - offset_y]
            self.contour_points = new_c.astype(np.float32)

    # --- Drawing ---
    def draw(self, frame, color=(0, 255, 0), thickness=2):
        cv2.drawContours(frame, [self.as_cv().astype(np.int32)], -1, color, thickness)






if __name__ == "__main__":
    import cv2
    import numpy as np


    # --- Helper function ---
    def ttest_contour(name, pts):
        print(f"\n🟢 Testing: {name}")
        c = Contour(pts)
        print("  shape:", c.get().shape, "| dtype:", c.get().dtype)
        print("  area:", round(c.getArea(), 2))
        print("  centroid:", c.getCentroid())
        print("  orientation:", round(c.getOrientation(), 2))
        return c


    # --- 1️⃣ Simple rectangle as list of tuples (unordered) ---
    rect_pts = [(10, 10), (110, 10), (110, 60), (10, 60)]
    ttest_contour("Rectangle (list of tuples)", rect_pts)

    # --- 2️⃣ NumPy array (N,2) shape ---
    np_rect = np.array(rect_pts, dtype=np.float32)
    ttest_contour("Rectangle (numpy (N,2))", np_rect)

    # --- 3️⃣ OpenCV contour format (N,1,2) ---
    cv_rect = np_rect.reshape(-1, 1, 2)
    ttest_contour("Rectangle (OpenCV (N,1,2))", cv_rect)

    # --- 4️⃣ Irregular polygon ---
    poly_pts = np.array([[50, 50], [150, 70], [130, 150], [70, 130]], dtype=np.float32)
    ttest_contour("Polygon", poly_pts)

    # --- 5️⃣ Circle (approximated using cv2.ellipse2Poly) ---
    circle_pts = cv2.ellipse2Poly((100, 100), (50, 50), 0, 0, 360, 15)
    ttest_contour("Circle (ellipse2Poly)", circle_pts)

    # --- 6️⃣ Star shape (non-convex polygon) ---
    star_pts = np.array([[100, 20], [120, 80], [180, 80], [130, 120],
                         [150, 180], [100, 140], [50, 180], [70, 120],
                         [20, 80], [80, 80]], dtype=np.float32)
    ttest_contour("Star shape", star_pts)

    # --- 7️⃣ Random noisy points (simulate raw contour from cv2.findContours) ---
    random_pts = (np.random.rand(10, 1, 2) * 100).astype(np.float32)
    ttest_contour("Random (N,1,2)", random_pts)

    # --- 8️⃣ Degenerate: Single point ---
    single_pt = np.array([[50, 50]], dtype=np.float32)
    ttest_contour("Single point", single_pt)

    # --- 9️⃣ Degenerate: Empty contour ---
    empty = np.empty((0, 2), dtype=np.float32)
    ttest_contour("Empty contour", empty)