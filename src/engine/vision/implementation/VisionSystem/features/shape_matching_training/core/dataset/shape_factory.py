"""
Shape Factory Module

Provides a factory pattern for generating various geometric shapes with
consistent interfaces and extensible architecture for adding new shapes.
"""

import cv2
import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Any, Type, Optional
from enum import Enum


class ShapeType(Enum):
    """Enumeration of available shape types"""
    # Basic geometric shapes
    CIRCLE = "circle"
    ELLIPSE = "ellipse"
    RECTANGLE = "rectangle"
    SQUARE = "square"
    TRIANGLE = "triangle"
    DIAMOND = "diamond"
    HEXAGON = "hexagon"
    OCTAGON = "octagon"
    PENTAGON = "pentagon"
    
    # Hard negatives - similar but different shapes
    OVAL = "oval"
    ROUNDED_RECT = "rounded_rect"
    ROUNDED_CORNER_RECT = "rounded_corner_rect"
    
    # Special shapes
    S_SHAPE = "s_shape"
    C_SHAPE = "c_shape"
    T_SHAPE = "t_shape"
    U_SHAPE = "u_shape"
    L_SHAPE = "l_shape"
    
    # Complex shapes
    STAR = "star"
    CROSS = "cross"
    ARROW = "arrow"
    HEART = "heart"
    CRESCENT = "crescent"
    
    # Industrial/mechanical shapes
    GEAR = "gear"
    DONUT = "donut"
    TRAPEZOID = "trapezoid"
    PARALLELOGRAM = "parallelogram"
    HOURGLASS = "hourglass"
    LIGHTNING = "lightning"


class BaseShapeGenerator(ABC):
    """
    Abstract base class for shape generators
    """
    
    def __init__(self, shape_type: ShapeType):
        self.shape_type = shape_type
    
    @abstractmethod
    def generate(self, 
                scale: float = 1.0, 
                img_size: Tuple[int, int] = (256, 256),
                **kwargs) -> np.ndarray:
        """
        Generate a contour for this shape
        
        Args:
            scale: Scale factor for the shape
            img_size: Size of the image canvas
            **kwargs: Additional shape-specific parameters
            
        Returns:
            OpenCV contour array
        """
        pass
    
    @abstractmethod
    def get_default_parameters(self) -> Dict[str, Any]:
        """
        Get default parameters for this shape
        
        Returns:
            Dictionary of default parameters
        """
        pass
    
    def validate_parameters(self, **kwargs) -> Dict[str, Any]:
        """
        Validate and merge parameters with defaults
        
        Args:
            **kwargs: Parameters to validate
            
        Returns:
            Validated parameter dictionary
        """
        defaults = self.get_default_parameters()
        defaults.update(kwargs)
        return defaults


class CircleGenerator(BaseShapeGenerator):
    """Generator for circular shapes"""
    
    def __init__(self):
        super().__init__(ShapeType.CIRCLE)
    
    def generate(self, scale: float = 1.0, img_size: Tuple[int, int] = (256, 256), **kwargs) -> np.ndarray:
        """Generate circle contour"""
        params = self.validate_parameters(**kwargs)
        
        img = np.zeros(img_size, dtype=np.uint8)
        h, w = img_size
        cx, cy = w // 2, h // 2
        radius = int(params['base_size'] * min(scale, 2.0))
        
        cv2.circle(img, (cx, cy), radius, 255, -1)
        contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        return contours[0] if contours else np.array([[[cx, cy]]], dtype=np.int32)
    
    def get_default_parameters(self) -> Dict[str, Any]:
        return {'base_size': 50}


class EllipseGenerator(BaseShapeGenerator):
    """Generator for elliptical shapes"""
    
    def __init__(self):
        super().__init__(ShapeType.ELLIPSE)
    
    def generate(self, scale: float = 1.0, img_size: Tuple[int, int] = (256, 256), **kwargs) -> np.ndarray:
        """Generate ellipse contour"""
        params = self.validate_parameters(**kwargs)
        
        img = np.zeros(img_size, dtype=np.uint8)
        h, w = img_size
        cx, cy = w // 2, h // 2
        base = int(params['base_size'] * min(scale, 2.0))
        
        axes = (base, int(base * params['aspect_ratio']))
        cv2.ellipse(img, (cx, cy), axes, 0, 0, 360, 255, -1)
        
        contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours[0] if contours else np.array([[[cx, cy]]], dtype=np.int32)
    
    def get_default_parameters(self) -> Dict[str, Any]:
        return {'base_size': 50, 'aspect_ratio': 0.6}


class RectangleGenerator(BaseShapeGenerator):
    """Generator for rectangular shapes"""
    
    def __init__(self):
        super().__init__(ShapeType.RECTANGLE)
    
    def generate(self, scale: float = 1.0, img_size: Tuple[int, int] = (256, 256), **kwargs) -> np.ndarray:
        """Generate rectangle contour"""
        params = self.validate_parameters(**kwargs)
        
        img = np.zeros(img_size, dtype=np.uint8)
        h, w = img_size
        cx, cy = w // 2, h // 2
        base = int(params['base_size'] * min(scale, 2.0))
        
        width = int(base * params['width_ratio'])
        height = int(base * params['height_ratio'])
        
        cv2.rectangle(img, (cx - width, cy - height), (cx + width, cy + height), 255, -1)
        
        contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours[0] if contours else np.array([[[cx, cy]]], dtype=np.int32)
    
    def get_default_parameters(self) -> Dict[str, Any]:
        return {'base_size': 50, 'width_ratio': 1.0, 'height_ratio': 1.0}


class PolygonGenerator(BaseShapeGenerator):
    """Generator for regular polygon shapes"""
    
    def __init__(self, shape_type: ShapeType, n_sides: int):
        super().__init__(shape_type)
        self.n_sides = n_sides
    
    def generate(self, scale: float = 1.0, img_size: Tuple[int, int] = (256, 256), **kwargs) -> np.ndarray:
        """Generate regular polygon contour"""
        params = self.validate_parameters(**kwargs)
        
        img = np.zeros(img_size, dtype=np.uint8)
        h, w = img_size
        cx, cy = w // 2, h // 2
        radius = int(params['base_size'] * min(scale, 2.0))
        
        # Generate polygon vertices
        angles = np.linspace(0, 2 * np.pi, self.n_sides, endpoint=False)
        points = []
        
        for angle in angles:
            x = cx + int(radius * np.cos(angle))
            y = cy + int(radius * np.sin(angle))
            points.append([x, y])
        
        points = np.array(points, dtype=np.int32)
        cv2.fillPoly(img, [points], 255)
        
        contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours[0] if contours else points.reshape(-1, 1, 2)
    
    def get_default_parameters(self) -> Dict[str, Any]:
        return {'base_size': 50}


class StarGenerator(BaseShapeGenerator):
    """Generator for star shapes"""
    
    def __init__(self, n_points: int = 5):
        super().__init__(ShapeType.STAR)
        self.n_points = n_points
    
    def generate(self, scale: float = 1.0, img_size: Tuple[int, int] = (256, 256), **kwargs) -> np.ndarray:
        """Generate star contour"""
        params = self.validate_parameters(**kwargs)
        
        img = np.zeros(img_size, dtype=np.uint8)
        h, w = img_size
        cx, cy = w // 2, h // 2
        outer_radius = int(params['base_size'] * min(scale, 2.0))
        inner_radius = int(outer_radius * params['inner_ratio'])
        
        points = []
        for i in range(self.n_points * 2):
            angle = i * np.pi / self.n_points
            if i % 2 == 0:
                # Outer point
                radius = outer_radius
            else:
                # Inner point
                radius = inner_radius
            
            x = cx + int(radius * np.cos(angle))
            y = cy + int(radius * np.sin(angle))
            points.append([x, y])
        
        points = np.array(points, dtype=np.int32)
        cv2.fillPoly(img, [points], 255)
        
        contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours[0] if contours else points.reshape(-1, 1, 2)
    
    def get_default_parameters(self) -> Dict[str, Any]:
        return {'base_size': 50, 'inner_ratio': 0.5}


class HeartGenerator(BaseShapeGenerator):
    """Generator for heart shapes using parametric equations"""
    
    def __init__(self):
        super().__init__(ShapeType.HEART)
    
    def generate(self, scale: float = 1.0, img_size: Tuple[int, int] = (256, 256), **kwargs) -> np.ndarray:
        """Generate heart contour using parametric equations"""
        params = self.validate_parameters(**kwargs)
        
        img = np.zeros(img_size, dtype=np.uint8)
        h, w = img_size
        cx, cy = w // 2, h // 2
        base = int(params['base_size'] * min(scale, 2.0))
        
        # Parametric heart equation
        t = np.linspace(0, 2 * np.pi, params['n_points'])
        
        # Heart equation: x = 16sin³(t), y = 13cos(t) - 5cos(2t) - 2cos(3t) - cos(4t)
        x = 16 * np.sin(t) ** 3
        y = 13 * np.cos(t) - 5 * np.cos(2*t) - 2 * np.cos(3*t) - np.cos(4*t)
        
        # Scale and center
        x = x * base / 20 + cx
        y = -y * base / 20 + cy  # Flip y-axis
        
        points = np.array(list(zip(x.astype(int), y.astype(int))), dtype=np.int32)
        cv2.fillPoly(img, [points], 255)
        
        contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours[0] if contours else points.reshape(-1, 1, 2)
    
    def get_default_parameters(self) -> Dict[str, Any]:
        return {'base_size': 50, 'n_points': 100}


class OvalGenerator(BaseShapeGenerator):
    """Generator for oval shapes (elongated ellipse)"""

    def __init__(self):
        super().__init__(ShapeType.OVAL)

    def generate(self, scale: float = 1.0, img_size: Tuple[int, int] = (256, 256), **kwargs) -> np.ndarray:
        """Generate oval contour"""
        params = self.validate_parameters(**kwargs)

        img = np.zeros(img_size, dtype=np.uint8)
        h, w = img_size
        cx, cy = w // 2, h // 2
        base = int(params['base_size'] * min(scale, 2.0))

        # Oval has a more extreme aspect ratio than ellipse
        axes = (base, int(base * params['aspect_ratio']))
        cv2.ellipse(img, (cx, cy), axes, 0, 0, 360, 255, -1)

        contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours[0] if contours else np.array([[[cx, cy]]], dtype=np.int32)

    def get_default_parameters(self) -> Dict[str, Any]:
        return {'base_size': 50, 'aspect_ratio': 0.4}  # More elongated than ellipse


class RoundedRectGenerator(BaseShapeGenerator):
    """Generator for rounded rectangle shapes"""

    def __init__(self):
        super().__init__(ShapeType.ROUNDED_RECT)

    def generate(self, scale: float = 1.0, img_size: Tuple[int, int] = (256, 256), **kwargs) -> np.ndarray:
        """Generate rounded rectangle contour"""
        params = self.validate_parameters(**kwargs)

        img = np.zeros(img_size, dtype=np.uint8)
        h, w = img_size
        cx, cy = w // 2, h // 2
        base = int(params['base_size'] * min(scale, 2.0))

        width = int(base * params['width_ratio'])
        height = int(base * params['height_ratio'])
        radius = int(min(width, height) * params['corner_radius'])

        # Draw rounded rectangle using ellipses for corners
        x1, y1 = cx - width, cy - height
        x2, y2 = cx + width, cy + height

        # Main rectangle
        cv2.rectangle(img, (x1 + radius, y1), (x2 - radius, y2), 255, -1)
        cv2.rectangle(img, (x1, y1 + radius), (x2, y2 - radius), 255, -1)

        # Corners
        cv2.circle(img, (x1 + radius, y1 + radius), radius, 255, -1)
        cv2.circle(img, (x2 - radius, y1 + radius), radius, 255, -1)
        cv2.circle(img, (x1 + radius, y2 - radius), radius, 255, -1)
        cv2.circle(img, (x2 - radius, y2 - radius), radius, 255, -1)

        contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours[0] if contours else np.array([[[cx, cy]]], dtype=np.int32)

    def get_default_parameters(self) -> Dict[str, Any]:
        return {'base_size': 50, 'width_ratio': 1.0, 'height_ratio': 1.0, 'corner_radius': 0.3}


class RoundedCornerRectGenerator(BaseShapeGenerator):
    """Generator for rectangle with rounded corners (less rounded than RoundedRect)"""

    def __init__(self):
        super().__init__(ShapeType.ROUNDED_CORNER_RECT)

    def generate(self, scale: float = 1.0, img_size: Tuple[int, int] = (256, 256), **kwargs) -> np.ndarray:
        """Generate rounded corner rectangle contour"""
        params = self.validate_parameters(**kwargs)

        img = np.zeros(img_size, dtype=np.uint8)
        h, w = img_size
        cx, cy = w // 2, h // 2
        base = int(params['base_size'] * min(scale, 2.0))

        width = int(base * params['width_ratio'])
        height = int(base * params['height_ratio'])
        radius = int(min(width, height) * params['corner_radius'])

        x1, y1 = cx - width, cy - height
        x2, y2 = cx + width, cy + height

        # Main rectangle
        cv2.rectangle(img, (x1 + radius, y1), (x2 - radius, y2), 255, -1)
        cv2.rectangle(img, (x1, y1 + radius), (x2, y2 - radius), 255, -1)

        # Corners
        cv2.circle(img, (x1 + radius, y1 + radius), radius, 255, -1)
        cv2.circle(img, (x2 - radius, y1 + radius), radius, 255, -1)
        cv2.circle(img, (x1 + radius, y2 - radius), radius, 255, -1)
        cv2.circle(img, (x2 - radius, y2 - radius), radius, 255, -1)

        contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours[0] if contours else np.array([[[cx, cy]]], dtype=np.int32)

    def get_default_parameters(self) -> Dict[str, Any]:
        return {'base_size': 50, 'width_ratio': 1.0, 'height_ratio': 1.0, 'corner_radius': 0.15}


class CrossGenerator(BaseShapeGenerator):
    """Generator for cross/plus shapes"""

    def __init__(self):
        super().__init__(ShapeType.CROSS)

    def generate(self, scale: float = 1.0, img_size: Tuple[int, int] = (256, 256), **kwargs) -> np.ndarray:
        """Generate cross contour"""
        params = self.validate_parameters(**kwargs)

        img = np.zeros(img_size, dtype=np.uint8)
        h, w = img_size
        cx, cy = w // 2, h // 2
        base = int(params['base_size'] * min(scale, 2.0))
        thickness = int(base * params['thickness_ratio'])

        # Vertical bar
        cv2.rectangle(img, (cx - thickness, cy - base), (cx + thickness, cy + base), 255, -1)
        # Horizontal bar
        cv2.rectangle(img, (cx - base, cy - thickness), (cx + base, cy + thickness), 255, -1)

        contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours[0] if contours else np.array([[[cx, cy]]], dtype=np.int32)

    def get_default_parameters(self) -> Dict[str, Any]:
        return {'base_size': 50, 'thickness_ratio': 0.3}


class ArrowGenerator(BaseShapeGenerator):
    """Generator for arrow shapes"""

    def __init__(self):
        super().__init__(ShapeType.ARROW)

    def generate(self, scale: float = 1.0, img_size: Tuple[int, int] = (256, 256), **kwargs) -> np.ndarray:
        """Generate arrow contour"""
        params = self.validate_parameters(**kwargs)

        img = np.zeros(img_size, dtype=np.uint8)
        h, w = img_size
        cx, cy = w // 2, h // 2
        base = int(params['base_size'] * min(scale, 2.0))

        # Arrow pointing right
        head_width = base
        head_height = int(base * params['head_ratio'])
        shaft_width = int(base * params['shaft_ratio'])

        points = np.array([
            [cx + head_width, cy],  # Arrow tip
            [cx, cy - head_height],  # Top of head
            [cx, cy - shaft_width],  # Top of shaft
            [cx - base, cy - shaft_width],  # Top left
            [cx - base, cy + shaft_width],  # Bottom left
            [cx, cy + shaft_width],  # Bottom of shaft
            [cx, cy + head_height],  # Bottom of head
        ], dtype=np.int32)

        cv2.fillPoly(img, [points], 255)

        contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours[0] if contours else points.reshape(-1, 1, 2)

    def get_default_parameters(self) -> Dict[str, Any]:
        return {'base_size': 50, 'head_ratio': 0.8, 'shaft_ratio': 0.3}


class TrapezoidGenerator(BaseShapeGenerator):
    """Generator for trapezoid shapes"""

    def __init__(self):
        super().__init__(ShapeType.TRAPEZOID)

    def generate(self, scale: float = 1.0, img_size: Tuple[int, int] = (256, 256), **kwargs) -> np.ndarray:
        """Generate trapezoid contour"""
        params = self.validate_parameters(**kwargs)

        img = np.zeros(img_size, dtype=np.uint8)
        h, w = img_size
        cx, cy = w // 2, h // 2
        base = int(params['base_size'] * min(scale, 2.0))

        top_width = int(base * params['top_ratio'])
        bottom_width = base
        height = int(base * params['height_ratio'])

        points = np.array([
            [cx - top_width, cy - height],
            [cx + top_width, cy - height],
            [cx + bottom_width, cy + height],
            [cx - bottom_width, cy + height],
        ], dtype=np.int32)

        cv2.fillPoly(img, [points], 255)

        contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours[0] if contours else points.reshape(-1, 1, 2)

    def get_default_parameters(self) -> Dict[str, Any]:
        return {'base_size': 50, 'top_ratio': 0.6, 'height_ratio': 0.8}


class ParallelogramGenerator(BaseShapeGenerator):
    """Generator for parallelogram shapes"""

    def __init__(self):
        super().__init__(ShapeType.PARALLELOGRAM)

    def generate(self, scale: float = 1.0, img_size: Tuple[int, int] = (256, 256), **kwargs) -> np.ndarray:
        """Generate parallelogram contour"""
        params = self.validate_parameters(**kwargs)

        img = np.zeros(img_size, dtype=np.uint8)
        h, w = img_size
        cx, cy = w // 2, h // 2
        base = int(params['base_size'] * min(scale, 2.0))

        width = base
        height = int(base * params['height_ratio'])
        skew = int(base * params['skew_ratio'])

        points = np.array([
            [cx - width + skew, cy - height],
            [cx + width + skew, cy - height],
            [cx + width - skew, cy + height],
            [cx - width - skew, cy + height],
        ], dtype=np.int32)

        cv2.fillPoly(img, [points], 255)

        contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours[0] if contours else points.reshape(-1, 1, 2)

    def get_default_parameters(self) -> Dict[str, Any]:
        return {'base_size': 50, 'height_ratio': 0.7, 'skew_ratio': 0.3}


class CrescentGenerator(BaseShapeGenerator):
    """Generator for crescent moon shapes"""

    def __init__(self):
        super().__init__(ShapeType.CRESCENT)

    def generate(self, scale: float = 1.0, img_size: Tuple[int, int] = (256, 256), **kwargs) -> np.ndarray:
        """Generate crescent contour"""
        params = self.validate_parameters(**kwargs)

        img = np.zeros(img_size, dtype=np.uint8)
        h, w = img_size
        cx, cy = w // 2, h // 2
        outer_radius = int(params['base_size'] * min(scale, 2.0))
        inner_radius = int(outer_radius * params['inner_ratio'])
        offset = int(outer_radius * params['offset_ratio'])

        # Draw outer circle
        cv2.circle(img, (cx, cy), outer_radius, 255, -1)
        # Subtract inner circle (offset to create crescent)
        cv2.circle(img, (cx + offset, cy), inner_radius, 0, -1)

        contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours[0] if contours else np.array([[[cx, cy]]], dtype=np.int32)

    def get_default_parameters(self) -> Dict[str, Any]:
        return {'base_size': 50, 'inner_ratio': 0.8, 'offset_ratio': 0.4}


class DonutGenerator(BaseShapeGenerator):
    """Generator for donut/ring shapes"""

    def __init__(self):
        super().__init__(ShapeType.DONUT)

    def generate(self, scale: float = 1.0, img_size: Tuple[int, int] = (256, 256), **kwargs) -> np.ndarray:
        """Generate donut contour"""
        params = self.validate_parameters(**kwargs)

        img = np.zeros(img_size, dtype=np.uint8)
        h, w = img_size
        cx, cy = w // 2, h // 2
        outer_radius = int(params['base_size'] * min(scale, 2.0))
        inner_radius = int(outer_radius * params['hole_ratio'])

        # Draw outer circle
        cv2.circle(img, (cx, cy), outer_radius, 255, -1)
        # Subtract inner circle
        cv2.circle(img, (cx, cy), inner_radius, 0, -1)

        contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours[0] if contours else np.array([[[cx, cy]]], dtype=np.int32)

    def get_default_parameters(self) -> Dict[str, Any]:
        return {'base_size': 50, 'hole_ratio': 0.5}


class LetterShapeGenerator(BaseShapeGenerator):
    """Generator for letter-shaped contours (T, U, L, S, C)"""

    def __init__(self, shape_type: ShapeType):
        super().__init__(shape_type)

    def generate(self, scale: float = 1.0, img_size: Tuple[int, int] = (256, 256), **kwargs) -> np.ndarray:
        """Generate letter-shaped contour"""
        params = self.validate_parameters(**kwargs)

        img = np.zeros(img_size, dtype=np.uint8)
        h, w = img_size
        cx, cy = w // 2, h // 2
        base = int(params['base_size'] * min(scale, 2.0))
        thickness = int(base * params['thickness_ratio'])

        if self.shape_type == ShapeType.T_SHAPE:
            # T shape: horizontal top bar + vertical stem
            cv2.rectangle(img, (cx - base, cy - base), (cx + base, cy - base + thickness), 255, -1)
            cv2.rectangle(img, (cx - thickness, cy - base), (cx + thickness, cy + base), 255, -1)

        elif self.shape_type == ShapeType.U_SHAPE:
            # U shape: two vertical bars + bottom bar
            cv2.rectangle(img, (cx - base, cy - base), (cx - base + thickness, cy + base), 255, -1)
            cv2.rectangle(img, (cx + base - thickness, cy - base), (cx + base, cy + base), 255, -1)
            cv2.rectangle(img, (cx - base, cy + base - thickness), (cx + base, cy + base), 255, -1)

        elif self.shape_type == ShapeType.L_SHAPE:
            # L shape: vertical bar + horizontal bottom bar
            cv2.rectangle(img, (cx - base, cy - base), (cx - base + thickness, cy + base), 255, -1)
            cv2.rectangle(img, (cx - base, cy + base - thickness), (cx + base, cy + base), 255, -1)

        elif self.shape_type == ShapeType.C_SHAPE:
            # C shape: circle with a gap on the right
            cv2.circle(img, (cx, cy), base, 255, thickness)
            # Remove right section
            cv2.rectangle(img, (cx, cy - base // 2), (cx + base + 10, cy + base // 2), 0, -1)

        elif self.shape_type == ShapeType.S_SHAPE:
            # S shape: two curves
            # Top curve
            cv2.ellipse(img, (cx, cy - base // 2), (base // 2, base // 2), 0, 180, 0, 255, thickness)
            # Bottom curve
            cv2.ellipse(img, (cx, cy + base // 2), (base // 2, base // 2), 0, 0, 180, 255, thickness)
            # Middle connection
            cv2.rectangle(img, (cx - thickness // 2, cy - base // 2), (cx + thickness // 2, cy + base // 2), 255, -1)

        contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours[0] if contours else np.array([[[cx, cy]]], dtype=np.int32)

    def get_default_parameters(self) -> Dict[str, Any]:
        return {'base_size': 50, 'thickness_ratio': 0.2}


class GearGenerator(BaseShapeGenerator):
    """Generator for gear shapes"""

    def __init__(self):
        super().__init__(ShapeType.GEAR)

    def generate(self, scale: float = 1.0, img_size: Tuple[int, int] = (256, 256), **kwargs) -> np.ndarray:
        """Generate gear contour"""
        params = self.validate_parameters(**kwargs)

        img = np.zeros(img_size, dtype=np.uint8)
        h, w = img_size
        cx, cy = w // 2, h // 2
        outer_radius = int(params['base_size'] * min(scale, 2.0))
        inner_radius = int(outer_radius * params['inner_ratio'])
        tooth_height = int(outer_radius * params['tooth_ratio'])
        n_teeth = params['n_teeth']

        points = []
        for i in range(n_teeth * 2):
            angle = i * np.pi / n_teeth
            if i % 2 == 0:
                # Tooth tip
                radius = outer_radius + tooth_height
            else:
                # Tooth valley
                radius = outer_radius

            x = cx + int(radius * np.cos(angle))
            y = cy + int(radius * np.sin(angle))
            points.append([x, y])

        points = np.array(points, dtype=np.int32)
        cv2.fillPoly(img, [points], 255)

        # Add center hole
        cv2.circle(img, (cx, cy), inner_radius, 0, -1)

        contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours[0] if contours else points.reshape(-1, 1, 2)

    def get_default_parameters(self) -> Dict[str, Any]:
        return {'base_size': 50, 'inner_ratio': 0.3, 'tooth_ratio': 0.2, 'n_teeth': 8}


class HourglassGenerator(BaseShapeGenerator):
    """Generator for hourglass shapes"""

    def __init__(self):
        super().__init__(ShapeType.HOURGLASS)

    def generate(self, scale: float = 1.0, img_size: Tuple[int, int] = (256, 256), **kwargs) -> np.ndarray:
        """Generate hourglass contour"""
        params = self.validate_parameters(**kwargs)

        img = np.zeros(img_size, dtype=np.uint8)
        h, w = img_size
        cx, cy = w // 2, h // 2
        base = int(params['base_size'] * min(scale, 2.0))

        width = base
        height = base
        waist = int(base * params['waist_ratio'])

        points = np.array([
            [cx - width, cy - height],
            [cx + width, cy - height],
            [cx + waist, cy],
            [cx + width, cy + height],
            [cx - width, cy + height],
            [cx - waist, cy],
        ], dtype=np.int32)

        cv2.fillPoly(img, [points], 255)

        contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours[0] if contours else points.reshape(-1, 1, 2)

    def get_default_parameters(self) -> Dict[str, Any]:
        return {'base_size': 50, 'waist_ratio': 0.3}


class LightningGenerator(BaseShapeGenerator):
    """Generator for lightning bolt shapes"""

    def __init__(self):
        super().__init__(ShapeType.LIGHTNING)

    def generate(self, scale: float = 1.0, img_size: Tuple[int, int] = (256, 256), **kwargs) -> np.ndarray:
        """Generate lightning bolt contour"""
        params = self.validate_parameters(**kwargs)

        img = np.zeros(img_size, dtype=np.uint8)
        h, w = img_size
        cx, cy = w // 2, h // 2
        base = int(params['base_size'] * min(scale, 2.0))

        # Lightning bolt zigzag pattern
        points = np.array([
            [cx, cy - base],
            [cx - base // 3, cy - base // 3],
            [cx + base // 4, cy - base // 3],
            [cx - base // 4, cy + base // 3],
            [cx + base // 3, cy + base // 3],
            [cx, cy + base],
            [cx + base // 6, cy],
            [cx - base // 6, cy],
        ], dtype=np.int32)

        cv2.fillPoly(img, [points], 255)

        contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours[0] if contours else points.reshape(-1, 1, 2)

    def get_default_parameters(self) -> Dict[str, Any]:
        return {'base_size': 50}


class ShapeFactory:
    """
    Factory class for creating shape generators and managing shape types
    """
    
    _generators: Dict[ShapeType, Type[BaseShapeGenerator]] = {}
    
    @classmethod
    def register_generator(cls, shape_type: ShapeType, generator_class: Type[BaseShapeGenerator]):
        """Register a shape generator"""
        cls._generators[shape_type] = generator_class
    
    @classmethod
    def create_generator(cls, shape_type: ShapeType) -> BaseShapeGenerator:
        """Create a shape generator for the specified type"""
        if shape_type not in cls._generators:
            raise ValueError(f"Unknown shape type: {shape_type}")
        
        generator_class = cls._generators[shape_type]
        
        # Handle special cases with parameters
        if shape_type == ShapeType.TRIANGLE:
            return PolygonGenerator(shape_type, 3)
        elif shape_type == ShapeType.SQUARE:
            return RectangleGenerator()  # Square is a special rectangle
        elif shape_type == ShapeType.DIAMOND:
            return PolygonGenerator(shape_type, 4)
        elif shape_type == ShapeType.PENTAGON:
            return PolygonGenerator(shape_type, 5)
        elif shape_type == ShapeType.HEXAGON:
            return PolygonGenerator(shape_type, 6)
        elif shape_type == ShapeType.OCTAGON:
            return PolygonGenerator(shape_type, 8)
        elif shape_type in (ShapeType.T_SHAPE, ShapeType.U_SHAPE, ShapeType.L_SHAPE,
                           ShapeType.C_SHAPE, ShapeType.S_SHAPE):
            return LetterShapeGenerator(shape_type)
        else:
            return generator_class()
    
    @classmethod
    def generate_shape(cls, 
                      shape_type: ShapeType, 
                      scale: float = 1.0, 
                      img_size: Tuple[int, int] = (256, 256),
                      **kwargs) -> np.ndarray:
        """
        Generate a shape contour
        
        Args:
            shape_type: Type of shape to generate
            scale: Scale factor
            img_size: Image canvas size
            **kwargs: Shape-specific parameters
            
        Returns:
            OpenCV contour array
        """
        generator = cls.create_generator(shape_type)
        return generator.generate(scale, img_size, **kwargs)
    
    @classmethod
    def get_available_shapes(cls) -> List[ShapeType]:
        """Get list of available shape types"""
        return list(cls._generators.keys())
    
    @classmethod
    def get_shape_info(cls, shape_type: ShapeType) -> Dict[str, Any]:
        """Get information about a shape type"""
        if shape_type not in cls._generators:
            raise ValueError(f"Unknown shape type: {shape_type}")
        
        generator = cls.create_generator(shape_type)
        return {
            'shape_type': shape_type,
            'generator_class': cls._generators[shape_type].__name__,
            'default_parameters': generator.get_default_parameters()
        }
    
    @classmethod
    def get_hard_negative_pairs(cls) -> List[Tuple[ShapeType, ShapeType]]:
        """Get pairs of similar-looking but different shapes for hard negative training"""
        return [
            (ShapeType.CIRCLE, ShapeType.OVAL),
            (ShapeType.CIRCLE, ShapeType.OCTAGON),
            (ShapeType.RECTANGLE, ShapeType.ROUNDED_RECT),
            (ShapeType.RECTANGLE, ShapeType.PARALLELOGRAM),
            (ShapeType.RECTANGLE, ShapeType.ROUNDED_CORNER_RECT),
            (ShapeType.HEXAGON, ShapeType.PENTAGON),
            (ShapeType.HEXAGON, ShapeType.OCTAGON),
            (ShapeType.TRIANGLE, ShapeType.ARROW),
            (ShapeType.SQUARE, ShapeType.DIAMOND),
            (ShapeType.ELLIPSE, ShapeType.OVAL)
        ]


# Register basic generators
ShapeFactory.register_generator(ShapeType.CIRCLE, CircleGenerator)
ShapeFactory.register_generator(ShapeType.ELLIPSE, EllipseGenerator)
ShapeFactory.register_generator(ShapeType.RECTANGLE, RectangleGenerator)
ShapeFactory.register_generator(ShapeType.SQUARE, RectangleGenerator)
ShapeFactory.register_generator(ShapeType.TRIANGLE, PolygonGenerator)
ShapeFactory.register_generator(ShapeType.DIAMOND, PolygonGenerator)
ShapeFactory.register_generator(ShapeType.PENTAGON, PolygonGenerator)
ShapeFactory.register_generator(ShapeType.HEXAGON, PolygonGenerator)
ShapeFactory.register_generator(ShapeType.OCTAGON, PolygonGenerator)
ShapeFactory.register_generator(ShapeType.STAR, StarGenerator)
ShapeFactory.register_generator(ShapeType.HEART, HeartGenerator)
ShapeFactory.register_generator(ShapeType.OVAL, OvalGenerator)
ShapeFactory.register_generator(ShapeType.ROUNDED_RECT, RoundedRectGenerator)
ShapeFactory.register_generator(ShapeType.ROUNDED_CORNER_RECT, RoundedCornerRectGenerator)
ShapeFactory.register_generator(ShapeType.CROSS, CrossGenerator)
ShapeFactory.register_generator(ShapeType.ARROW, ArrowGenerator)
ShapeFactory.register_generator(ShapeType.TRAPEZOID, TrapezoidGenerator)
ShapeFactory.register_generator(ShapeType.PARALLELOGRAM, ParallelogramGenerator)
ShapeFactory.register_generator(ShapeType.CRESCENT, CrescentGenerator)
ShapeFactory.register_generator(ShapeType.GEAR, GearGenerator)
ShapeFactory.register_generator(ShapeType.DONUT, DonutGenerator)
ShapeFactory.register_generator(ShapeType.HOURGLASS, HourglassGenerator)
ShapeFactory.register_generator(ShapeType.LIGHTNING, LightningGenerator)

# Register letter-shaped generators
ShapeFactory.register_generator(ShapeType.T_SHAPE, LetterShapeGenerator)
ShapeFactory.register_generator(ShapeType.U_SHAPE, LetterShapeGenerator)
ShapeFactory.register_generator(ShapeType.L_SHAPE, LetterShapeGenerator)
ShapeFactory.register_generator(ShapeType.C_SHAPE, LetterShapeGenerator)
ShapeFactory.register_generator(ShapeType.S_SHAPE, LetterShapeGenerator)

# Note: Additional complex shapes (gear, crescent, etc.) would be implemented
# as separate generator classes and registered here