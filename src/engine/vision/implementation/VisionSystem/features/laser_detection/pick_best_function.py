import logging
import numpy as np
import matplotlib.pyplot as plt
from sklearn.preprocessing import PolynomialFeatures
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score

_logger = logging.getLogger(__name__)

# Calibration data
calibration_data = [
    (0, 0.0),
    (0.5, -0.5148642604821134),
    (1.0, -1.325464498663564),
    (1.5, -2.029709994717223),
    (2.0, -2.7585097412418236),
    (2.5, -3.2652337933582203),
    (3.0, -4.163599214929263),
    (3.5, -4.681674161871911),
    (4.0, -5.426653030913712),
    (4.5, -6.223797830469039),
    (5.0, -6.884406673975491),
    (5.5, -7.722956318810816),
    (6.0, -8.421546361335231),
    (6.5, -9.120635894201314),
    (7.0, -9.799338652471192),
    (7.5, -10.405487056047605),
    (8.0, -11.004121963097987),
    (8.5, -11.957868377918203),
    (9.0, -12.538644154490726),
    (9.5, -13.361083369786343),
    (10.0, -14.02152062360949),
    (10.5, -14.804019367411456),
    (11.0, -15.382957808226251),
    (11.5, -16.143512244316526),
    (12.0, -17.067588796282394),
    (12.5, -17.524950493609253),
    (13.0, -18.293655758448494),
    (13.5, -18.98507381185857),
    (14.0, -20.202199302284725),
    (14.5, -20.64664357494962),
    (15.0, -21.22472560083054)
]

heights = np.array([h for h, d in calibration_data]).reshape(-1, 1)
deltas = np.array([d for h, d in calibration_data])

# Automatically determine best polynomial degree
best_r2 = -np.inf
best_degree = 1
best_model = None
best_poly = None

max_degree = 6  # Can increase if needed

for degree in range(1, max_degree + 1):
    poly = PolynomialFeatures(degree)
    X_poly = poly.fit_transform(deltas.reshape(-1, 1))
    model = LinearRegression()
    model.fit(X_poly, heights)
    pred = model.predict(X_poly)
    r2 = r2_score(heights, pred)
    if r2 > best_r2:
        best_r2 = r2
        best_degree = degree
        best_model = model
        best_poly = poly

_logger.info(f"Best polynomial degree: {best_degree}, R²={best_r2:.4f}")


# Plot
plt.figure(figsize=(8,5))
plt.scatter(deltas, heights, color='blue', label='Measured data')  # pixel -> height
delta_range = np.linspace(deltas.min(), deltas.max(), 200).reshape(-1,1)
plt.plot(delta_range, best_model.predict(best_poly.transform(delta_range)), 'r-', label=f'Best fit degree={best_degree}')
plt.xlabel("Pixel Delta")
plt.ylabel("Robot Height (mm)")
plt.title("Laser Calibration Curve")
plt.grid(True)
plt.legend()
plt.show()

# Query function
def pixel_to_mm(pixel_delta):
    pixel_array = np.array([[pixel_delta]])
    return float(best_model.predict(best_poly.transform(pixel_array)))

# Test known and unknown pixel delta
_logger.info("Pixel -10.4 -> Height:", pixel_to_mm(-10.4))

_logger.info("Pixel -15.0 -> Height:", pixel_to_mm(-15.0))

_logger.info("Pixel -5.0 -> Height:", pixel_to_mm(-5.0))

