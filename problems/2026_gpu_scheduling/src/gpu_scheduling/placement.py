"""Node-local worker capacity calculation retained from the research package."""
import numpy as np

def slots(free_g: np.ndarray, free_c: np.ndarray, q: int, c: int) -> np.ndarray:
    h = free_g // q
    if c: h = np.minimum(h, free_c // c)
    return h
