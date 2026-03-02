import logging
from typing import Optional

import cv2
import numpy as np
from pyzbar.pyzbar import decode

_logger = logging.getLogger(__name__)


class QrDetectionService:

    def detect(self, image: Optional[np.ndarray]) -> Optional[str]:
        if image is None:
            _logger.warning("No image provided for QR/barcode detection")
            return None

        gray     = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        barcodes = decode(gray)
        _logger.info("Barcodes found: %d", len(barcodes))

        for barcode in barcodes:
            data = barcode.data.decode("utf-8")
            if data:
                x, y, w, h = barcode.rect
                cv2.rectangle(image, (x, y), (x + w, y + h), (255, 0, 0), 2)
                cv2.putText(image, f"{data} ({barcode.type})",
                            (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                _logger.info("Decoded: %s (%s)", data, barcode.type)
                return data

        return None