from pyluxel.debug.cprint import _CPrint
from pyluxel.debug.gpu_stats import GPUStats

cprint = _CPrint()
CPrint = cprint
Cprint = cprint

__all__ = ["cprint", "CPrint", "Cprint", "GPUStats"]
