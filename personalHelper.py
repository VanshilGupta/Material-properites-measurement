import numpy as np
import time
import matplotlib.pyplot as plt


# def vdp_equation(rho):
#         return (np.exp(-np.pi * 0.5 / rho) + np.exp(-np.pi * 0.5 / rho)) - 1


# def run_exp():
#                 rho_grid = np.arange(5e-5, 1000, 10e-6)

#                 # Optimized version (fully vectorized NumPy)
#                 t2 = time.time()
#                 f_vec = np.abs(vdp_equation(rho_grid))
#                 f_vec_raw = vdp_equation(rho_grid)
#                 id_min_vec = np.nanargmin(f_vec)
#                 rho_min_vec = rho_grid[id_min_vec]
#                 vec_time = time.time() - t2
#                 print(f'Time elapsed: {vec_time}')
#                 print(f'Min rho: {rho_min_vec}')
#                 print(f'Value: {f_vec[id_min_vec]}')
                
#                 # Plot rho_grid vs f_vec
#                 plt.figure(figsize=(10, 6))
#                 plt.plot(rho_grid, f_vec_raw, linewidth=1.5)
#                 plt.xlabel('rho_grid')
#                 plt.ylabel('f_vec')
#                 plt.title('rho_grid vs f_vec')
#                 plt.grid(True, alpha=0.3)
                
#                 # Hold forever until user closes the window
#                 plt.show(block=True)
                


# run_exp()

# print(f"{'Temp (°C)':<12} {'Sigma (S/cm)':<18} {'Seebeck (µV/K)':<18}")

import PySide6

print(PySide6)