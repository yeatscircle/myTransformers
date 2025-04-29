import sys

from myTransformers.testing_utils import run_test_using_subprocess
from myTransformers.utils.import_utils import clear_import_cache


@run_test_using_subprocess
def test_clear_import_cache():
    """Test the clear_import_cache function."""

    # Save initial state
    initial_modules = {name: mod for name, mod in sys.modules.items() if name.startswith("myTransformers.")}
    assert len(initial_modules) > 0, "No myTransformers modules loaded before test"

    # Execute clear_import_cache() function
    clear_import_cache()

    # Verify modules were removed
    remaining_modules = {name: mod for name, mod in sys.modules.items() if name.startswith("myTransformers.")}
    assert len(remaining_modules) < len(initial_modules), "No modules were removed"

    # Import and verify module exists
    from myTransformers.models.auto import modeling_auto

    assert "myTransformers.models.auto.modeling_auto" in sys.modules
    assert modeling_auto.__name__ == "myTransformers.models.auto.modeling_auto"
