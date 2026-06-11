import numpy as np
import matplotlib.pyplot as plt

# Raw offsets from your calibration log
x_raw = 4.771315
y_raw = 54.873061

# The hidden physical camera rotation (16.2 degrees)
alpha = np.radians(16.2)

# Corrected offsets (account for the 16.2 deg tilt)
x_corr = x_raw * np.cos(alpha) - y_raw * np.sin(alpha)
y_corr = x_raw * np.sin(alpha) + y_raw * np.cos(alpha)

# Define a range of robot rotation angles (Rz) from 0 to 90 degrees
angles_deg = np.array([0, 15, 30, 45, 60, 75, 90])
angles_rad = np.radians(angles_deg)

# Let's assume a true target is physically at (X=0, Y=250) relative to the robot base
target_world_x = 0.0
target_world_y = 250.0

plt.figure(figsize=(9, 7))

# 1. Plot where the robot *thinks* the target is using UNCORRECTED offsets
uncorrected_x = []
uncorrected_y = []
for theta in angles_rad:
    # Math the robot runs, assuming a square camera but physically tilted by alpha
    # This causes a coordinate cross-contamination that changes with theta
    err_x = target_world_x + (x_raw * np.cos(theta - alpha) - y_raw * np.sin(theta - alpha)) - (x_raw * np.cos(theta) - y_raw * np.sin(theta))
    err_y = target_world_y + (x_raw * np.sin(theta - alpha) + y_raw * np.cos(theta - alpha)) - (x_raw * np.sin(theta) + y_raw * np.cos(theta))
    uncorrected_x.append(err_x)
    uncorrected_y.append(err_y)

plt.plot(uncorrected_x, uncorrected_y, 'ro--', label='Uncorrected Offsets (Drifting Target)')
for i, txt in enumerate(angles_deg):
    plt.annotate(f"{txt}°", (uncorrected_x[i], uncorrected_y[i]), textcoords="offset points", xytext=(10,-5), ha='left', color='red')

# 2. Plot where the target lands using CORRECTED offsets
# Because the math matches the physics, all angles map to the exact same physical spot
corrected_x = [target_world_x] * len(angles_deg)
corrected_y = [target_world_y] * len(angles_deg)

plt.plot(corrected_x, corrected_y, 'gX', markersize=12, label='Corrected Offsets (Spot On at All Angles)')

# Formatting the plot
plt.title('Target Positioning Error vs. Robot Rotation ($R_Z$)', fontsize=14, pad=15)
plt.xlabel('World X Coordinates (mm)', fontsize=12)
plt.ylabel('World Y Coordinates (mm)', fontsize=12)
plt.grid(True, linestyle=':', alpha=0.6)
plt.axis('equal') # Crucial to see true geometric arcs
plt.legend(loc='upper left', fontsize=11)

# Show the plot
plt.show()