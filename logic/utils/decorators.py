import inspect
import string
import logging
import functools
import time
from datetime import datetime
from typing import Literal

def log(
    template: str,
    level: int = 20,
    mode: Literal["before", "after", "both"] = "both"
):
    """
    Decorator to log function execution details including arguments,
    return values, timestamps, and execution duration.
    """
    # Define reserved words that are injected by the decorator
    RESERVED_VARS = {"status", "return_value", "timestamp", "duration"}
    template_vars = {name for _, name, _, _ in string.Formatter().parse(template) if name}

    def decorator(func):
        sig = inspect.signature(func)
        func_params = set(sig.parameters.keys())

        # Validation: Ensure all template variables are either function params or reserved words
        invalid_vars = template_vars - func_params - RESERVED_VARS
        if invalid_vars:
            raise RuntimeError(f"Invalid variables in log template for '{func.__name__}': {invalid_vars}")

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            # Prepare context with repr() of arguments for better visibility
            context = {k: repr(v) for k, v in bound.arguments.items()}

            def get_now_str():
                return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # --- BEFORE EXECUTION ---
            start_time = time.time()
            if mode in ("before", "both"):
                context["status"] = "BEFORE"
                context["return_value"] = "PENDING"
                context["timestamp"] = get_now_str()
                context["duration"] = "0.00s"
                logging.log(level, f"[START] {template.format(**context)}")

            try:
                result = func(*args, **kwargs)

                # --- AFTER EXECUTION ---
                end_time = time.time()
                if mode in ("after", "both"):
                    duration = end_time - start_time
                    context["status"] = "AFTER"
                    context["return_value"] = repr(result)
                    context["timestamp"] = get_now_str()
                    context["duration"] = f"{duration:.2f}s"
                    logging.log(level, f"[END]   {template.format(**context)}")

                return result
            except Exception as e:
                logging.error(f"[ERROR] {func.__name__} failed: {e}")
                raise
        return wrapper
    return decorator