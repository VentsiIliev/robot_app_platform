import cv2
import matplotlib.pyplot as plt

# --- Board definition ---
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_250)

squares_x = 11
squares_y = 8
square_length_mm = 18.0
marker_length_mm = 12.0

board = cv2.aruco.CharucoBoard(
    (squares_x, squares_y),
    square_length_mm,
    marker_length_mm,
    aruco_dict
)

# --- Physical board size in mm ---
board_w_mm = squares_x * square_length_mm   # 198 mm
board_h_mm = squares_y * square_length_mm   # 144 mm

# --- A4 landscape size in mm ---
page_w_mm = 297.0
page_h_mm = 210.0

# --- Create raster board image at high resolution ---
dpi = 300
board_w_px = int(round(board_w_mm / 25.4 * dpi))
board_h_px = int(round(board_h_mm / 25.4 * dpi))

img = board.generateImage((board_w_px, board_h_px))
cv2.imwrite("charuco_a4_11x8_18mm_12mm.png", img)

# --- Create exact-size PDF on A4 landscape ---
fig = plt.figure(figsize=(page_w_mm / 25.4, page_h_mm / 25.4), dpi=dpi)
ax = fig.add_axes([0, 0, 1, 1])
ax.axis("off")

# Center board on page
x0_mm = (page_w_mm - board_w_mm) / 2.0
y0_mm = (page_h_mm - board_h_mm) / 2.0

# Place image with exact physical size
ax.imshow(
    img,
    cmap="gray",
    extent=[
        x0_mm / 25.4,
        (x0_mm + board_w_mm) / 25.4,
        y0_mm / 25.4,
        (y0_mm + board_h_mm) / 25.4,
    ],
    origin="lower",
)

ax.set_xlim(0, page_w_mm / 25.4)
ax.set_ylim(0, page_h_mm / 25.4)

plt.savefig("charuco_a4_11x8_18mm_12mm.pdf", dpi=dpi)
plt.close(fig)