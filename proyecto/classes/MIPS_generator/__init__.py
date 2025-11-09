# classes/MIPS_generator/__init__.py
"""
MIPS Generator Package - Generación de código MIPS desde TAC
"""

from .mips_generator import MIPSGenerator
from .register_allocator import RegisterAllocator
from .mips_stack_manager import MIPSStackManager
from .mips_runtime import MIPSRuntime

__all__ = [
    'MIPSGenerator',
    'RegisterAllocator',
    'MIPSStackManager',
    'MIPSRuntime'
]
