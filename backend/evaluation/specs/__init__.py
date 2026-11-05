"""Case definitions for the held-out corpus.

Each module exports ``CASES``; this file concatenates them in a stable order.
"""
from .exceptions import CASES as EXCEPTION_CASES
from .multi_file import CASES as MULTI_FILE_CASES
from .mutation import CASES as MUTATION_CASES
from .none_handling import CASES as NONE_CASES
from .off_by_one import CASES as OFF_BY_ONE_CASES
from .operators import CASES as OPERATOR_CASES
from .state_updates import CASES as STATE_CASES
from .type_errors import CASES as TYPE_CASES

ALL_CASES = (
    OFF_BY_ONE_CASES
    + OPERATOR_CASES
    + NONE_CASES
    + MUTATION_CASES
    + TYPE_CASES
    + STATE_CASES
    + MULTI_FILE_CASES
    + EXCEPTION_CASES
)
